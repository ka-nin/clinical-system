// Auto-formatting for typed fields: dates (MM/DD/YYYY) and blood pressure (118 / 74).
// Add data-format="date" or data-format="bp" to an input. Without JavaScript the boxes still work, you just type the slashes.
(function (root) {
  "use strict";

  // 10141988 -> 10/14/1988. Slashes appear as you type; backspace removes them naturally.
  function fmtDate(raw, deleting) {
    var d = String(raw).replace(/\D/g, "").slice(0, 8);
    if (!deleting) {
      if (d.length === 1 && +d > 1) d = "0" + d;                          // typing 3 means March: 03/
      if (d.length === 3 && +d.charAt(2) > 3) d = d.slice(0, 2) + "0" + d.charAt(2);   // 10/4 means the 4th: 10/04/
    }
    var out = d.slice(0, 2);
    if (d.length > 2) out += "/" + d.slice(2, 4);
    if (d.length > 4) out += "/" + d.slice(4);
    if (!deleting && (d.length === 2 || d.length === 4)) out += "/";
    return out;
  }

  // 118074 -> 118 / 74. Systolic (top number) is 50-99 or 100-260, so the first digit tells how many digits it has.
  // Typing "/" (or a space or dash) after the top number also works.
  function fmtBP(raw, deleting) {
    var s = String(raw).replace(/^\D+/, "");
    var m = /^(\d+)(\D*)(.*)$/.exec(s);
    if (!m) return "";
    var first = m[1], sep = m[2], tail = m[3].replace(/\D/g, "");
    var sys, dia, slash;
    if (sep && first.length >= 2 && first.length <= 3) {   // separator typed by hand
      sys = first.slice(0, 3);
      dia = tail;
      slash = !deleting || tail.length > 0;
    } else {                                              // digits only: work out where the top number ends
      var digits = first + tail;
      var len = digits.charAt(0) === "1" || digits.charAt(0) === "2" ? 3 : 2;
      sys = digits.slice(0, len);
      dia = digits.slice(len);
      slash = dia.length > 0 || (!deleting && sys.length === len);
    }
    dia = dia.slice(0, dia.charAt(0) === "1" ? 3 : 2);    // bottom number: 30-99 or 100-160
    return slash ? sys + " / " + dia : sys;
  }

  var api = { fmtDate: fmtDate, fmtBP: fmtBP };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CareFormat = api;
  if (typeof document === "undefined") return;

  function bind(el, fn) {
    el.addEventListener("input", function (e) {
      var deleting = /^delete/.test(e.inputType || "");
      var pos = el.selectionStart;
      var atEnd = pos === null || pos >= el.value.length;
      var digitsBefore = (el.value.slice(0, pos || 0).match(/\d/g) || []).length;
      var out = fn(el.value, deleting);
      if (out === el.value) return;
      el.value = out;
      var place = out.length;
      if (!atEnd) {                                       // editing in the middle: keep the cursor next to the same digit
        var seen = 0;
        place = 0;
        for (var i = 0; i < out.length && seen < digitsBefore; i++) {
          if (/\d/.test(out.charAt(i))) seen++;
          place = i + 1;
        }
      }
      if (el.setSelectionRange) el.setSelectionRange(place, place);
    });
  }
  document.querySelectorAll('[data-format="date"]').forEach(function (el) { bind(el, fmtDate); });
  document.querySelectorAll('[data-format="bp"]').forEach(function (el) { bind(el, fmtBP); });
})(typeof window !== "undefined" ? window : globalThis);
