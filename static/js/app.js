// CareBoard page behaviour. Everything degrades gracefully: the pages work without any of this.

// ---- small helpers -------------------------------------------------------------------------------
// Submit a form when a control marked data-autosubmit changes (e.g. the status filter).
document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
  el.addEventListener("change", function () { el.form.submit(); });
});

// Ask before a risky click or submit. Uses delegation so it also works on content that refreshes itself.
document.addEventListener("click", function (e) {
  var btn = e.target.closest("[data-confirm]");
  if (btn && !window.confirm(btn.dataset.confirm)) e.preventDefault();
});
document.addEventListener("submit", function (e) {
  var message = e.target.dataset && e.target.dataset.confirmSubmit;
  if (message && !window.confirm(message)) e.preventDefault();
});

function debounce(fn, ms) {
  var timer;
  return function () { clearTimeout(timer); timer = setTimeout(fn, ms); };
}

// ---- triage: reference hints + suggested priority (the server does the maths) ----------------------
(function () {
  var form = document.querySelector("[data-triage]");
  if (!form || !form.dataset.assess) return;
  var RANK = { normal: 0, priority: 1, urgent: 2 };
  var NAMES = { normal: "Normal Level", priority: "Priority Level", urgent: "Urgent Level" };
  var hints = {};
  form.querySelectorAll("[data-hint-for]").forEach(function (el) { hints[el.dataset.hintFor] = el; });
  var box = form.querySelector("[data-suggest]");
  var levelEl = form.querySelector("[data-suggest-level]");
  var reasonsEl = form.querySelector("[data-suggest-reasons]");
  var override = form.querySelector("[data-override]");
  var suggested = null;

  function selected() {
    var checked = form.querySelector('input[name="priority"]:checked');
    return checked ? checked.value : "normal";
  }
  function syncOverride() {
    if (!override || !suggested) return;
    override.hidden = RANK[selected()] >= RANK[suggested];
  }
  function render(data) {
    Object.keys(hints).forEach(function (key) {
      var el = hints[key], h = data.hints[key];
      el.hidden = !h;
      el.textContent = h ? h[0] : "";
      el.className = "hint" + (h ? " hint--" + h[1] : "");
    });
    suggested = data.suggested;
    var anything = Object.keys(data.hints).length > 0;
    box.hidden = !anything;
    levelEl.textContent = NAMES[suggested];
    levelEl.className = "suggest__level suggest__level--" + suggested;
    reasonsEl.innerHTML = "";
    data.reasons.forEach(function (text) { var li = document.createElement("li"); li.textContent = text; reasonsEl.appendChild(li); });
    // Never lower the nurse's choice automatically, but do raise it when the numbers call for it.
    if (anything && RANK[suggested] > RANK[selected()]) {
      var radio = form.querySelector('input[name="priority"][value="' + suggested + '"]');
      if (radio) radio.checked = true;
    }
    syncOverride();
  }
  function ask() {
    var body = new FormData();
    body.append("csrfmiddlewaretoken", form.querySelector('[name="csrfmiddlewaretoken"]').value);
    ["temp", "bp", "pulse", "spo2", "resp", "pain", "weight", "height"].forEach(function (key) {
      var el = form.querySelector('[data-vital="' + key + '"]');
      body.append(key, el ? el.value : "");
    });
    fetch(form.dataset.assess, { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(render)
      .catch(function () { /* hints are optional: stay quiet if the network hiccups */ });
  }
  form.addEventListener("input", debounce(ask, 350));
  form.querySelectorAll('input[name="priority"]').forEach(function (r) { r.addEventListener("change", syncOverride); });
  ask();
})();

// ---- consultation notes: auto-save the draft while typing ---------------------------------------------
(function () {
  var form = document.querySelector("[data-consult]");
  if (!form) return;
  var label = document.querySelector("[data-saved-label]");
  var sending = false, dirty = false;

  function save() {
    if (sending) { dirty = true; return; }
    sending = true; dirty = false;
    fetch(form.dataset.autosave, { method: "POST", body: new FormData(form), credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) { if (label && data.saved_at) label.textContent = "Draft auto-saved at " + data.saved_at; })
      .catch(function () { if (label) label.textContent = "Auto-save failed. Use Save Draft."; })
      .finally(function () { sending = false; if (dirty) save(); });
  }
  var later = debounce(save, 1500);
  form.addEventListener("input", function () { if (label) label.textContent = "Saving…"; later(); });
})();

// ---- live refresh + alerts ---------------------------------------------------------------------------------
(function () {
  var box = document.querySelector("[data-live]");
  if (!box) return;
  var url = box.dataset.live;
  var body = box.querySelector("[data-live-body]");
  var role = box.dataset.liveRole || "";
  var seen = {};
  var toasts = document.querySelector(".toasts");

  function alertsIn(root) {
    var node = root.querySelector("#live-alerts");
    try { return node ? JSON.parse(node.textContent) : []; } catch (e) { return []; }
  }
  function beep() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.frequency.value = 880; gain.gain.value = 0.05;
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(); osc.stop(ctx.currentTime + 0.25);
    } catch (e) { /* sound is a bonus, not a requirement */ }
  }
  function toast(item) {
    if (!toasts) return;
    var el = document.createElement("div");
    el.className = "toast toast--" + item.kind;
    el.setAttribute("role", "alert");
    var text = document.createElement("span");
    text.textContent = item.text;
    var close = document.createElement("button");
    close.type = "button"; close.textContent = "×"; close.setAttribute("aria-label", "Dismiss");
    close.addEventListener("click", function () { el.remove(); });
    el.appendChild(text); el.appendChild(close);
    toasts.appendChild(el);
    if (item.kind !== "urgent") setTimeout(function () { el.remove(); }, 15000);
    if (item.kind === "urgent") beep();
  }
  function handle(items, announce) {
    items.forEach(function (item) {
      if (seen[item.id]) return;
      seen[item.id] = true;
      var relevant = item.kind === "urgent" || (item.kind === "ready" && role === "physician");
      if (announce && relevant) toast(item);
    });
  }
  handle(alertsIn(box), false); // what is already on the page when it opens is not "new"

  function poll() {
    if (document.hidden) return;
    var active = document.activeElement;
    if (active && body.contains(active) && /^(INPUT|SELECT|TEXTAREA)$/.test(active.tagName)) return; // don't disturb typing
    if (body.querySelector("details[open]")) return; // or an open "close visit" box
    fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(); })
      .then(function (html) {
        var holder = document.createElement("div");
        holder.innerHTML = html;
        handle(alertsIn(holder), true);
        body.innerHTML = html;
      })
      .catch(function () { /* try again next time */ });
  }
  setInterval(poll, 15000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
})();

// Add-user form: show only the fields that fit the chosen role.
(function () {
  var form = document.querySelector("[data-role-form]");
  if (!form) return;
  var select = form.querySelector('select[name="role"]');
  var groups = form.querySelectorAll("[data-role-group]");
  function sync() {
    var role = select.value;
    var active = role === "student" ? "student" : role === "administrator" ? "" : "staff";
    groups.forEach(function (el) { el.hidden = el.dataset.roleGroup !== active; });
  }
  select.addEventListener("change", sync);
  sync();
})();
