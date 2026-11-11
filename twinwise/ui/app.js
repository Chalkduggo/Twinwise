/* Twinwise review screen. Plain JavaScript, no build step, talks only to the local server. */
(() => {
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ICONS = {
  up: '<path d="M12 16V4M6 10l6-6 6 6M4 20h16"/>',
  grid: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/>',
  book: '<path d="M4 4h10a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4z"/>',
  shield: '<path d="M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  down: '<path d="M12 4v12M6 10l6 6 6-6M4 20h16"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  next: '<path d="M9 6l6 6-6 6"/>',
  warn: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
};
const ic = (n, s = 18, c = "currentColor", w = 1.8) =>
  `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${ICONS[n]}</svg>`;

const S = {
  page: "twin", step: "upload", job: null, file: 0, sheet: 0, view: "plan", grid: null,
  sel: null, tab: "summary", verify: null, exp: null, busy: false, lib: null, status: null,
  restore: { key: null, keyName: "", text: "", result: null }, preview: null,
};

async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.json !== undefined) {
    o.method = o.method || "POST";
    o.headers = { "Content-Type": "application/json" };
    o.body = JSON.stringify(o.json);
    delete o.json;
  }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch { /* empty */ }
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}

function toast(msg, err = false) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), err ? 6500 : 3200);
}

/* ---------------- navigation ---------------- */
function navTo(page) {
  location.hash = "#/" + page;
}
window.addEventListener("hashchange", route);
function route() {
  const p = (location.hash.replace("#/", "") || "twin").split("?")[0];
  S.page = ["twin", "templates", "names", "safe", "restore", "history"].includes(p) ? p : "twin";
  if (S.page !== "twin" || !S.lib) loadLib();
  render();
}

async function loadLib() {
  try {
    S.lib = await api("/api/library");
    renderSide();
    if (S.page !== "twin") render();
  } catch (e) { toast(e.message, true); }
}

function renderSide() {
  const L = S.lib || { templates: [], names: [], safe_words: [], history: [] };
  const items = [
    ["twin", "up", "Create a twin"],
    ["templates", "grid", "Templates", L.templates.length],
    ["names", "book", "Name library", L.names.length],
    ["safe", "shield", "Safe words", L.safe_words.length],
  ];
  const items2 = [["restore", "undo", "Restore AI answer"], ["history", "clock", "History", L.history.length]];
  const ni = (x) => `<div class="ni ${S.page === x[0] ? "on" : ""}" data-nav="${x[0]}">${ic(x[1])}${x[2]}${x[3] !== undefined ? `<span class="c">${x[3]}</span>` : ""}</div>`;
  const month = new Date().toISOString().slice(0, 7);
  const thisMonth = L.history.filter((h) => (h.time || "").startsWith(month));
  const nfiles = thisMonth.reduce((a, h) => a + (h.files || []).length, 0);
  $("#side").innerHTML = `<div class="sec">Workspace</div>${items.map(ni).join("")}
    <div class="sec">After the AI</div>${items2.map(ni).join("")}
    <div class="bot"><b>This month</b>${nfiles} twin${nfiles === 1 ? "" : "s"} created · ${thisMonth.reduce((a, h) => a + (h.files || []).reduce((b, f) => b + (f.leaks || 0), 0), 0)} leaks<br><span style="color:var(--faint)" title="${esc(L.home || "")}">Library saved on this computer</span></div>`;
}
document.addEventListener("click", (e) => {
  const n = e.target.closest("[data-nav]");
  if (n) navTo(n.dataset.nav);
});

/* ---------------- render ---------------- */
function render() {
  renderSide();
  const m = $("#main");
  const pages = { twin: renderTwin, templates: renderTemplates, names: renderNames, safe: renderSafe, restore: renderRestore, history: renderHistory };
  m.innerHTML = pages[S.page]();
  afterRender();
}

function stepper(cur) {
  const s = ["Upload", "Review", "Verify", "Export"];
  return `<div class="steps">${s.map((x, i) => `<div class="st ${i < cur ? "done" : i === cur ? "cur" : ""}"><span class="d">${i < cur ? ic("check", 12, "#fff", 3) : i + 1}</span>${x}${i < s.length - 1 ? '<span class="ln"></span>' : ""}</div>`).join("")}</div>`;
}

function renderTwin() {
  if (S.step === "upload" || !S.job) return renderUpload();
  if (S.step === "review") return renderReview();
  if (S.step === "verify") return renderVerify();
  if (S.step === "export") return renderExport();
  return "";
}

function renderUpload() {
  return `<div class="crumb">Workspace <span>/</span> <b>Create a twin</b></div>
  <div class="ph"><h1>Create a data twin</h1></div>
  <div class="sub">A twin has the same layout as your file, with names, IDs and numbers replaced — safe to give to any AI tool.</div>
  ${stepper(0)}
  <label class="drop" id="drop">
    <input type="file" id="fileIn" multiple accept=".xlsx,.xlsm,.csv,.tsv,.zip" hidden>
    ${S.busy ? `<div class="spinner"></div><div style="font-size:14px;color:var(--muted)">Reading your files…</div>` : `
    <div class="ic">${ic("up", 20, "#475467")}</div>
    <div style="font-size:14px"><b style="color:var(--pri)">Click to choose files</b> <span style="color:var(--muted)">or drag and drop</span></div>
    <div style="font-size:12.5px;color:var(--faint)">Excel (.xlsx), CSV or a ZIP of them · files never leave this computer</div>`}
  </label>
  <div class="points">
    <div class="card point"><b>1 · Automatic first pass</b><span>Finds numbers, names, IDs, places and totals. Reuses what it learned from your earlier files.</span></div>
    <div class="card point"><b>2 · You review</b><span>Colours show the plan. Click any cell or column to change it. Your decisions are remembered.</span></div>
    <div class="card point"><b>3 · Safety check, then export</b><span>Every replaced value is searched for in the twin before you can share it.</span></div>
  </div>`;
}

function reviewCount() {
  return S.job ? (S.job.counts.review || 0) : 0;
}

function renderReview() {
  const job = S.job, f = job.files[S.file], sh = f.sheets[S.sheet];
  const rc = reviewCount();
  return `<div class="crumb">Workspace <span>/</span> Create a twin <span>/</span> <b>Review</b></div>
  <div class="ph"><h1><span class="t" title="${esc(f.name)}">${esc(f.name)}</span>${rc ? `<span class="chip r">${rc} to review</span>` : `<span class="chip g">Nothing to review</span>`}</h1>
    <div class="actions"><div class="toggle" id="viewT">${["plan", "original", "twin"].map((v) => `<button data-view="${v}" class="${S.view === v ? "on" : ""}">${v === "plan" ? "Plan" : v === "original" ? "Original" : "Twin"}</button>`).join("")}</div>
    <button class="btn" data-act="restart">Start over</button><button class="btn p" data-act="verify">Continue</button></div></div>
  ${stepper(1)}
  ${job.files.length > 1 ? `<div class="tabs-row">${job.files.map((x, i) => `<button data-file="${i}" class="${i === S.file ? "on" : ""}">${esc(x.name)} ${x.counts.review ? `<span class="chip r" style="margin-left:6px">${x.counts.review}</span>` : ""}</button>`).join("")}</div>` : ""}
  <div class="toolbar">
    <div class="leg"><span><i style="background:var(--num-mk)"></i>Number · changed</span><span><i style="background:var(--name-mk)"></i>Name / ID · replaced</span><span><i style="background:var(--date-mk)"></i>Date · kept</span><span><i style="background:#fff;box-shadow:inset 0 0 0 1px #D0D5DD"></i>Text · kept</span><span><i style="background:var(--ask-mk)"></i>Needs your decision</span></div>
    <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
      ${f.sheets.length > 1 ? `<div class="sheettabs">${f.sheets.map((s, i) => `<button data-sheet="${i}" class="${i === S.sheet ? "on" : ""}">${esc(s.name)}${s.hidden ? " (hidden)" : ""}</button>`).join("")}</div>` : ""}
      ${rc ? `<button class="btn sm" data-act="nextReview">${ic("next", 14)}Next to review</button>` : ""}
    </div>
  </div>
  <div class="work">
    <div class="card gridwrap" id="gridwrap">${S.grid ? gridHTML() : `<div class="loading"><div class="spinner"></div>Loading sheet…</div>`}</div>
    <div class="card insp">${inspectorHTML()}</div>
  </div>
  <div class="status"><span>${esc(sh.name)} · <b>${sh.rows}</b> rows · ${sh.cols} columns</span>
    <span style="color:var(--num-fg)"><b style="color:inherit">${f.counts.number || 0}</b> numbers</span>
    <span style="color:var(--name-fg)"><b style="color:inherit">${(f.counts.name || 0) + (f.counts.id || 0)}</b> names & IDs</span>
    <span style="color:var(--ask-fg)"><b style="color:inherit">${f.counts.review || 0}</b> to review</span>
    <span style="margin-left:auto">${f.template_found ? `Template: <b>${esc(f.template)}</b> · ${Math.round(f.template_score * 100)}% match` : "New layout · saved as a template when you export"}</span>
    <span>Mode: <b>${esc(job.settings.mode)}</b></span></div>`;
}

const ROLE_COLOR = { measure: "var(--num-mk)", count: "var(--num-mk)", price: "var(--num-mk)", percent: "var(--num-mk)", id: "var(--name-mk)", entity: "var(--name-mk)", date: "var(--date-mk)", text: "#D0D5DD", empty: "transparent" };
const NUM_STATUS = new Set(["number"]);

function gridHTML() {
  const g = S.grid;
  const selCol = S.sel && S.sel.type === "col" ? S.sel.c : null;
  const selCell = S.sel && S.sel.type === "cell" ? S.sel : null;
  const cols = g.columns;
  // horizontal merges
  const covered = new Set(), span = {};
  for (const [r1, c1, r2, c2] of g.merged || []) {
    if (r1 === r2 && c2 > c1) { span[`${r1},${c1}`] = c2 - c1 + 1; for (let c = c1 + 1; c <= c2; c++) covered.add(`${r1},${c}`); }
  }
  let h = `<table class="g v-${S.view}"><thead><tr><th class="rn"></th>${cols.map((c) => `<th data-col="${c.index}" class="${selCol === c.index ? "colsel" : ""}" title="${esc(c.header)}">${c.letter}</th>`).join("")}</tr>
    <tr class="ty"><th class="rn"></th>${cols.map((c) => `<th data-col="${c.index}" class="${selCol === c.index ? "colsel" : ""}">${c.role === "empty" ? "" : `<span class="tt"><i style="background:${c.action === "keep" ? "#D0D5DD" : ROLE_COLOR[c.role] || "#D0D5DD"}"></i>${esc(c.label)}</span>`}</th>`).join("")}</tr></thead><tbody>`;
  for (const row of g.rows) {
    const map = {};
    for (const c of row.cells) map[c.c] = c;
    h += `<tr class="${row.header ? "hdr" : ""} ${row.total ? "tot" : ""}"><th class="rn">${row.r}</th>`;
    for (const col of cols) {
      const k = `${row.r},${col.index}`;
      if (covered.has(k)) continue;
      const c = map[col.index];
      const sp = span[k] ? ` colspan="${span[k]}"` : "";
      if (!c) { h += `<td${sp} data-r="${row.r}" data-c="${col.index}" class="${selCol === col.index ? "colsel" : ""}"></td>`; continue; }
      const val = S.view === "original" ? c.o : (S.view === "twin" ? c.t : c.o);
      const cls = [S.view === "original" ? "" : c.s, NUM_STATUS.has(c.s) || /^[\d$€£₹(.,%-]+$/.test(val) ? "r" : "",
        selCell && selCell.r === row.r && selCell.c === col.index ? "selc" : "", selCol === col.index ? "colsel" : ""].join(" ");
      const tip = c.s === "keep" ? "Kept as is" : `${c.o} → ${c.t}${c.n ? " · " + c.n : ""}`;
      h += `<td${sp} data-r="${row.r}" data-c="${col.index}" class="${cls}" title="${esc(tip)}">${esc(val)}</td>`;
    }
    h += "</tr>";
  }
  h += "</tbody></table>";
  if (g.max_row > g.offset + g.rows.length) h += `<div style="padding:12px 16px;font-size:12.5px;color:var(--muted)">Showing the first ${g.rows.length} of ${g.max_row} rows. All rows are included in the twin.</div>`;
  return h;
}

function cellData(r, c) {
  const row = S.grid && S.grid.rows.find((x) => x.r === r);
  return row ? row.cells.find((x) => x.c === c) : null;
}
function colLetter(c) { return S.grid.columns[c - 1].letter; }

function inspectorHTML() {
  const tabs = ["summary", "cell", "column"];
  const head = `<div class="tabs">${tabs.map((t) => `<button data-tab="${t}" class="${S.tab === t ? "on" : ""}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div>`;
  let body = "";
  if (S.tab === "cell") body = cellPanel();
  else if (S.tab === "column") body = columnPanel();
  else body = summaryPanel();
  return head + `<div class="body">${body}</div>`;
}

function summaryPanel() {
  const f = S.job.files[S.file], c = f.counts, set = S.job.settings;
  const rows = [["Numbers changed", c.number || 0, "var(--num-mk)"], ["Names & IDs replaced", (c.name || 0) + (c.id || 0), "var(--name-mk)"], ["Dates kept", c.date || 0, "var(--date-mk)"], ["Text kept", c.keep || 0, "#D0D5DD"], ["Needs your decision", c.review || 0, "var(--ask-mk)"]];
  const modes = [["consistent", "Consistent (recommended)", "Each column scaled by a hidden factor; totals and formulas recalculated so the twin adds up."], ["scale", "One hidden factor", "Every amount multiplied by the same factor. Ratios stay exact."], ["random", "Random", "Each number changed independently. Safest, but totals will not add up."]];
  return `<div class="lbl">This file</div>${rows.map((x) => `<div class="kv"><span><i class="dot" style="background:${x[2]}"></i>${x[0]}</span><b>${x[1]}</b></div>`).join("")}
  <div class="field"><label>Template name</label><input class="inp" id="tplName" value="${esc(f.template)}" placeholder="e.g. Partner PPV report"></div>
  <div class="note" style="margin-top:8px">${f.template_found ? `Recognised from a saved template (${Math.round(f.template_score * 100)}% match). Your column rules were applied.` : "On export, your column decisions are saved under this name so next month's file is recognised."}</div>
  <div class="field"><label>How numbers change</label>${modes.map((m) => `<button class="opt ${set.mode === m[0] ? "on" : ""}" data-mode="${m[0]}"><span class="rad"></span><span><b>${m[1]}</b><small>${m[2]}</small></span></button>`).join("")}</div>
  <label class="switch"><input type="checkbox" id="pp" ${set.price_points ? "checked" : ""}> Round prices to real price points (3.64 → 3.99)</label>
  <label class="switch"><input type="checkbox" id="stable" ${set.stable_factors ? "checked" : ""}> Keep the same hidden factors every month (trends stay comparable)</label>`;
}

function cellPanel() {
  if (!S.sel || S.sel.type !== "cell") return `<div class="empty" style="padding:24px 8px">Click any cell in the sheet to see what happens to it and change it.</div>`;
  const d = cellData(S.sel.r, S.sel.c);
  const ref = colLetter(S.sel.c) + S.sel.r;
  if (!d) return `<div class="lbl">Cell ${ref}</div><div class="note">This cell is empty.</div>`;
  const statusText = { keep: "Kept as is", number: "Number — changed", name: "Name — replaced", id: "ID — replaced", date: "Date — kept", review: "New text — masked, please confirm", formula: "Formula — kept (Excel recalculates it)" }[d.s] || d.s;
  const decided = d.d || "auto";
  const canDecide = !["number", "date", "formula"].includes(d.s) || d.s === "keep";
  return `<div class="lbl">Cell ${ref}</div>
  <div style="margin-top:8px"><span class="chip ${d.s === "review" ? "r" : d.s === "keep" ? "n" : d.s === "number" ? "b" : "w"}">${statusText}</span></div>
  <div class="field"><label>Original</label><div class="valbox real">${esc(d.o)}</div></div>
  <div class="field"><label>In the twin</label><div class="valbox fake">${esc(d.t)}</div></div>
  ${d.n ? `<div class="note">${esc(d.n)}</div>` : ""}
  ${d.s === "number" ? `<div class="note b">Numbers are handled by column. Use the Column tab to keep or change how this column is treated.</div>` : ""}
  ${canDecide && d.s !== "number" ? `<div class="field"><label>Your decision</label>
    <button class="opt ${!decided || decided === "auto" ? "on" : ""}" data-cell="auto"><span class="rad"></span><span><b>Automatic</b><small>Replace the names and codes Twinwise found</small></span></button>
    <button class="opt ${decided === "keep" ? "on" : ""}" data-cell="keep"><span class="rad"></span><span><b>Keep as is</b><small>Adds the new words to your safe-word list</small></span></button>
    <button class="opt ${decided === "mask_all" ? "on" : ""}" data-cell="mask_all"><span class="rad"></span><span><b>Replace the whole cell</b><small>One label for the entire text</small></span></button></div>` : ""}`;
}

function columnPanel() {
  if (!S.sel || S.sel.type !== "col") return `<div class="empty" style="padding:24px 8px">Click a column letter (A, B, C…) to change how the whole column is treated.</div>`;
  const col = S.grid.columns[S.sel.c - 1];
  const roles = [["auto", "Automatic"], ["measure", "Number — scale"], ["count", "Count — scale, whole numbers"], ["price", "Price — scale"], ["percent", "Percent — gentle change"], ["id", "ID / code — replace"], ["entity", "Names — replace"], ["date", "Date — keep"], ["text", "Text — check words"]];
  const cats = ["Partner", "Vendor", "Company", "Channel", "Title", "Region", "Person", "Email", "Address", "Name"];
  return `<div class="lbl">Column ${col.letter}${col.header ? " · " + esc(col.header) : ""}</div>
  <div style="margin-top:8px"><span class="chip ${col.action === "keep" ? "n" : "b"}">${esc(col.label)}</span>${col.derived ? ' <span class="chip g">Formula found</span>' : ""}</div>
  <div class="field"><label>What this column holds</label><select class="sel" id="colRole" style="width:100%">${roles.map((r) => `<option value="${r[0]}">${r[1]}</option>`).join("")}</select></div>
  <div class="field" id="catField" style="${col.role === "entity" ? "" : "display:none"}"><label>Name type (used for labels)</label><select class="sel" id="colCat" style="width:100%">${cats.map((c) => `<option ${col.category === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
  <div class="field"><label>Action</label>
    <button class="opt ${col.action !== "keep" ? "on" : ""}" data-colact="auto"><span class="rad"></span><span><b>Mask this column</b><small>Recommended</small></span></button>
    <button class="opt ${col.action === "keep" ? "on" : ""}" data-colact="keep"><span class="rad"></span><span><b>Keep original values</b><small>Only for data that is public or not sensitive</small></span></button></div>
  ${col.role === "price" ? `<label class="switch"><input type="checkbox" id="colPP" ${col.price_points ? "checked" : ""}> Round to real price points</label>` : ""}
  ${col.derived ? `<div class="note b">Twinwise found that this column is calculated from other columns, so it is recalculated in the twin.</div>` : ""}
  <div class="note">Column rules are saved in the template, so next month's file gets the same treatment.</div>`;
}

function renderVerify() {
  const v = S.verify;
  if (!v) return `<div class="crumb">Workspace <span>/</span> Create a twin <span>/</span> <b>Verify</b></div><div class="ph"><h1>Safety check</h1></div>${stepper(2)}<div class="card" style="margin-top:16px"><div class="loading"><div class="spinner"></div>Building the twin and searching it for every original value…</div></div>`;
  const allOk = v.all_clear;
  return `<div class="crumb">Workspace <span>/</span> Create a twin <span>/</span> <b>Verify</b></div>
  <div class="ph"><h1>Safety check ${allOk ? '<span class="chip g">0 leaks found</span>' : '<span class="chip r">Leaks found</span>'}</h1>
  <div class="actions"><button class="btn" data-act="back">Back to review</button><button class="btn p" data-act="export" ${allOk ? "" : "disabled"}>${ic("down", 16, "#fff", 2)}Export twin</button></div></div>
  ${stepper(2)}
  ${v.files.map((f) => {
    const L = f.leak, R = f.risk;
    return `<div class="card" style="margin-top:16px"><div class="row" style="border-bottom:1px solid var(--line)"><span class="fi x">${f.twin_name.split(".").pop().toUpperCase()}</span><div style="flex:1;min-width:0"><div style="font-weight:600">${esc(f.original)}</div><div style="font-size:12.5px;color:var(--muted)">becomes <b style="color:var(--ink2)">${esc(f.twin_name)}</b></div></div><span class="chip ${R.level === "low" ? "g" : R.level === "medium" ? "w" : "r"}">Re-identification risk: ${R.level}</span></div>
    <div class="chk"><div style="display:flex;gap:12px;align-items:center"><span class="tk ${L.ok ? "ok" : "bad"}">${ic(L.ok ? "check" : "x", 12, "#fff", 3)}</span>Searched the twin for all ${L.checked_values.toLocaleString()} replaced values (cells, sheet names, file name, properties)</div><span class="chip ${L.ok ? "g" : "r"}">${L.ok ? "0 found" : L.leak_count + " found"}</span></div>
    ${L.leaks.slice(0, 8).map((x) => `<div class="chk" style="color:var(--ask-fg)"><span>${esc(x.where)}: ${esc(x.value)}</span><span>${esc(x.type)}</span></div>`).join("")}
    <div class="chk"><div style="display:flex;gap:12px;align-items:center"><span class="tk ok">${ic("check", 12, "#fff", 3)}</span>Comments, headers/footers and document author removed</div><span class="chip g">Clean</span></div>
    ${R.warnings.map((w) => `<div class="chk"><div style="display:flex;gap:12px;align-items:flex-start"><span class="tk w" style="margin-top:2px">${ic("warn", 11, "#fff", 2.4)}</span><div><div style="font-weight:600">${esc(w.title)}</div><div style="font-size:12.5px;color:var(--muted);margin-top:2px;line-height:1.5">${esc(w.detail)}</div></div></div><span class="chip ${w.level === "low" ? "n" : "w"}">${w.level}</span></div>`).join("")}
    </div>`;
  }).join("")}
  <div style="height:20px"></div>`;
}

function renderExport() {
  const e = S.exp;
  if (!e) return `<div class="crumb">Workspace <span>/</span> Create a twin <span>/</span> <b>Export</b></div><div class="ph"><h1>Exporting…</h1></div>${stepper(3)}<div class="card" style="margin-top:16px"><div class="loading"><div class="spinner"></div>Saving your twin…</div></div>`;
  const pv = S.preview;
  return `<div class="crumb">Workspace <span>/</span> Create a twin <span>/</span> <b>Export</b></div>
  <div class="ph"><h1>Twin ready <span class="chip g">Exported</span></h1><div class="actions"><button class="btn" data-act="openFolder">${ic("folder", 16)}Open folder</button><button class="btn p" data-act="restart">Create another twin</button></div></div>
  ${stepper(4)}
  <div class="cols2">
    <div class="card" style="flex:1.25;min-width:0;overflow:hidden"><div style="padding:12px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:10px"><span class="lbl">Exactly what the AI will read</span>
      ${S.job.files.length > 1 ? `<select class="sel" id="pvFile">${S.job.files.map((f, i) => `<option value="${i}" ${pv && pv.i === i ? "selected" : ""}>${esc(f.twin_name)}</option>`).join("")}</select>` : `<button class="btn sm" data-act="copyPreview">${ic("copy", 14)}Copy</button>`}</div>
      <div class="preview" id="pvText">${pv ? esc(pv.text) : "Loading…"}</div></div>
    <div style="flex:1;min-width:300px">
      <div class="card"><div style="padding:12px 16px;border-bottom:1px solid var(--line)"><span class="lbl">Saved to</span><div class="mono" style="font-size:12px;margin-top:6px;color:var(--ink2);word-break:break-all">${esc(e.out_dir)}</div></div>
      ${e.downloads.map((d) => `<div class="row"><span class="fi ${d.kind === "key" ? "k" : "x"}">${d.kind === "key" ? "KEY" : d.name.split(".").pop().toUpperCase()}</span><div style="flex:1;min-width:0"><div style="font-size:13.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(d.name)}</div><div style="font-size:12px;color:var(--muted);margin-top:2px">${d.kind === "key" ? "Private · stays on this computer · turns AI answers back into real names" : "Safe to share with any AI tool"}</div></div><a class="btn sm" href="/api/download?path=${encodeURIComponent(d.path)}">${ic("down", 14)}Download</a></div>`).join("")}
      </div>
      <div class="note b" style="margin-top:14px">Next: upload the twin to your AI tool. When you get an answer, paste it into <a href="#/restore">Restore AI answer</a> with the key file to see real names again.</div>
      <div class="note" style="margin-top:10px">Your decisions were saved. Next time a file with this layout arrives, Twinwise will recognise it.</div>
    </div>
  </div><div style="height:20px"></div>`;
}

/* ---------------- library pages ---------------- */
function pageHead(title, sub, crumb) {
  return `<div class="crumb">${crumb || "Workspace"} <span>/</span> <b>${title}</b></div><div class="ph"><h1>${title}</h1></div><div class="sub">${sub}</div>`;
}
function renderTemplates() {
  const L = S.lib;
  if (!L) return `<div class="loading"><div class="spinner"></div></div>`;
  return pageHead("Templates", "A template remembers a file layout and your column decisions. Matching files are recognised automatically.") +
    `<div class="card" style="margin-top:16px">${L.templates.length ? `<table class="list"><tr><th>Name</th><th>Columns recognised</th><th>Your column rules</th><th>Mode</th><th>Version</th><th>Updated</th><th></th></tr>
    ${L.templates.map((t) => `<tr><td style="font-weight:600;color:var(--ink)">${esc(t.name)}</td><td>${(t.fingerprint || []).length}</td><td>${Object.keys(t.columns || {}).length}</td><td>${esc((t.settings || {}).mode || "")}</td><td>v${t.version}</td><td>${esc((t.updated || "").replace("T", " "))}</td><td style="text-align:right"><button class="btn sm danger" data-deltpl="${esc(t._file)}">Delete</button></td></tr>`).join("")}</table>` :
    `<div class="empty">No templates yet. Export your first twin and its layout is saved here.</div>`}</div>`;
}
function renderNames() {
  const L = S.lib;
  if (!L) return `<div class="loading"><div class="spinner"></div></div>`;
  return pageHead("Name library", "Every real name and its fake label. The same name always gets the same label, across all files.") +
    `<div class="card" style="margin-top:16px;padding:14px 16px;display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div style="flex:2;min-width:180px"><label class="lbl">Real name</label><input class="inp" id="nmReal" placeholder="e.g. Northwind Cable" style="margin-top:6px"></div>
      <div style="flex:1;min-width:140px"><label class="lbl">Type</label><select class="sel" id="nmCat" style="margin-top:6px;width:100%">${["Partner", "Vendor", "Company", "Channel", "Title", "Region", "Person", "Name"].map((c) => `<option>${c}</option>`).join("")}</select></div>
      <div style="flex:1.5;min-width:160px"><label class="lbl">Fake label (optional)</label><input class="inp" id="nmFake" placeholder="auto" style="margin-top:6px"></div>
      <button class="btn p" data-act="addName">Add name</button></div>
    <div class="card" style="margin-top:16px">${L.names.length ? `<table class="list"><tr><th>Real name</th><th>Type</th><th>Fake label</th><th></th></tr>
    ${L.names.map((n) => `<tr><td style="color:var(--ink)">${esc(n.real)}</td><td><span class="chip n">${esc(n.category)}</span></td><td><b style="color:var(--pri-ink)">${esc(n.fake)}</b></td><td style="text-align:right"><button class="btn sm ghost" data-safe-name="${esc(n.real)}">Mark safe</button><button class="btn sm danger" data-delname="${esc(n.real)}">Remove</button></td></tr>`).join("")}</table>` :
    `<div class="empty">No names yet. Names are added when you export a twin, or you can add them above.</div>`}</div>`;
}
function renderSafe() {
  const L = S.lib;
  if (!L) return `<div class="loading"><div class="spinner"></div></div>`;
  return pageHead("Safe words", "Words and phrases that are never masked — for example column headings or public terms used in your reports.") +
    `<div class="card" style="margin-top:16px;padding:14px 16px;display:flex;gap:10px"><input class="inp" id="safeIn" placeholder="Add a word or phrase, e.g. Bad Debt"><button class="btn p" data-act="addSafe">Add</button></div>
    <div class="card" style="margin-top:16px">${L.safe_words.length ? `<div class="wordchips">${L.safe_words.map((w) => `<span>${esc(w)}<button title="Remove" data-unsafe="${esc(w)}">×</button></span>`).join("")}</div>` :
    `<div class="empty">Your own safe words appear here. Twinwise already knows common business words like Revenue, Total and Subscribers.</div>`}</div>`;
}
function renderHistory() {
  const L = S.lib;
  if (!L) return `<div class="loading"><div class="spinner"></div></div>`;
  return pageHead("History", "A local record of every twin you exported. Stored only on this computer.") +
    `<div class="card" style="margin-top:16px">${L.history.length ? `<table class="list"><tr><th>When</th><th>Original</th><th>Twin</th><th>Template</th><th>Mode</th><th>Leaks</th></tr>
    ${L.history.flatMap((h) => (h.files || []).map((f) => `<tr><td>${esc((h.time || "").replace("T", " "))}</td><td style="color:var(--ink)">${esc(f.original)}</td><td>${esc(f.twin)}</td><td>${esc(f.template)}</td><td>${esc(h.mode)}</td><td><span class="chip ${f.leaks ? "r" : "g"}">${f.leaks || 0}</span></td></tr>`)).join("")}</table>` :
    `<div class="empty">Nothing exported yet.</div>`}</div>`;
}
function renderRestore() {
  const R = S.restore;
  return pageHead("Restore AI answer", "Paste what the AI said about the twin. With the key file, Twinwise swaps the fake names and numbers back to the real ones — on this computer.", "After the AI") +
  `<div class="cols2"><div class="card" style="flex:1;padding:16px;min-width:0">
    <div class="field" style="margin-top:0"><label>1 · Key file</label><label class="btn" style="width:100%">${ic("up", 16)}${R.keyName ? esc(R.keyName) : "Choose twin-key_….json"}<input type="file" id="keyIn" accept=".json" hidden></label></div>
    <div class="field"><label>2 · AI answer</label><textarea class="inp" id="rsText" rows="12" placeholder="e.g. Channel A had 1,204 buys in Region 3, up 8% on last month…">${esc(R.text)}</textarea></div>
    <div style="margin-top:12px;display:flex;justify-content:flex-end"><button class="btn p" data-act="doRestore">Restore real names</button></div></div>
  <div class="card" style="flex:1;min-width:0;overflow:hidden"><div style="padding:12px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center"><span class="lbl">Result</span>${R.result ? `<button class="btn sm" data-act="copyRestore">${ic("copy", 14)}Copy</button>` : ""}</div>
    ${R.result ? `<div class="preview" style="white-space:pre-wrap;font-family:var(--font);font-size:13.5px">${esc(R.result.text)}</div>
      <div style="padding:12px 16px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted);line-height:1.6">${R.result.replaced.length} values restored.${R.result.note ? " " + esc(R.result.note) : ""}</div>` :
    `<div class="empty">The restored answer appears here.</div>`}</div></div>`;
}

/* ---------------- events ---------------- */
function afterRender() {
  const drop = $("#drop");
  if (drop) {
    const fi = $("#fileIn");
    fi.addEventListener("change", () => fi.files.length && upload(fi.files));
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => e.dataTransfer.files.length && upload(e.dataTransfer.files));
  }
  const role = $("#colRole");
  if (role) {
    const col = S.grid.columns[S.sel.c - 1];
    role.value = col.override_role || "auto";
    role.addEventListener("change", () => { const r = role.value; setColumn({ role: r, category: r === "entity" ? ($("#colCat") ? $("#colCat").value : "Name") : null }); });
  }
  const cat = $("#colCat");
  if (cat) cat.addEventListener("change", () => setColumn({ role: "entity", category: cat.value }));
  const pp = $("#pp"); if (pp) pp.addEventListener("change", () => setSettings({ price_points: pp.checked }));
  const stb = $("#stable"); if (stb) stb.addEventListener("change", () => setSettings({ stable_factors: stb.checked }));
  const cpp = $("#colPP"); if (cpp) cpp.addEventListener("change", () => setColumn({ price_points: cpp.checked }));
  const tn = $("#tplName"); if (tn) tn.addEventListener("change", async () => { S.job = await api(`/api/jobs/${S.job.id}/template`, { json: { file: S.file, name: tn.value } }); toast("Template name saved"); });
  const pf = $("#pvFile"); if (pf) pf.addEventListener("change", () => loadPreview(+pf.value));
  const keyIn = $("#keyIn");
  if (keyIn) keyIn.addEventListener("change", async () => {
    const f = keyIn.files[0]; if (!f) return;
    try { S.restore.key = JSON.parse(await f.text()); S.restore.keyName = f.name; render(); } catch { toast("That file is not a Twinwise key.", true); }
  });
  const rt = $("#rsText"); if (rt) rt.addEventListener("input", () => { S.restore.text = rt.value; });
  const gw = $("#gridwrap"); if (gw && S._scroll) { gw.scrollTop = S._scroll[0]; gw.scrollLeft = S._scroll[1]; }
}

document.addEventListener("click", async (e) => {
  const t = e.target.closest("button, td, th, a");
  if (!t) return;
  const ds = t.dataset;
  const gw = $("#gridwrap");
  if (gw) S._scroll = [gw.scrollTop, gw.scrollLeft];
  try {
    if (ds.view) { S.view = ds.view; render(); }
    else if (ds.file !== undefined && t.tagName === "BUTTON") { S.file = +ds.file; S.sheet = 0; S.sel = null; S._scroll = null; await loadGrid(); }
    else if (ds.sheet !== undefined && t.tagName === "BUTTON") { S.sheet = +ds.sheet; S.sel = null; S._scroll = null; await loadGrid(); }
    else if (ds.tab) { S.tab = ds.tab; render(); }
    else if (t.tagName === "TD" && ds.r) { S.sel = { type: "cell", r: +ds.r, c: +ds.c }; S.tab = "cell"; render(); }
    else if (t.tagName === "TH" && ds.col) { S.sel = { type: "col", c: +ds.col }; S.tab = "column"; render(); }
    else if (ds.cell) {
      const ref = colLetter(S.sel.c) + S.sel.r;
      S.job = await api(`/api/jobs/${S.job.id}/cell`, { json: { file: S.file, sheet: S.sheet, ref, decision: ds.cell } });
      await loadGrid(true);
      toast(ds.cell === "keep" ? "Kept. New words added to your safe-word list on export." : ds.cell === "mask_all" ? "Whole cell will be replaced." : "Back to automatic.");
    }
    else if (ds.colact) setColumn({ action: ds.colact });
    else if (ds.mode) setSettings({ mode: ds.mode });
    else if (ds.deltpl) { await api(`/api/library/templates/${encodeURIComponent(ds.deltpl)}`, { method: "DELETE" }); await loadLib(); toast("Template deleted"); }
    else if (ds.delname) { await api("/api/library/name", { json: { real: ds.delname, delete: true } }); await loadLib(); }
    else if (ds.safeName) { await api("/api/library/name", { json: { real: ds.safeName, delete: true } }); await api("/api/library/safe", { json: { word: ds.safeName } }); await loadLib(); toast("Marked as safe"); }
    else if (ds.unsafe) { await api("/api/library/safe", { json: { word: ds.unsafe, remove: true } }); await loadLib(); }
    else if (ds.act) await action(ds.act);
  } catch (err) { toast(err.message, true); }
});

async function action(a) {
  if (a === "restart") { S.step = "upload"; S.job = null; S.grid = null; S.sel = null; S.verify = null; S.exp = null; S.preview = null; render(); }
  else if (a === "verify") { S.step = "verify"; S.verify = null; render(); S.verify = await api(`/api/jobs/${S.job.id}/verify`, { method: "POST" }); render(); }
  else if (a === "back") { S.step = "review"; render(); }
  else if (a === "export") { S.step = "export"; S.exp = null; render(); S.exp = await api(`/api/jobs/${S.job.id}/export`, { json: {} }); await loadLib(); render(); loadPreview(0); }
  else if (a === "openFolder") { await api("/api/open-folder", { json: { path: S.exp.out_dir } }); }
  else if (a === "copyPreview") { await navigator.clipboard.writeText(S.preview ? S.preview.text : ""); toast("Copied"); }
  else if (a === "nextReview") nextReview();
  else if (a === "addName") {
    const real = $("#nmReal").value.trim(); if (!real) return toast("Enter the real name", true);
    await api("/api/library/name", { json: { real, category: $("#nmCat").value, fake: $("#nmFake").value.trim() } }); await loadLib(); toast("Name added");
  }
  else if (a === "addSafe") { const w = $("#safeIn").value.trim(); if (!w) return; await api("/api/library/safe", { json: { word: w } }); await loadLib(); toast("Added to safe words"); }
  else if (a === "doRestore") {
    if (!S.restore.key) return toast("Choose the key file first", true);
    S.restore.result = await api("/api/restore", { json: { key: S.restore.key, text: S.restore.text } }); render();
  }
  else if (a === "copyRestore") { await navigator.clipboard.writeText(S.restore.result.text); toast("Copied"); }
}

async function upload(files) {
  S.busy = true; render();
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  try {
    S.job = await api("/api/jobs", { method: "POST", body: fd });
    S.file = 0; S.sheet = 0; S.step = "review"; S.tab = "summary"; S.sel = null; S.grid = null; S._scroll = null;
    S.busy = false; render(); await loadGrid();
    const found = S.job.files.filter((f) => f.template_found).length;
    toast(found ? `${found} file${found > 1 ? "s" : ""} recognised from your templates` : "Automatic pass done — review the plan");
  } catch (e) { S.busy = false; render(); toast(e.message, true); }
}

async function loadGrid(keepScroll = false) {
  if (!keepScroll) S._scroll = null;
  S.grid = await api(`/api/jobs/${S.job.id}/grid?file=${S.file}&sheet=${S.sheet}`);
  render();
}
async function setColumn(opts) {
  S.job = await api(`/api/jobs/${S.job.id}/column`, { json: { file: S.file, sheet: S.sheet, col: S.sel.c, ...opts } });
  await loadGrid(true);
}
async function setSettings(opts) {
  S.job = await api(`/api/jobs/${S.job.id}/settings`, { json: opts });
  await loadGrid(true);
}
async function loadPreview(i) {
  const p = await api(`/api/jobs/${S.job.id}/preview?file=${i}`);
  S.preview = { ...p, i };
  const el = $("#pvText"); if (el) el.textContent = p.text;
}
function nextReview() {
  const cells = [];
  for (const row of S.grid.rows) for (const c of row.cells) if (c.s === "review") cells.push([row.r, c.c]);
  if (!cells.length) {
    const f = S.job.files[S.file];
    const si = f.sheets.findIndex((s) => s.counts.review);
    if (si >= 0 && si !== S.sheet) { S.sheet = si; return loadGrid(); }
    const fi = S.job.files.findIndex((x) => x.counts.review);
    if (fi >= 0) { S.file = fi; S.sheet = 0; return loadGrid(); }
    return toast("Nothing left to review in this sheet");
  }
  const cur = S.sel && S.sel.type === "cell" ? S.sel : { r: 0, c: 0 };
  const nxt = cells.find(([r, c]) => r > cur.r || (r === cur.r && c > cur.c)) || cells[0];
  S.sel = { type: "cell", r: nxt[0], c: nxt[1] }; S.tab = "cell"; render();
  const td = document.querySelector(`td[data-r="${nxt[0]}"][data-c="${nxt[1]}"]`);
  if (td) td.scrollIntoView({ block: "center", inline: "center" });
}

route();
})();
