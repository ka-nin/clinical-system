"""Rebuilds static/css/dashboard.css.

The screens were drawn at larger scales than they are shown, so sizes written as @N (drawn at 1.46x), ~N (1.26x)
or ^N (1.29x) are divided down to real pixels. Plain px values are used as they are.
Edit the CSS text in this file, then run:  python tools/build_dashboard_css.py
"""
import re
K = 2108/1440  # the design was drawn at ~1.46x; @N = N design px -> real px
def u(m):
    v = float(m.group(1))/K
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s + "px"
css = r'''/* Dashboard shell (generated from the design at 1.46x; values are already scaled to real px). */
.app { display: flex; min-height: 100vh; background: #fafcff; font-family: var(--font-body); color: var(--ink); }

/* Sidebar */
.side { width: @380; flex-shrink: 0; background: #161b28; color: #fff; display: flex; flex-direction: column; padding: @45 @29 @35; position: sticky; top: 0; height: 100vh; }
.side__brand { display: flex; align-items: center; gap: @19; padding-left: 0; }
.side__mark { width: @52; height: @52; border-radius: @13; background: #4a83c3; display: grid; place-items: center; flex-shrink: 0; }
.side__mark svg { width: @32; height: @32; }
.side__name { font: 600 @26/1.15 var(--font-head); color: #fff; display: block; }
.side__by { font-size: @16; color: #9aa3b8; display: block; margin-top: @6; }
.side__nav { flex: 1; display: flex; flex-direction: column; gap: @11; margin-top: @51; }
.side__link { display: flex; align-items: center; gap: @17; height: @62; padding: 0 @20; border-radius: @31; font: 500 @20 var(--font-body); color: #9aa3b8; background: none; border: 0; width: 100%; cursor: pointer; text-align: left; }
.side__link svg { width: @28; height: @28; flex-shrink: 0; }
.side__link:hover { color: #fff; background: #1d2231; }
.side__link.is-active { background: #262a38; color: #fff; }
.side__signout { margin-top: auto; }
.side__signout form { margin: 0; }
.side__footer { border-top: 1px solid #242938; padding-top: @24; margin-top: @16; }
.usercard { display: flex; align-items: center; gap: @18; height: @99; padding: 0 @18; border-radius: @16; background: #1d212f; border: 1px solid #272c3b; }
.usercard__avatar { width: @64; height: @64; border-radius: 50%; background: #4a83c3; color: #fff; display: grid; place-items: center; font: 600 @22 var(--font-head); flex-shrink: 0; }
.usercard__text { min-width: 0; flex: 1; }
.usercard__name, .usercard__role { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.usercard__name { font: 600 @21/1.3 var(--font-head); color: #fff; }
.usercard__role { font-size: @17; color: #9aa3b8; margin-top: @2; }
.usercard__dot { width: @12; height: @12; border-radius: 50%; background: #5fbf7f; flex-shrink: 0; }

/* Main */
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.topbar { height: @102; padding: 0 @48; display: flex; align-items: center; justify-content: space-between; gap: @24; background: #fff; border-bottom: 1px solid #edf1f6; }
.crumbs { font-size: @16.2; color: #9aa3b8; line-height: @24; }
.crumbs span { margin: 0 @8; }
.topbar h1 { font: 600 @29.6/1.25 var(--font-head); color: var(--ink); margin-top: @8; }
.shift { display: flex; align-items: center; gap: @24; font-size: @19.2; color: #475569; white-space: nowrap; }
.shift__icon { width: @47; height: @47; border-radius: @13; background: #eff3f8; color: #3b4358; display: grid; place-items: center; }
.shift__icon svg { width: @26; height: @26; }
.content { padding: @48; display: flex; flex-direction: column; gap: @36; }

/* Welcome banner */
.banner { background: #eff6fc; border-radius: @16; padding: @20 @29 @20 @30; min-height: @131; display: flex; align-items: center; justify-content: space-between; gap: @24; }
.banner h2 { font: 600 @32.5/@38 var(--font-head); color: var(--ink); }
.banner p { font-size: @20; line-height: @28; color: #475569; margin-top: @2; }
.banner__actions { display: flex; gap: @18; flex-shrink: 0; }
.abtn { display: inline-flex; align-items: center; gap: @12; height: @54; padding: 0 @21; border-radius: @9; font: 500 @19 var(--font-body); color: #fff; white-space: nowrap; transition: filter .15s; }
.abtn:hover { filter: brightness(.94); }
.abtn svg { width: @26; height: @26; }
.abtn--green { background: #549387; }
.abtn--blue { background: #4a83c3; }

/* Stat cards */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: @31; }
.stat { position: relative; background: #fff; border: 1px solid #e8edf4; border-radius: @20; padding: @28 @29 0; height: @180; }
.stat__label { display: block; font-size: @18; font-weight: 500; color: #475569; line-height: @26; text-transform: uppercase; letter-spacing: .005em; }
.stat__value { display: block; font: 700 @44/@54 var(--font-head); color: var(--ink); margin-top: @17; }
.stat__sub { display: block; font-size: @17; color: #9aa3b8; line-height: @26; margin-top: @2; }

/* Lower panels */
.lower { display: grid; grid-template-columns: 1.6fr 1fr; gap: @36; align-items: start; }
.panel { background: #fff; border: 1px solid #e8edf4; border-radius: @24; padding: @35; min-width: 0; }
.panel__head { display: flex; align-items: center; justify-content: space-between; gap: @16; height: @36; }
.panel__head h3 { font: 600 @24/1.2 var(--font-head); color: var(--ink); }
.pill-chip { display: inline-flex; align-items: center; height: @34; padding: 0 @13; border-radius: 999px; font: 500 @17 var(--font-body); white-space: nowrap; }
.pill-chip--yellow { background: #fbf0c8; color: #e0a020; }
.pill-chip--red { background: #fbe1e1; color: #dc5b5b; }
.pill-chip--green { background: #d6f5e2; color: #46b26f; }
.pill-chip--blue { background: #e5f2fe; color: #2f6aa8; }
.queue { margin-top: @29; display: flex; flex-direction: column; gap: @18; }
.qrow { display: flex; align-items: center; gap: @24; height: @87; padding: 0 @19 0 @17; border: 1px solid #e6ecf4; border-radius: @14; background: #fafcff; }
.qrow__avatar { width: @52; height: @52; border-radius: 50%; background: #e2eef9; color: #4a83c3; display: grid; place-items: center; font: 600 @18 var(--font-head); flex-shrink: 0; }
.qrow__who { min-width: 0; }
.qrow__name { display: block; font: 500 @21/1.3 var(--font-head); color: var(--ink); }
.qrow__meta { display: block; font-size: @15.3; color: #475569; margin-top: @1; }
.qrow__right { margin-left: auto; display: flex; align-items: center; gap: @23; flex-shrink: 0; }
.qrow__stage { font-size: @16.6; color: #334155; }
.qrow__wait { font-size: @16; color: #9aa3b8; }

.audit-panel .panel__head h3 { font-size: @23; }
.alog { margin-top: @29; }
.alog__item { padding-bottom: @9; border-bottom: 1px solid #ecf0f6; }
.alog__item + .alog__item { margin-top: @24; }
.alog__item:last-child { border-bottom: 0; padding-bottom: 0; }
.alog__top { display: flex; align-items: center; justify-content: space-between; height: @36; }
.alog__time { font-size: @15.5; font-weight: 500; color: #8a94a8; }
.alog__tag { display: inline-flex; align-items: center; height: @36; padding: 0 @14; border-radius: 999px; font: 500 @16 var(--font-body); text-transform: uppercase; }
.alog__tag--modified { background: #e5f2fe; color: #2f6aa8; }
.alog__tag--authorized { background: #d8f5e3; color: #4bb374; }
.alog__tag--created { background: #e9ecf2; color: #3d4658; }
.alog__tag--system { background: #e5e8ef; color: #3d4658; }
.alog__text { font-size: @17.6; line-height: @28; color: #1e293b; margin-top: @10; }

/* Student portal */
.empty { text-align: center; padding: @70 @35; color: #475569; }
.empty h3 { font: 600 @26 var(--font-head); color: var(--ink); margin-bottom: @10; }
.empty p { font-size: @19; max-width: 520px; margin: 0 auto; }


/* Flash messages, forms and inner pages */
.flash { padding: 14px 18px; border-radius: 12px; font-size: 15px; background: #e5f2fe; color: #2b5f9e; }
.flash--success { background: #dcfce7; color: #166534; }
.flash--error { background: #fee2e2; color: #b91c1c; }
.crumbs a:hover { color: #4a83c3; }
.abtn { border: 0; cursor: pointer; }
.abtn--ghost { background: #eef2f7; color: #334155; }
.abtn--sm { height: 40px; font-size: 14px; padding: 0 16px; border-radius: 8px; }
.qrow__right form { margin: 0; }
.muted-empty { padding: 28px 8px; text-align: center; color: #64748b; font-size: 15px; }
.muted-empty a { color: #4a83c3; font-weight: 600; }
.qrow--link { color: inherit; transition: border-color .15s, background .15s; }
.qrow--link:hover { border-color: #b9cfe8; background: #f4f9fe; }
.formpanel { max-width: 860px; }
.formpanel__lead { color: #475569; font-size: 15px; margin-bottom: 24px; }
.formpanel__note { margin-top: 16px; font-size: 13px; color: #64748b; }
.checkline { display: flex; align-items: center; gap: 10px; margin-top: 22px; font-size: 15px; color: #334155; cursor: pointer; }
.checkline input { width: 18px; height: 18px; accent-color: #dc5b5b; }
.form-actions { display: flex; gap: 12px; margin-top: 26px; flex-wrap: wrap; }
.reg__grid--3 { grid-template-columns: repeat(3, 1fr); }
.reg__field textarea, .reg__field select { border: 1px solid #e4eaf2; border-radius: 10px; background: #fff; font: 400 15.8px var(--font-body); color: var(--ink); padding: 12px 16px; width: 100%; }
.reg__field select { height: 52px; padding: 0 12px; }
.reg__field textarea:focus, .reg__field select:focus { outline: 3px solid rgba(74,131,195,.25); border-color: #4a83c3; }
.reg__field input[type=number], .reg__field input[type=search] { height: 52px; padding: 0 16px; border: 1px solid #e4eaf2; border-radius: 10px; background: #fff; font: 400 15.8px var(--font-body); color: var(--ink); width: 100%; }
.reg__field input[type=number]:focus { outline: 3px solid rgba(74,131,195,.25); border-color: #4a83c3; }
.reg__field .req { color: #dc2626; }
.toolbar { display: flex; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.toolbar input[type=search] { flex: 1; min-width: 220px; height: 48px; padding: 0 16px; border: 1px solid #e4eaf2; border-radius: 10px; font: 400 15px var(--font-body); }
.toolbar .abtn { height: 48px; }
.qrow--link, .queue .qrow { text-decoration: none; }
.lower--detail { grid-template-columns: 1fr 1.4fr; }
.facts > div { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid #ecf0f6; font-size: 15px; }
.facts > div:last-child { border-bottom: 0; }
.facts dt { color: #64748b; }
.facts dd { margin: 0; font-weight: 500; text-align: right; }
.facts { margin: 12px 0 0; }
.text-danger { color: #dc2626; }
.visits { margin-top: 20px; display: flex; flex-direction: column; gap: 14px; }
.visit { border: 1px solid #e6ecf4; border-radius: 14px; padding: 16px 18px; background: #fafcff; }
.visit__top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.visit__top strong { font-size: 15px; }
.visit__complaint { margin-top: 10px; font-size: 15px; color: #1e293b; }
.visit__complaint.muted { color: #94a3b8; }
.vchips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.vchips span { background: #fff; border: 1px solid #e6ecf4; border-radius: 999px; padding: 4px 12px; font-size: 13px; color: #334155; }
.banner--patient .allergy { font-size: 16px; color: #475569; }
@media (max-width: 1180px) { .lower--detail { grid-template-columns: 1fr; } }
@media (max-width: 860px) { .reg__grid--3 { grid-template-columns: 1fr; } }

/* Patient directory */
.dir { padding: @35; }
.dir__toolbar { display: flex; align-items: center; gap: @18; flex-wrap: wrap; }
.dir__search { display: flex; align-items: center; gap: @14; width: @410; max-width: 100%; height: @53; padding: 0 @22; border: 1px solid #e3eaf3; border-radius: @10; background: #fafcff; color: #8a94a8; }
.dir__search svg { width: @24; height: @24; flex-shrink: 0; }
.dir__search input { border: 0; background: none; outline: 0; width: 100%; font: 400 @19 var(--font-body); color: var(--ink); }
.dir__search input::placeholder { color: #9aa3b8; }
.dir__search:focus-within { border-color: #4a83c3; box-shadow: 0 0 0 3px rgba(74,131,195,.18); }
.dir__status { position: relative; display: inline-flex; align-items: center; gap: @8; height: @53; padding: 0 @20; border: 1px solid #e3eaf3; border-radius: @10; background: #fff; font: 500 @18.5 var(--font-body); color: #334155; }
.dir__status select { appearance: none; -webkit-appearance: none; border: 0; background: none; font: inherit; color: inherit; padding: 0 @22 0 0; cursor: pointer; outline: 0; }
.dir__status svg { position: absolute; right: @16; width: @20; height: @20; pointer-events: none; }
.dir__status:focus-within { border-color: #4a83c3; box-shadow: 0 0 0 3px rgba(74,131,195,.18); }
.dir__count { margin-left: auto; display: inline-flex; align-items: center; height: @40; padding: 0 @16; border-radius: 999px; background: #e5f2fe; color: #2f6aa8; font: 600 @17.5 var(--font-body); letter-spacing: .01em; white-space: nowrap; }
.dir__table { margin-top: @36; border-top: 1px solid #e7ecf3; }
.dir__row { display: grid; grid-template-columns: 205fr 290fr 234fr 264fr 234fr 190fr 147fr; align-items: center; min-height: @88; padding: 0 @24; border-bottom: 1px solid #e7ecf3; font-size: @19; color: #475569; }
.dir__row > span { min-width: 0; }
.dir__row--head { min-height: @80; background: #fafcff; font: 600 @17 var(--font-body); color: #475569; text-transform: uppercase; letter-spacing: .01em; }
.dir__right { text-align: right; }
.dir__id { color: #4586c6; font-weight: 500; }
.dir__id:hover { text-decoration: underline; }
.dir__name { font: 600 @19 var(--font-head); color: var(--ink); }
.dir__badge { display: inline-flex; align-items: center; height: @37; padding: 0 @15; border-radius: 999px; font: 500 @17 var(--font-body); font-style: normal; }
.dir__badge--active { background: #d9f6e4; color: #46b26f; }
.dir__badge--inactive { background: #e3e7ef; color: #475569; }
.dir__view { display: inline-flex; align-items: center; height: @43; padding: 0 @17; border: 1px solid #e3eaf3; border-radius: @9; background: #fafcff; font: 500 @17.5 var(--font-body); color: var(--ink); white-space: nowrap; transition: background .15s; }
.dir__view:hover { background: #eef4fb; }
.dir__foot { display: flex; align-items: center; justify-content: space-between; gap: @16; margin-top: @70; font-size: @18.5; color: #9aa3b8; }
.dir__pager { display: flex; gap: @12; }
.dir__pbtn { display: inline-flex; align-items: center; height: @47; padding: 0 @17; border: 1px solid #e3eaf3; border-radius: @9; background: #fff; font: 500 @17.5 var(--font-body); color: #475569; }
.dir__pbtn--next { background: #4a83c3; border-color: #4a83c3; color: #fff; }
a.dir__pbtn:hover { filter: brightness(.96); }
.dir__pbtn.is-off { opacity: .45; cursor: default; }
@media (max-width: 1100px) {
  .dir__row { grid-template-columns: 1.1fr 1.5fr 1.2fr 1.4fr; row-gap: 6px; padding-top: 12px; padding-bottom: 12px; }
  .dir__row--head { display: none; }
  .dir__count { margin-left: 0; }
}

/* Registration flow + intake form */
.flowcard { display: flex; align-items: center; justify-content: space-between; gap: @24; flex-wrap: wrap; background: #fff; border: 1px solid #e8edf4; border-radius: @20; padding: @24 @29; min-height: @115; }
.flowcard h3 { font: 600 @21.7/1.3 var(--font-head); color: var(--ink); }
.flowcard p { margin-top: @6; font-size: @17; color: #8a94a8; }
.stepper { display: flex; align-items: center; gap: @22; list-style: none; margin: 0; padding: 0; }
.stepper__item { display: inline-flex; align-items: center; gap: @10; font: 500 @17.5 var(--font-body); color: #9aa3b8; }
.stepper__item.is-active { color: var(--ink); font-weight: 600; }
.stepper__dot { width: @26; height: @26; border-radius: 50%; background: #e5eaf2; display: inline-block; }
.stepper__item.is-active .stepper__dot { background: #4a83c3; }
.stepper__line { width: @55; height: 1px; background: #d9dfe8; }
.draftbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.draftbar form { margin: 0; }
.draftbar__btn { border: 0; background: none; color: #2b5f9e; font: 600 14px var(--font-body); cursor: pointer; text-decoration: underline; }

.ik { background: #fff; border: 1px solid #e8edf4; border-radius: @24; padding: @47 @47 @46; }
.ik h3 { font: 600 @22.5/1.3 var(--font-head); color: var(--ink); }
.ik__cols { display: grid; grid-template-columns: 1fr 1fr; gap: @47; }
.ik__grid { display: grid; grid-template-columns: 1fr 1fr; gap: @28 @24; margin-top: @28; }
.ik__grid--3 { grid-template-columns: repeat(3, 1fr); }
.ik__field { display: flex; flex-direction: column; min-width: 0; }
.ik__field--wide { grid-column: 1 / -1; }
.ik__field label { font: 500 @18/1.35 var(--font-body); color: #4b5567; margin-bottom: @11; }
.ik .req { color: #dc2626; }
.ik__field input, .ik__field select { height: @62; padding: 0 @20; border: 1px solid #e6ecf5; border-radius: @10; background-color: #fafcff; font: 400 @19.5 var(--font-body); color: #334155; width: 100%; }
.ik__field input::placeholder { color: #a3adbd; }
.ik__field select { appearance: none; -webkit-appearance: none; padding-right: @50; cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238a94a8' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right @18 center; background-size: @26; }
.ik__field input:focus, .ik__field select:focus { outline: 3px solid rgba(74,131,195,.22); border-color: #4a83c3; }
.ik__field.has-error input, .ik__field.has-error select { border-color: #f87171; }
.ik__err { margin-top: 6px; font-size: 13px; color: #b91c1c; }
.ik__rule { border: 0; border-top: 1px solid #e7ecf3; margin: @36 0 @38; }
.ik__actions { display: flex; justify-content: flex-end; gap: @17; margin-top: @41; flex-wrap: wrap; }
.ik__btn { display: inline-flex; align-items: center; justify-content: center; gap: @12; height: @62; padding: 0 @34; border-radius: @10; font: 500 @19 var(--font-body); cursor: pointer; transition: filter .15s, background .15s; }
.ik__btn svg { width: @26; height: @26; }
.ik__btn--ghost { background: #fff; border: 1px solid #e3eaf3; color: #1e293b; }
.ik__btn--ghost:hover { background: #f4f7fb; }
.ik__btn--primary { background: #4a83c3; border: 1px solid #4a83c3; color: #fff; }
.ik__btn--primary:hover { filter: brightness(.94); }
@media (max-width: 1100px) { .ik__cols { grid-template-columns: 1fr; gap: 28px; } }
@media (max-width: 760px) { .ik__grid, .ik__grid--3 { grid-template-columns: 1fr; } .ik { padding: 22px; } .stepper__line { width: 20px; } }

/* Triage & clinical pre-check */
.ptcard { display: flex; align-items: center; gap: @24; flex-wrap: wrap; background: #fff; border: 1px solid #e8edf4; border-radius: @20; padding: @26 @29; min-height: @124; }
.ptcard__avatar { width: @68; height: @68; border-radius: 50%; background: #e2eef9; color: #4a83c3; display: grid; place-items: center; font: 600 @22 var(--font-head); flex-shrink: 0; }
.ptcard__who h2 { font: 600 @25/1.25 var(--font-head); color: var(--ink); }
.ptcard__who p { margin-top: @4; font-size: @18; color: #475569; }
.waitchip { margin-left: auto; display: inline-flex; align-items: center; gap: @10; height: @39; padding: 0 @18; border-radius: 999px; background: #fbe1e1; color: #d94b4b; font: 600 @17.5 var(--font-body); white-space: nowrap; }
.waitchip i { width: @10; height: @10; border-radius: 50%; background: currentColor; }
.waitchip--ok { background: #d9f6e4; color: #46b26f; }

.tri__stack { display: flex; flex-direction: column; gap: @10; }
.vgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: @30; margin-bottom: @20; }
.vcard { background: #fff; border: 1px solid #e8edf4; border-radius: @20; padding: @29; min-height: @167; }
.vcard__top { display: flex; align-items: center; justify-content: space-between; gap: @12; min-height: @35; }
.vcard__top label { font: 500 @19 var(--font-body); color: #334155; }
.vcard__row { display: flex; align-items: center; gap: @12; margin-top: @26; }
.vcard__row input { width: @198; height: @55; padding: 0 @16; border: 1px solid #e6ecf5; border-radius: @8; background: #fafcff; font: 600 @24 var(--font-head); color: var(--ink); }
.vcard__row input::placeholder { color: #c3cbd8; font-weight: 500; }
.vcard__row input:focus { outline: 3px solid rgba(74,131,195,.22); border-color: #4a83c3; }
.vcard.has-error .vcard__row input { border-color: #f87171; }
.vcard__unit { font-size: @18; color: #9aa3b8; }
.hint { display: inline-flex; align-items: center; height: @35; padding: 0 @14; border-radius: 999px; font: 500 @17 var(--font-body); }
.hint[hidden] { display: none; }
.hint--ok { background: #d9f6e4; color: #46b26f; }
.hint--warn { background: #fbf0c8; color: #d99a1e; }
.hint--bad { background: #fbe1e1; color: #d94b4b; }

.assess { background: #fff; border: 1px solid #e8edf4; border-radius: @20; padding: @32 @34 @32; }
.assess h3, .assess h3 label { font: 600 @19 var(--font-head); color: var(--ink); }
.assess textarea { display: block; width: 100%; margin-top: @16; min-height: @111; padding: @22; border: 1px solid #e6ecf5; border-radius: @12; background: #fafcff; font: 400 @19 var(--font-body); color: #1e293b; resize: vertical; }
.assess textarea:focus { outline: 3px solid rgba(74,131,195,.22); border-color: #4a83c3; }
.assess__sub { margin-top: @34; }
.prio { display: flex; flex-wrap: wrap; gap: @17; margin-top: @21; }
.prio__opt { position: relative; cursor: pointer; }
.prio__opt input { position: absolute; opacity: 0; inset: 0; }
.prio__opt span { display: inline-flex; align-items: center; gap: @12; height: @52; padding: 0 @22; border: 1.5px solid transparent; border-radius: @10; font: 500 @19 var(--font-body); }
.prio__opt i { width: @11; height: @11; border-radius: 50%; background: currentColor; }
.prio__opt--normal span { background: #f1faf5; color: #46b26f; }
.prio__opt--priority span { background: #fbf0c8; color: #d99a1e; }
.prio__opt--urgent span { background: #fbe1e1; color: #d94b4b; }
.prio__opt--normal input:checked + span { background: #d9f6e4; border-color: #46b26f; }
.prio__opt--priority input:checked + span { border-color: #d99a1e; }
.prio__opt--urgent input:checked + span { border-color: #d94b4b; }
.prio__opt input:focus-visible + span { outline: 3px solid rgba(74,131,195,.35); outline-offset: 2px; }
.assess .ik__actions { margin-top: @44; }
.ik__btn--green { background: #549387; border: 1px solid #549387; color: #fff; }
.ik__btn--green:hover { filter: brightness(.94); }
.assess .formpanel__note { text-align: right; }
@media (max-width: 1180px) { .vgrid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .vgrid { grid-template-columns: 1fr; } .waitchip { margin-left: 0; } }

/* Clinical consultation suite (design drawn at 1.26x; ~N = N design px) */
.suite { display: grid; grid-template-columns: minmax(0, 1fr) ~427; gap: ~32; align-items: stretch; min-height: calc(100vh - 70px - 66px); }
.suite__main { display: flex; flex-direction: column; gap: ~31; min-width: 0; }
.pcard { display: flex; align-items: center; flex-wrap: wrap; gap: ~22 ~18; background: #fff; border: 1px solid #e6ecf4; border-radius: ~20; padding: ~25; }
.pcard__avatar { width: ~68; height: ~68; border-radius: 50%; background: #e5f0fa; color: #4a83c3; display: grid; place-items: center; font: 600 ~22 var(--font-head); flex-shrink: 0; }
.pcard__who { flex: 1 1 ~200; min-width: 0; }
.pcard__who h2 { font: 600 ~26/1.2 var(--font-head); color: var(--ink); display: flex; align-items: center; gap: ~12; flex-wrap: wrap; }
.pcard__code { font: 600 ~14 var(--font-body); background: #e5f2fe; color: #2f6aa8; padding: ~3 ~11; border-radius: 999px; }
.pcard__who p { margin-top: ~4; font-size: ~14.5; color: #475569; }
.tabs { margin-left: auto; display: flex; flex-wrap: wrap; gap: ~8; }
.tab { display: inline-flex; align-items: center; height: ~40; padding: 0 ~15; border: 1px solid #e3eaf3; border-radius: ~8; background: #fafcff; font: 500 ~15.5 var(--font-body); white-space: nowrap; color: #475569; transition: background .15s; }
.tab:hover { background: #eef4fb; }
.tab.is-active { background: #4a83c3; border-color: #4a83c3; color: #fff; }

.tsum { background: #f2f9ff; border: 1px solid #cfe6fa; border-radius: ~16; padding: ~20 ~20 ~22; }
.tsum__head { display: flex; align-items: center; justify-content: space-between; gap: ~16; flex-wrap: wrap; }
.tsum__head h3 { display: flex; align-items: center; gap: ~10; font: 600 ~18 var(--font-head); color: #3b6fa5; }
.tsum__head svg { width: ~22; height: ~22; }
.tsum__head > span { font-size: ~14; color: #475569; }
.tsum__grid { display: flex; flex-wrap: wrap; gap: ~18 ~40; margin-top: ~16; }
.tsum__grid span { display: block; font-size: ~14; color: #64748b; text-transform: uppercase; }
.tsum__grid strong { display: block; margin-top: ~4; font: 600 ~21 var(--font-head); color: var(--ink); }
.tsum__complaint { margin-top: ~16; font-size: ~15; color: #334155; }

.soap { display: grid; grid-template-columns: 1fr 1fr; gap: ~22 ~21; }
.soapcard { display: flex; flex-direction: column; background: #fff; border: 1px solid #e6ecf4; border-radius: ~16; padding: ~20; min-height: ~188; cursor: text; }
.soapcard:focus-within { border-color: #4a83c3; box-shadow: 0 0 0 3px rgba(74,131,195,.16); }
.soapcard h4 { font: 600 ~17.5 var(--font-head); color: var(--ink); }
.soapcard textarea { flex: 1; width: 100%; margin-top: ~12; border: 0; outline: 0; resize: none; background: transparent; font: 400 ~16/1.35 var(--font-body); color: #475569; padding: 0; min-height: ~120; }
.soapcard textarea::placeholder { color: #b0b9c7; }
.soapcard__text { margin-top: ~12; font-size: ~16; line-height: 1.35; color: #475569; white-space: pre-wrap; }
.suite__empty { background: #fff; border: 1px dashed #d5dde8; border-radius: ~20; padding: ~50 ~30; text-align: center; color: #64748b; }
.suite__empty h3 { font: 600 ~22 var(--font-head); color: var(--ink); margin-bottom: ~8; }
.suite__empty a { color: #4a83c3; font-weight: 600; }
.suite__viewing { font-size: ~16; color: #475569; }
.suite__form { display: flex; flex-direction: column; flex: 1; gap: ~24; }
.suite__actions { margin-top: auto; padding-top: ~16; display: flex; align-items: center; justify-content: space-between; gap: ~16; flex-wrap: wrap; }
.suite__saved { font-size: ~14; color: #9aa3b8; }
.suite__btns { display: flex; gap: ~15; flex-wrap: wrap; }
.sbtn { display: inline-flex; align-items: center; gap: ~9; height: ~47; padding: 0 ~21; border-radius: ~8; font: 500 ~16 var(--font-body); cursor: pointer; transition: filter .15s, background .15s; }
.sbtn svg { width: ~20; height: ~20; }
.sbtn--ghost { background: #fff; border: 1px solid #e3eaf3; color: #1e293b; }
.sbtn--ghost:hover { background: #f4f7fb; }
.sbtn--primary { background: #4a83c3; border: 1px solid #4a83c3; color: #fff; }
.sbtn--primary:hover { filter: brightness(.94); }

.tline { background: #fff; border: 1px solid #e6ecf4; border-radius: ~20; padding: ~25; align-self: stretch; }
.tline h3 { font: 600 ~20 var(--font-head); color: var(--ink); margin-bottom: ~14; }
.tline__item { display: block; padding: ~18 0 ~20; border-bottom: 1px solid #edf1f6; color: inherit; }
.tline__item:last-child { border-bottom: 0; }
.tline__top { display: flex; align-items: center; justify-content: space-between; }
.tline__top time { font: 600 ~15 var(--font-body); color: #9aa3b8; }
.tline__item.is-current .tline__top time { color: #4a83c3; }
.tline__top i { font-style: normal; font: 600 ~12.5 var(--font-body); color: #3b6fa5; background: #e5f2fe; padding: ~4 ~11; border-radius: ~6; letter-spacing: .02em; }
.tline__item strong { display: block; margin-top: ~9; font: 600 ~18 var(--font-head); color: var(--ink); }
.tline__item small { display: block; margin-top: ~12; font-size: ~14; color: #64748b; }
.tline__item:hover strong { color: #4a83c3; }
@media (max-width: 1180px) { .suite { grid-template-columns: 1fr; } .tabs { margin-left: 0; } }
@media (max-width: 700px) { .soap { grid-template-columns: 1fr; } }

/* Safety, live areas and record tools */
.live, .live__body { display: flex; flex-direction: column; gap: 25px; }
.flash--warn { background: #fef3c7; color: #92400e; }
.flash a { color: inherit; font-weight: 600; text-decoration: underline; }
.text-warn { color: #b45309; }
.allergy { display: flex; align-items: center; gap: 12px; padding: 12px 18px; border-radius: 12px; font-size: 15px; }
.allergy svg { width: 20px; height: 20px; flex-shrink: 0; }
.allergy--listed { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; font-size: 16px; }
.allergy--none { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.allergy--unknown { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.allergy a { color: inherit; font-weight: 600; text-decoration: underline; }

.matches { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 16px; padding: 20px 24px; }
.matches h3 { font: 600 18px var(--font-head); color: #92400e; }
.matches p { margin-top: 4px; color: #92400e; font-size: 14px; }
.matches ul { list-style: none; margin: 14px 0; display: flex; flex-direction: column; gap: 10px; }
.matches li { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; background: #fff; border: 1px solid #fde68a; border-radius: 12px; padding: 12px 16px; }
.matches li strong { display: block; font-size: 15px; }
.matches li span { font-size: 13px; color: #64748b; }
.ik__btn--sm { height: 38px; padding: 0 16px; font-size: 14px; }

.suggest { margin-top: 16px; padding: 12px 16px; border-radius: 12px; background: #f1f5f9; font-size: 14px; color: #334155; }
.suggest ul { margin: 6px 0 4px 18px; }
.suggest small { color: #64748b; }
.suggest__level { font-weight: 700; }
.suggest__level--normal { color: #46b26f; } .suggest__level--priority { color: #d99a1e; } .suggest__level--urgent { color: #d94b4b; }
.suggest[hidden], .assess__override[hidden] { display: none; }
.assess__override { margin-top: 14px; }
.assess__override label { font: 500 14px var(--font-body); color: #334155; display: block; margin-bottom: 6px; }
.assess__override input { width: 100%; height: 44px; padding: 0 14px; border: 1px solid #e6ecf5; border-radius: 10px; background: #fafcff; font: 400 15px var(--font-body); }
.assess__gap { height: 18px; }
.assess input[type=text] { display: block; width: 100%; margin-top: 12px; height: 44px; padding: 0 14px; border: 1px solid #e6ecf5; border-radius: 10px; background: #fafcff; font: 400 15px var(--font-body); }
.assess .req { color: #dc2626; }

.closer { margin-top: 12px; font-size: 14px; }
.closer summary { cursor: pointer; color: #64748b; list-style: none; display: inline-block; padding: 4px 10px; border-radius: 8px; }
.closer summary::-webkit-details-marker { display: none; }
.closer summary:hover { background: #eef2f7; }
.closer__form { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; align-items: center; }
.closer__form select, .closer__form input { height: 38px; padding: 0 10px; border: 1px solid #e3eaf3; border-radius: 8px; background: #fff; font: 400 14px var(--font-body); }
.closer--inline { margin-top: 0; }
.closer--inline summary { font-size: 18px; line-height: 1; padding: 6px 10px; }
.closer--inline .closer__form { position: absolute; right: 16px; z-index: 5; background: #fff; border: 1px solid #e3eaf3; border-radius: 12px; padding: 12px; box-shadow: 0 8px 24px rgba(15,23,42,.12); }
.qrow { position: relative; }
.qrow__handler { font-size: 13px; color: #92400e; background: #fef3c7; padding: 4px 10px; border-radius: 999px; white-space: nowrap; }

.tsum__amend { margin: 12px 0 0; padding: 10px 14px; list-style: none; background: #fff; border: 1px dashed #93c5fd; border-radius: 10px; font-size: 13px; color: #334155; }
.tsum__amend li + li { margin-top: 4px; }
.tsum__amend span { color: #64748b; }
.tsum__fix { display: inline-block; margin-top: 10px; font-size: 13px; font-weight: 600; color: #3b6fa5; text-decoration: underline; }
.pcard__edit { color: #4a83c3; font-weight: 600; text-decoration: underline; }

.tabpanel { background: #fff; border: 1px solid #e6ecf4; border-radius: 16px; padding: 24px; }
.tabpanel h3 { font: 600 20px var(--font-head); margin-bottom: 14px; }
.tabpanel__sub { font: 600 16px var(--font-head); margin: 26px 0 12px; padding-top: 22px; border-top: 1px solid #edf1f6; }
.dtable { width: 100%; border-collapse: collapse; font-size: 14px; }
.dtable th { text-align: left; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; color: #64748b; padding: 8px 10px; border-bottom: 1px solid #e6ecf4; }
.dtable td { padding: 12px 10px; border-bottom: 1px solid #f0f3f8; vertical-align: top; }
.dtable small { display: block; color: #64748b; margin-top: 2px; }
.tabform .ik__grid { margin-top: 0; }
.reasons { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.reasons__opt { display: flex; gap: 10px; align-items: center; padding: 12px 14px; border: 1px solid #e3eaf3; border-radius: 12px; font-size: 15px; cursor: pointer; }
.reasons__opt:has(input:checked) { border-color: #4a83c3; background: #f0f7ff; }
.edit__h { font: 600 16px var(--font-head); margin: 28px 0 10px; }
.changes { list-style: none; font-size: 14px; color: #334155; }
.changes li { padding: 8px 0; border-bottom: 1px solid #f0f3f8; }
.changes span { display: block; font-size: 12px; color: #64748b; }

.toasts { position: fixed; top: 16px; right: 16px; z-index: 100; display: flex; flex-direction: column; gap: 10px; max-width: 360px; }
.toast { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 16px; border-radius: 12px; font-size: 14px; font-weight: 500; box-shadow: 0 10px 30px rgba(15,23,42,.18); background: #1e293b; color: #fff; }
.toast--urgent { background: #b91c1c; }
.toast--ready { background: #166534; }
.toast button { border: 0; background: none; color: inherit; font-size: 20px; line-height: 1; cursor: pointer; opacity: .8; }

/* Student portal (design drawn at 1.29x; ^N = N design px) */
.pnote { display: flex; align-items: center; gap: ^14; background: #faf1c9; color: #9a5b12; border-radius: ^10; padding: ^19 ^21; font-size: ^18; line-height: 1.4; }
.pnote svg { width: ^22; height: ^22; flex-shrink: 0; }
.securechip { display: inline-flex; align-items: center; gap: ^8; background: #dcf7e6; color: #1f7a4a; border-radius: ^10; padding: ^9 ^16; font: 600 ^16 var(--font-body); letter-spacing: .01em; }
.securechip svg { width: ^18; height: ^18; }
.pprofile { background: #fff; border: 1px solid #e6ecf4; border-radius: ^24; padding: ^31; }
.pprofile__head { display: flex; align-items: center; gap: ^18; padding-bottom: ^26; border-bottom: 1px solid #e6ecf4; flex-wrap: wrap; }
.pprofile__avatar { width: ^62; height: ^62; border-radius: 50%; background: #dcf7e6; color: #46b26f; display: grid; place-items: center; font: 600 ^22 var(--font-head); flex-shrink: 0; }
.pprofile__name { font: 600 ^28/1.2 var(--font-head); color: var(--ink); }
.pprofile__sub { font-size: ^17; color: #475569; margin-top: ^4; }
.pprofile__chip { margin-left: auto; background: #dcf7e6; color: #46b26f; border-radius: 999px; padding: ^8 ^16; font: 600 ^14 var(--font-body); letter-spacing: .02em; }
.pprofile__chip--off { background: #e5e8ef; color: #475569; }
.pfacts { display: grid; grid-template-columns: repeat(4, 1fr); gap: ^34 ^24; margin: ^30 0 0; }
.pfacts dt { font-size: ^14; text-transform: uppercase; letter-spacing: .02em; color: #8a94a8; }
.pfacts dd { margin: ^8 0 0; font: 600 ^17 var(--font-body); color: #1e293b; }
.ptitle { font: 600 ^21 var(--font-head); color: var(--ink); margin-top: ^6; }
.ptitle--in { margin: 0 0 ^18; }
.ptiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: ^27; }
.ptile { background: #fff; border: 1px solid #e6ecf4; border-radius: ^20; padding: ^25; min-height: ^165; }
.ptile__top { display: flex; align-items: center; justify-content: space-between; gap: ^10; }
.ptile__top > span { font: 600 ^17 var(--font-body); text-transform: uppercase; color: #475569; letter-spacing: .01em; }
.pbadge { font: 500 ^15 var(--font-body); font-style: normal; padding: ^5 ^12; border-radius: ^6; background: #dcf5e6; color: #46b26f; white-space: nowrap; }
.pbadge--info { background: #e2f0fc; color: #3a78b5; }
.pbadge--warn { background: #fbf0c8; color: #b45309; }
.ptile__val { font: 700 ^40/1.1 var(--font-head); color: var(--ink); margin-top: ^24; }
.ptile__val small { font: 400 ^17 var(--font-body); color: #9aa3b8; }
.ptile__meta { font-size: ^16; color: #9aa3b8; margin-top: ^14; }
.pvisits { background: #fff; border: 1px solid #e6ecf4; border-radius: ^24; padding: ^31; display: flex; flex-direction: column; gap: ^16; }
.pvisit { display: grid; grid-template-columns: ^225 1fr; gap: ^22; border: 1px solid #e6ecf4; border-radius: ^14; padding: ^20 ^21; background: #fbfcfe; }
.pvisit time { display: block; font: 500 ^19 var(--font-head); color: var(--ink); }
.pvisit small { display: block; margin-top: ^6; color: #9aa3b8; font-size: ^16; }
.pvisit h4 { font: 600 ^18 var(--font-head); color: var(--ink); }
.pvisit p { margin-top: ^6; font-size: ^17; color: #475569; }
.pvisits__more { font-size: 14px; color: #64748b; margin-top: 4px; }
.pvisits__more a { color: #4a83c3; font-weight: 600; }
.soapcard--wide { grid-column: 1 / -1; min-height: 110px; }
.soapcard h4 small { font: 400 12px var(--font-body); color: #9aa3b8; }
.tab__badge { background: #d94b4b; color: #fff; border-radius: 999px; padding: 1px 7px; font-size: 11px; margin-left: 4px; }
.dtable__actions { white-space: nowrap; display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap; }
.tabform input[type=file] { padding: 10px 12px; height: auto; }
@media (max-width: 1180px) { .ptiles { grid-template-columns: repeat(2, 1fr); } .pfacts { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .ptiles, .pfacts { grid-template-columns: 1fr; } .pvisit { grid-template-columns: 1fr; } }

/* System admin (design drawn at 1.29x; ^N = N design px) */
.pend { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: ^27; }
.penditem { display: flex; align-items: center; gap: ^18; flex-wrap: wrap; background: #fff; border: 1px solid #e6ecf4; border-radius: ^18; padding: ^20 ^24; min-height: ^92; }
.penditem__avatar { width: ^52; height: ^52; border-radius: 50%; display: grid; place-items: center; font: 600 ^18 var(--font-head); flex-shrink: 0; text-transform: uppercase; }
.penditem__avatar--blue { background: #e2eef9; color: #4a83c3; }
.penditem__avatar--green { background: #dcf7e6; color: #46b26f; }
.penditem__who { min-width: 0; flex: 1; }
.penditem__who strong { display: block; font: 600 ^18 var(--font-head); color: var(--ink); }
.penditem__who span { display: block; font-size: ^15; color: #475569; margin-top: ^4; }
.penditem__btns { display: flex; gap: ^10; flex-wrap: wrap; }
.penditem__btns form { margin: 0; }
.abtn--deny { background: #fbe1e1; border: 1px solid #efb6b6; color: #d94b4b; }
.abtn--deny:hover { filter: brightness(.96); }

.um__add { margin-left: auto; }
.um__table { margin-top: ^36; border-top: 1px solid #e7ecf3; }
.um__row { display: grid; grid-template-columns: 230fr 275fr 150fr 115fr 190fr 250fr; align-items: center; gap: 10px; min-height: ^89; padding: 0 ^20; border-bottom: 1px solid #e7ecf3; font-size: ^17; color: #475569; }
.um__row > span { min-width: 0; }
.um__row--head { min-height: ^50; background: #fafcff; font: 600 ^15 var(--font-body); color: #475569; text-transform: uppercase; letter-spacing: .01em; }
.um__name { font: 600 ^17 var(--font-head); color: var(--ink); }
.um__name small { display: block; font: 400 ^14 var(--font-body); color: #8a94a8; margin-top: 2px; }
.um__email { overflow-wrap: anywhere; }
.um__actions { display: flex; align-items: center; gap: ^10; flex-wrap: wrap; }
.um__actions form { margin: 0; }
.um__actions .abtn { font-size: 13px; padding: 0 13px; white-space: nowrap; }
.um__you { font-size: 13px; color: #8a94a8; }
.rolebadge, .statusbadge { display: inline-flex; align-items: center; font-style: normal; font: 500 ^14 var(--font-body); padding: ^5 ^13; white-space: nowrap; }
.rolebadge { border-radius: ^6; }
.rolebadge--admin { background: #ece8fb; color: #6d4ad0; }
.rolebadge--staff { background: #e2f0fc; color: #3a78b5; }
.rolebadge--student { background: #dcf5e6; color: #46b26f; }
.rolebadge--other { background: #eef2f7; color: #64748b; }
.statusbadge { border-radius: 999px; }
.statusbadge--active { background: #dcf5e6; color: #46b26f; }
.statusbadge--pending { background: #fbf0c8; color: #d99a1e; }
.statusbadge--inactive { background: #e5e8ef; color: #475569; }
.statusbadge--denied { background: #fbe1e1; color: #d94b4b; }
.um__tools { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; margin-top: 18px; }
.um__tools form { margin: 0; }

.logf { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.logf input, .logf select { height: 40px; padding: 0 12px; border: 1px solid #e3eaf3; border-radius: 10px; background: #fff; font: 400 14px var(--font-body); }
.logf label { font-size: 13px; color: #64748b; display: inline-flex; align-items: center; gap: 6px; }
.logf__check { color: #334155 !important; }
.logf__check input { height: auto; }
.logbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 16px 0 6px; font-size: 14px; color: #64748b; flex-wrap: wrap; }
.logbar__btns { display: flex; gap: 8px; }
.logbar__btns form { margin: 0; }
.logtable td { font-size: 14px; }
.logtable__alert td { background: #fff5f5; }
@media (max-width: 1100px) { .um__row { grid-template-columns: 1fr 1fr; row-gap: 6px; padding-top: 12px; padding-bottom: 12px; } .um__row--head { display: none; } }

/* Admin overview + audit logs */
.astats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.astat { position: relative; background: #fff; border: 1px solid #e8edf4; border-radius: 16px; padding: 18px 20px; min-height: 138px; display: flex; flex-direction: column; }
.astat__label { font: 600 11.5px var(--font-body); text-transform: uppercase; color: #475569; letter-spacing: .01em; padding-right: 48px; }
.astat__icon { position: absolute; top: 16px; right: 16px; width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; }
.astat__icon svg { width: 20px; height: 20px; }
.astat__icon--blue { background: #e2eef9; color: #4a83c3; } .astat__icon--green { background: #dcf7e6; color: #46b26f; }
.astat__icon--yellow { background: #fbf0c8; color: #d99a1e; } .astat__icon--purple { background: #ece8fb; color: #6d4ad0; } .astat__icon--red { background: #fbe1e1; color: #d94b4b; }
.astat__value { font: 700 28px/1.1 var(--font-head); color: var(--ink); margin-top: 14px; }
.astat__sub { font-size: 12px; color: #9aa3b8; margin-top: 4px; }
.astat__foot { margin-top: auto; padding-top: 10px; font-size: 12px; display: flex; gap: 6px; align-items: center; flex-wrap: nowrap; white-space: nowrap; }
.astat__foot--green { color: #46b26f; } .astat__foot--amber { color: #d99a1e; } .astat__foot--red { color: #d94b4b; }
.astat__link { font-weight: 600; text-decoration: underline; }
.astat .dot, .lgf__live .dot { width: 8px; height: 8px; border-radius: 50%; background: #46b26f; display: inline-block; }
.mchip { font: 600 11.5px var(--font-body); font-style: normal; padding: 3px 9px; border-radius: 6px; }
.mchip--blue { background: #e2eef9; color: #3a78b5; } .mchip--green { background: #dcf5e6; color: #46b26f; } .mchip--purple { background: #ece8fb; color: #6d4ad0; }
.lower--even { grid-template-columns: 1fr 1fr; }
.pill-chip--grey { background: #eef2f7; color: #475569; }
.acts { list-style: none; margin: 14px 0 0; }
.acts li { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid #edf1f6; }
.acts li:last-child { border-bottom: 0; }
.acts__dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.acts__dot--purple { background: #6d4ad0; } .acts__dot--green { background: #46b26f; } .acts__dot--red { background: #d94b4b; } .acts__dot--orange { background: #e0a020; }
.acts div { flex: 1; min-width: 0; }
.acts strong { display: block; font: 600 14px var(--font-head); color: var(--ink); }
.acts span { display: block; font-size: 12px; color: #64748b; margin-top: 2px; }
.acts time { font-size: 13px; color: #9aa3b8; white-space: nowrap; }
.alerts { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; }
.alertrow { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; }
.alertrow svg { width: 20px; height: 20px; flex-shrink: 0; }
.alertrow div { flex: 1; min-width: 0; }
.alertrow strong { display: block; font: 600 14.5px var(--font-head); color: var(--ink); }
.alertrow span { display: block; font-size: 12.5px; color: #475569; }
.alertrow time { font-size: 12.5px; color: #64748b; white-space: nowrap; }
.alertrow__level { font: 700 10.5px var(--font-body); font-style: normal; padding: 3px 9px; border-radius: 4px; color: #fff; }
.alertrow--critical { background: #f7dfdf; color: #d94b4b; } .alertrow--critical .alertrow__level { background: #d94b4b; }
.alertrow--warning { background: #faf0c6; color: #d99a1e; } .alertrow--warning .alertrow__level { background: #e0a020; }
.dist__sub { font-size: 14px; color: #475569; margin: 4px 0 18px; }
.dist__bar { display: flex; height: 32px; border-radius: 16px; overflow: hidden; }
.dist__seg { display: flex; align-items: center; padding: 0 16px; color: #fff; font: 600 12.5px var(--font-body); white-space: nowrap; overflow: hidden; }
.dist__seg--blue { background: #4a83c3; } .dist__seg--green { background: #6cbb85; } .dist__seg--purple { background: #7c4ddf; }
.dist__legend { list-style: none; display: flex; gap: 40px; margin-top: 20px; flex-wrap: wrap; }
.dist__legend li { display: flex; gap: 10px; align-items: flex-start; }
.dist__dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 6px; }
.dist__dot--blue { background: #4a83c3; } .dist__dot--green { background: #6cbb85; } .dist__dot--purple { background: #7c4ddf; }
.dist__legend strong { display: block; font: 600 15px var(--font-head); }
.dist__legend span { font-size: 13px; color: #64748b; }

.logtop { display: flex; align-items: center; gap: 12px; }
.logtop form { margin: 0; }
.logtop__export { display: inline-flex; gap: 8px; align-items: center; }
.logfilters { padding: 6px 0 14px; }
.lgf { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.lgf__pill { display: inline-flex; align-items: center; gap: 8px; height: 34px; padding: 0 12px; border: 1px solid #e3eaf3; border-radius: 10px; background: #fff; font: 500 12.5px var(--font-body); color: #334155; }
.lgf__pill svg { width: 16px; height: 16px; }
.lgf__pill select { border: 0; background: none; font: inherit; color: inherit; cursor: pointer; outline: 0; }
.lgf__live { margin-left: auto; font-size: 13px; color: #64748b; display: inline-flex; align-items: center; gap: 8px; }
.lgf__more { flex-basis: 100%; }
.logtop .abtn { height: 34px; font-size: 13px; }
.lgf__more summary { cursor: pointer; color: #4a83c3; font-size: 13px; font-weight: 600; padding: 4px 0; }
.lgf__grid { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-top: 10px; }
.lgf__grid input[type=search], .lgf__grid input[type=date] { height: 38px; padding: 0 12px; border: 1px solid #e3eaf3; border-radius: 10px; font: 400 13.5px var(--font-body); }
.lgf__grid label { font-size: 13px; color: #64748b; display: inline-flex; gap: 6px; align-items: center; }
.lgpanel { padding: 16px 20px 20px; }
.lgrow { display: grid; grid-template-columns: 130fr 220fr 150fr 400fr 130fr; gap: 12px; align-items: center; padding: 10px 8px; border-bottom: 1px solid #edf1f6; font-size: 13px; color: #475569; }
.lgrow--head { background: #fafcff; font: 600 12.5px var(--font-body); text-transform: uppercase; color: #475569; letter-spacing: .01em; border-bottom: 1px solid #e7ecf3; }
.lgrow--alert { background: #fff5f5; }
.lgrow > span { min-width: 0; }
.lg__time small { display: block; font-size: 12px; color: #9aa3b8; }
.lg__user { display: flex; align-items: center; gap: 10px; font: 600 13.5px var(--font-head); color: var(--ink); }
.lg__avatar { width: 20px; height: 20px; border-radius: 50%; background: #4a83c3; flex-shrink: 0; }
.lg__record b { font: 600 13.5px var(--font-head); color: var(--ink); display: block; }
.lg__record small { display: block; font-size: 11.5px; color: #9aa3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lg__ip { font-variant-numeric: tabular-nums; }
.abadge { font-style: normal; font: 500 12px var(--font-body); padding: 3px 10px; border-radius: 6px; white-space: nowrap; display: inline-block; }
.abadge--edit { background: #fbf0c8; color: #d99a1e; } .abadge--view { background: #e2f0fc; color: #3a78b5; } .abadge--create { background: #dcf5e6; color: #46b26f; }
.abadge--login { background: #ece8fb; color: #6d4ad0; } .abadge--fail { background: #fbe1e1; color: #d94b4b; } .abadge--system { background: #e5e8ef; color: #475569; }
@media (max-width: 1180px) { .astats { grid-template-columns: repeat(2, 1fr); } .lower--even { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .lgrow { grid-template-columns: 1fr 1fr; } .lgrow--head { display: none; } .logtop { flex-wrap: wrap; } }
@media (max-width: 600px) { .astats { grid-template-columns: 1fr; } }

@media (max-width: 1180px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .lower { grid-template-columns: 1fr; }
  .banner { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 860px) {
  .app { flex-direction: column; }
  .side { position: static; width: 100%; height: auto; padding: 16px; }
  .side__nav { flex-direction: row; flex-wrap: wrap; margin-top: 16px; gap: 6px; }
  .side__link { width: auto; height: 42px; font-size: 14px; padding: 0 14px; }
  .side__link svg { width: 18px; height: 18px; }
  .side__signout { margin-top: 0; }
  .side__footer { margin-top: 12px; padding-top: 12px; }
  .usercard { height: 64px; }
  .usercard__avatar { width: 42px; height: 42px; font-size: 14px; }
  .usercard__name { font-size: 15px; } .usercard__role { font-size: 12px; }
  .topbar { height: auto; padding: 16px; flex-wrap: wrap; }
  .content { padding: 16px; }
  .banner__actions { flex-wrap: wrap; }
  .abtn { height: 44px; font-size: 14px; }
  .qrow { height: auto; flex-wrap: wrap; padding: 12px; }
  .qrow__right { margin-left: 0; width: 100%; flex-wrap: wrap; gap: 10px; }
  .stats { grid-template-columns: 1fr; }
}
'''
css = re.sub(r"@(\d+(?:\.\d+)?)", u, css)
K2 = 1.26
def u2(m):
    v = float(m.group(1))/K2
    return (f"{v:.2f}".rstrip("0").rstrip(".")) + "px"
css = re.sub(r"~(\d+(?:\.\d+)?)", u2, css)
K3 = 1.29
def u3(m):
    v = float(m.group(1))/K3
    return (f"{v:.2f}".rstrip("0").rstrip(".")) + "px"
css = re.sub(r"\^(\d+(?:\.\d+)?)", u3, css)
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
(ROOT / "static/css/dashboard.css").write_text(css)
print(len(css))
