const D = JSON.parse(document.getElementById("hub-data").textContent);
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const DAY = 864e5;
const VERDICTS = { passed: "Passed", promoted: "Promoted", failed: "Failed", inconclusive: "Inconclusive", running: "Running", planned: "Planned" };
const STAGES = ["Card", "Run", "Report", "Summary", "OOS", "Shadow", "Live"];
const TAGS = { experiment: "Experiment", paper: "Paper", general: "General research" };
const HEADS = { experiment: "Experiments", paper: "Papers", general: "General research" };
const TOPIC = Object.fromEntries(D.topics);
const byId = Object.fromEntries(D.cards.map(c => [c.id, c]));
const STATUS = { done: "Done", next: "Next", active: "Active", idea: "Idea" };
const state = { topic: "all", verdict: "all", tag: "all", when: "all", view: "timeline", kind: "all", allDocs: false, allCards: false };
const CARD_LIMIT = 10;

const date = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const days = (a, b) => Math.round((b - a) / DAY);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const money = v => v == null ? "—" : `${v < 0 ? "−" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
const fixed = (v, d = 2) => v == null ? "—" : `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}`;
const href = l => /^(https?:|files\/)/.test(l) ? l : `${D.repo}/blob/main/${l}`;

/* chips */
function chips(el, options, active, pick) {
  el.innerHTML = options.map(([v, label, tag, n]) =>
    `<button type="button" data-v="${esc(v)}" class="${v === active ? "is-active" : ""}${tag ? ` c-${tag}` : ""}" aria-pressed="${v === active}">${tag ? `<span class="dot"></span>` : ""}${esc(label)}${n != null ? `<span class="n">${n}</span>` : ""}</button>`).join("");
  el.onclick = e => {
    const b = e.target.closest("button");
    if (!b) return;
    $$("button", el).forEach(c => { c.classList.toggle("is-active", c === b); c.setAttribute("aria-pressed", c === b); });
    pick(b.dataset.v);
  };
}

/* page chrome */
function chrome() {
  $("#repo").href = D.repo;
  const sha = D.build.commit.replace("-dirty", "");
  $("#built").innerHTML = `Built from <a href="${D.repo}/commit/${esc(sha)}" target="_blank" rel="noopener">${esc(D.build.commit)}</a> · ${esc(D.build.date)}`;
}

/* team */
function memberHtml(m) {
  const pm = m.role === "PM";
  const initials = m.name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const logs = m.logs ? `${m.logs} log ${m.logs === 1 ? "entry" : "entries"}${m.lastLog ? ` · last ${date(m.lastLog).toLocaleDateString("en-US", { month: "short", day: "numeric" })}` : ""}` : "No work log yet";
  const bits = [m.cards ? plural(m.cards, "card") : "No cards yet"];
  if (!pm) bits.push(m.logLink ? `<a href="${esc(m.logLink)}" target="_blank" rel="noopener">${logs}</a>` : logs);
  const topics = pm ? "" : `<div class="topics${m.topics.length ? "" : " none"}">${m.topics.length ? esc(m.topics.join(" · ")) : "Topic not picked yet"}</div>`;
  return `<article class="gs-card member${pm ? " pm" : ""}">
    ${m.photo ? `<img class="avatar" src="${esc(m.photo)}" alt="${esc(m.name)}" loading="lazy">` : `<div class="avatar" aria-hidden="true">${esc(initials)}</div>`}
    <div class="gs-cardh">${esc(m.name)}</div>
    <span class="vpill ${pm ? "v-pm" : "v-analyst"}">${pm ? "Portfolio manager" : "Analyst"}</span>
    ${topics}
    ${m.github ? `<a class="gh" href="https://github.com/${esc(m.github)}" target="_blank" rel="noopener">@${esc(m.github)}</a>` : ""}
    <div class="gs-divider">${bits.join("<br>")}</div>
  </article>`;
}

function team() {
  const analysts = D.team.filter(m => m.role !== "PM").length;
  $("#team-tag").textContent = `QUANTT · ${D.team.length - analysts} PM · ${plural(analysts, "analyst")}`;
  $("#team-grid").innerHTML = D.team.map(memberHtml).join("");
}

/* experiments */
function cardHtml(c) {
  const when = c.finished && c.finished !== c.started ? `${c.started} → ${c.finished}` : c.started;
  const n = c.trials.length;
  const bits = [n ? plural(n, "trial") : "no trials logged", c.figures.length && plural(c.figures.length, "chart"), c.report && "report"].filter(Boolean);
  const done = c.stages.filter(Boolean).length;
  return `<article class="gs-card xcard" id="card-${c.id}" data-id="${c.id}" data-topic="${c.topic}" data-verdict="${c.verdict}">
    <div class="xhead">
      <div class="xmain">
        <div class="gs-meta">${when} · ${esc(c.topicLabel)}${c.owner ? ` · ${esc(c.owner)}` : ""}</div>
        <h3 class="gs-cardh">${esc(c.title)}</h3>
        <div class="xverdict"><span class="vpill v-${c.verdict}">${VERDICTS[c.verdict]}</span>${c.detail ? `<span class="gs-meta">${esc(c.detail)}</span>` : ""}</div>
      </div>
      <button class="gs-pill gs-pill-ghost xtoggle" type="button" aria-expanded="false" aria-controls="body-${c.id}">Details</button>
    </div>
    <div class="xfoot">
      <ol class="stepper" aria-label="Lifecycle, ${done} of 7 stages">${STAGES.map((s, i) => `<li class="${c.stages[i] ? "done" : ""}">${s}</li>`).join("")}</ol>
      <div class="stage-text">${done} of 7 stages · ${STAGES.filter((_, i) => c.stages[i]).join(", ")}</div>
      <div class="gs-meta">${bits.join(" · ")}</div>
    </div>
    <div class="xbody" id="body-${c.id}" hidden></div>
  </article>`;
}

function trialsHtml(c) {
  const rows = c.trials.map(t => `<tr><td>${esc(t.variant || "run")}</td><td class="num">${t.spread_mult ? `${t.spread_mult}x` : "—"}</td>
    <td class="num">${money(t.pnl)}</td><td class="num">${fixed(t.sharpe)}</td><td class="num">${money(t.max_dd)}</td>
    <td class="num">${money(t.es_5)}</td><td class="num">${t.trades == null ? "—" : t.trades}</td>
    <td class="num">${t.win_rate == null ? "—" : `${Math.round(t.win_rate * 100)}%`}</td><td>${esc(t.run)} · ${esc(t.commit)}</td></tr>`).join("");
  const bare = c.trials.every(t => t.pnl == null);
  return `<p class="gs-meta" style="margin:0 0 14px">${plural(c.trials.length, "trial")} logged for this card, all shown.${bare ? " Forecast experiments log runs without P&L metrics." : " Window 2014-06-02 to 2024-12-31 unless noted on the card."}</p>
    <table class="trials"><thead><tr><th>Variant</th><th class="num">Spread</th><th class="num">Net P&amp;L</th><th class="num">Sharpe</th><th class="num">Max DD</th>
    <th class="num">ES 5%</th><th class="num">Trades</th><th class="num">Win</th><th>Run · commit</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function paneHtml(c, tab) {
  if (tab === "summary") return `<div class="prose">${c.summaryHtml}</div>`;
  if (tab === "card") return `<div class="prose">${c.cardHtml}</div>`;
  if (tab === "trials") return trialsHtml(c);
  if (tab === "charts") return `<div class="figs">${c.figures.map((f, i) =>
    `<button class="fig" type="button" data-fig="${i}"><img loading="lazy" src="${f.src}" alt="${esc(f.caption)}"><span class="gs-meta">${esc(f.caption)}</span></button>`).join("")}</div>`;
  return `<iframe class="pdf" data-src="${c.report}#view=FitH&navpanes=0" title="Report PDF for ${esc(c.id)}"></iframe>
    <div class="pane-foot"><span class="gs-meta">The full write-up, compiled from LaTeX.</span><a class="gs-pill gs-pill-ghost" href="${c.report}" target="_blank" rel="noopener">Open PDF</a></div>`;
}

function bodyHtml(c) {
  const tabs = [["summary", "Summary", c.summaryHtml], ["card", "Card", true], ["charts", "Charts", c.figures.length],
    ["trials", "Trials", c.trials.length], ["report", "Report", c.report]].filter(t => t[2]);
  return `<div class="gs-segment chips tabs" role="tablist">${tabs.map(([k, l], i) =>
      `<button type="button" role="tab" data-tab="${k}" class="${i ? "" : "is-active"}" aria-selected="${!i}">${l}</button>`).join("")}</div>
    <div class="pane">${tabs.map(([k], i) => `<div data-pane="${k}" role="tabpanel"${i ? " hidden" : ""}>${paneHtml(c, k)}</div>`).join("")}</div>
    <div class="pane-foot gs-meta"><span>${c.summaryHtml ? "" : "Summary not written yet · "}${esc(c.id)}</span><a href="${c.github}" target="_blank" rel="noopener">Folder on GitHub ↗</a></div>`;
}

function toggle(el, open) {
  const body = $(".xbody", el), btn = $(".xtoggle", el);
  open = open ?? body.hidden;
  if (open && !body.dataset.ready) { body.innerHTML = bodyHtml(byId[el.dataset.id]); body.dataset.ready = "1"; }
  body.hidden = !open;
  btn.setAttribute("aria-expanded", open);
  btn.textContent = open ? "Close" : "Details";
}

function showTab(btn) {
  const body = btn.closest(".xbody");
  $$("[data-tab]", body).forEach(b => { b.classList.toggle("is-active", b === btn); b.setAttribute("aria-selected", b === btn); });
  $$("[data-pane]", body).forEach(p => { p.hidden = p.dataset.pane !== btn.dataset.tab; });
  const frame = $(`[data-pane="${btn.dataset.tab}"] iframe[data-src]`, body);
  if (frame && !frame.getAttribute("src")) frame.src = frame.dataset.src;
}

function filterCards() {
  let match = 0;
  $$(".xcard").forEach(el => {
    const ok = (state.topic === "all" || el.dataset.topic === state.topic) && (state.verdict === "all" || el.dataset.verdict === state.verdict);
    match += ok;
    el.hidden = !ok || (!state.allCards && match > CARD_LIMIT);
  });
  $("#cards-empty").hidden = match > 0;
  $("#cards-more").hidden = state.allCards || match <= CARD_LIMIT;
  $("#cards-more button").textContent = `Show all ${match}`;
}

function experimentFilters() {
  const topics = D.topics.filter(([t]) => D.cards.some(c => c.topic === t));
  chips($("#f-topic"), [["all", "All topics"], ...topics], state.topic, v => { state.topic = v; filterCards(); });
  const verdicts = Object.keys(VERDICTS).filter(v => D.cards.some(c => c.verdict === v));
  chips($("#f-verdict"), [["all", "Any result"], ...verdicts.map(v => [v, VERDICTS[v]])], state.verdict, v => { state.verdict = v; filterCards(); });
}

function experiments() {
  $("#exp-tag").textContent = `${plural(D.cards.length, "card")} · ${D.stats.trials} trials logged`;
  experimentFilters();
  $("#cards").innerHTML = D.cards.map(cardHtml).join("") + `<p class="gs-meta" id="cards-empty" hidden>No cards match these filters.</p>
    <div class="more" id="cards-more" hidden><button class="gs-pill gs-pill-ghost" type="button">Show all</button></div>`;
  filterCards();
  $("#cards-more button").addEventListener("click", () => { state.allCards = true; filterCards(); });
  $("#cards").addEventListener("click", e => {
    const t = e.target.closest(".xtoggle");
    if (t) return toggle(t.closest(".xcard"));
    const tab = e.target.closest("[data-tab]");
    if (tab) return showTab(tab);
    const fig = e.target.closest("[data-fig]");
    if (fig) lightbox(byId[fig.closest(".xcard").dataset.id], Number(fig.dataset.fig));
  });
}

function openCard(id) {
  const el = document.getElementById(`card-${id}`);
  if (!el) return;
  if (el.hidden) { state.topic = state.verdict = "all"; state.allCards = true; experimentFilters(); filterCards(); }
  toggle(el, true);
  el.scrollIntoView({ block: "start" });
  history.replaceState(null, "", `#card-${id}`);
}

/* modal */
const modal = $("#modal"), dialog = $("#dialog");
let lastFocus = null, keys = null;

function openModal(html, wide = false) {
  lastFocus = document.activeElement;
  dialog.className = `gs-dialog${wide ? " wide" : ""}`;
  dialog.innerHTML = html;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  ($("[data-focus]", dialog) || $("button, a", dialog))?.focus();
}

function closeModal() {
  modal.hidden = true;
  dialog.innerHTML = "";
  keys = null;
  document.body.style.overflow = "";
  lastFocus?.focus();
}

modal.addEventListener("click", e => {
  if (e.target === modal || e.target.closest("[data-close]")) return closeModal();
  const open = e.target.closest("[data-open-card]");
  if (open) { closeModal(); openCard(open.dataset.openCard); }
});
document.addEventListener("keydown", e => {
  if (modal.hidden) return;
  if (e.key === "Escape") closeModal();
  else if (keys) keys(e);
});

function lightbox(c, i) {
  const f = c.figures[i];
  openModal(`<h2 id="dlg-title">${esc(f.caption)}</h2><div class="gs-meta">${esc(c.id)} · ${i + 1} of ${c.figures.length}${c.figures.length > 1 ? " · ← → to step" : ""}</div>
    <img class="shot" src="${f.src}" alt="${esc(f.caption)}">
    <div class="gs-actions"><button class="gs-pill gs-pill-ghost" type="button" data-close data-focus>Close</button></div>`, true);
  keys = e => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (step) lightbox(c, (i + step + c.figures.length) % c.figures.length);
  };
}

const whenText = it => it.start ? (it.end && it.end !== it.start ? `${it.start} → ${it.end}` : it.start) : "Not scheduled";
const statusText = it => it.verdict ? VERDICTS[it.verdict] : STATUS[it.status] || it.status;

function itemModal(it) {
  const rows = [["Tag", `<span class="dot c-${it.tag}"></span> ${TAGS[it.tag]}`], ["Topic", esc(TOPIC[it.topic] || it.topic)],
    ["Owner", esc(it.owner || "Unassigned")], ["Dates", whenText(it)], [it.verdict ? "Result" : "Status", statusText(it)]];
  const act = it.card && byId[it.card] ? `<button class="gs-pill gs-pill-primary" type="button" data-open-card="${esc(it.card)}">Open card</button>`
    : it.link ? `<a class="gs-pill gs-pill-primary" href="${esc(href(it.link))}" target="_blank" rel="noopener">Open</a>` : "";
  openModal(`<h2 id="dlg-title">${esc(it.title)}</h2>
    <dl class="rows">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
    ${it.note ? `<div class="note">${esc(it.note)}</div>` : ""}
    <div class="gs-actions"><button class="gs-pill gs-pill-ghost" type="button" data-close>Close</button>${act}</div>`);
}

/* roadmap */
const BACK = 6, AHEAD = 12, LANE = 26;
const today = new Date(); today.setHours(0, 0, 0, 0);
const g0 = new Date(today); g0.setDate(g0.getDate() - ((g0.getDay() + 6) % 7) - 7 * BACK);
const SPAN = 7 * (BACK + AHEAD);
const ctx = document.createElement("canvas").getContext("2d");
const textW = (s, weight) => { ctx.font = `${weight} 13px Inter, system-ui, sans-serif`; return ctx.measureText(s).width; };
const isNext = it => it.status !== "done";
const short = it => {
  if (it.short || it.title.length <= 34) return it.short || it.title;
  const cut = it.title.lastIndexOf(" ", 32);
  return `${it.title.slice(0, cut > 12 ? cut : 32)}…`;
};
const roadItems = () => D.timeline.filter(it => (state.tag === "all" || it.tag === state.tag)
  && (state.when === "all" || (state.when === "done") === !isNext(it)));

function layout(items, px, width, at) {
  const list = [];
  for (const it of items) {
    const a = days(g0, date(it.start)), b = days(g0, date(it.end || it.start));
    if (b < 0 || a >= SPAN) continue;
    const next = isNext(it), bar = b > a, a0 = Math.max(a, 0), b0 = Math.min(b, SPAN - 1);
    const lw = textW(short(it), next ? 500 : 400) + (it.verdict === "passed" ? 14 : 0);
    const mark = bar ? (b0 - a0 + 1) * px : next ? 12 : 10;
    const inside = bar && next && lw + 20 <= mark;
    list.push({ it, next, bar, inside, mark, x: bar ? a0 * px : (a0 + 0.5) * px - mark / 2, w: inside ? mark : mark + 7 + lw });
  }
  list.sort((p, q) => p.x - q.x);
  const lanes = [];
  for (const e of list) {
    e.flip = e.x + e.w + 8 > width;
    const lo = e.flip ? e.x + e.mark - e.w : e.x;
    let lane = lanes.findIndex(end => end + 14 <= lo);
    if (lane < 0) { lane = lanes.length; lanes.push(0); }
    lanes[lane] = lo + e.w;
    e.lane = lane;
    e.cross = !e.inside && lo < at + 3 && lo + e.w > at - 3;
  }
  return { list, lanes: Math.max(lanes.length, 1) };
}

function itemHtml(e, i, width) {
  const it = e.it, name = esc(short(it));
  const pos = e.flip ? `right:${width - e.x - e.mark}px;flex-direction:row-reverse` : `left:${e.x}px`;
  const pass = it.verdict === "passed" ? `<span class="g-pass">✓</span>` : "";
  const mark = e.bar ? `<span class="g-mark bar-mark" style="width:${e.mark}px">${e.inside ? name : ""}</span>` : `<span class="g-mark dot-mark"></span>`;
  return `<button class="g-item c-${it.tag}${e.next ? " next" : ""}${e.cross ? " cross" : ""}" type="button" data-i="${i}" style="top:${8 + e.lane * LANE}px;${pos}"
    aria-label="${esc(`${it.title}. ${TAGS[it.tag]}, ${whenText(it)}, ${statusText(it)}`)}">${mark}${e.inside ? "" : `<span>${name}</span>`}${pass}</button>`;
}

function gantt() {
  const root = $("#gantt");
  root.className = "gantt";
  const lab = innerWidth <= 760 ? 116 : 190;
  root.style.setProperty("--label", `${lab}px`);
  const width = Math.max(root.clientWidth, 960) - lab, px = width / SPAN;
  root.style.setProperty("--week", `${7 * px}px`);
  const at = (days(g0, today) + 0.5) * px;
  const head = [];
  for (let d = new Date(g0.getFullYear(), g0.getMonth() + 1, 1); days(g0, d) < SPAN; d.setMonth(d.getMonth() + 1)) {
    head.push(`<div class="g-month" style="left:${days(g0, d) * px}px"><b>${d.toLocaleString("en-US", { month: "short" })}</b> ${d.getFullYear()}</div>`);
  }
  for (let k = 0; k < SPAN; k += 7) {
    const d = new Date(g0); d.setDate(d.getDate() + k);
    head.push(`<div class="g-week" style="left:${k * px}px">${d.getDate()}</div>`);
  }
  head.push(`<div class="g-side" style="right:${width - at + 66}px">← Done</div><div class="g-side" style="left:${at + 66}px">Up next →</div>`);
  const items = roadItems().filter(it => it.start);
  gantt.items = [];
  const rows = D.topics.map(([topic, label]) => {
    const { list, lanes } = layout(items.filter(it => it.topic === topic), px, width, at);
    const html = list.map(e => itemHtml(e, gantt.items.push(e.it) - 1, width)).join("");
    return `<div class="g-row"><div class="g-label">${esc(label)}<span class="n">${list.length || ""}</span></div>
      <div class="g-track" style="height:${lanes * LANE + 16}px">${html || `<span class="g-empty">—</span>`}</div></div>`;
  }).join("");
  const none = gantt.items.length ? "" : `<div class="g-none">${state.when === "done" ? "Nothing finished in this window."
    : "Nothing scheduled yet. The ideas below have no dates: add a start and end in research/roadmap.toml to place them here."}</div>`;
  const day = today.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  root.innerHTML = `<div class="g-future" style="left:${lab + at}px"></div>
    <div class="g-row g-head"><div class="g-label"></div><div class="g-track">${head.join("")}</div></div>${none || rows}
    <div class="g-today" style="left:${lab + at}px"><span>Today · ${day}</span></div>`;
  const sc = root.parentElement;
  sc.scrollLeft = Math.max(0, at - (sc.clientWidth - lab) * 0.55);
}

function showTip(btn) {
  const it = gantt.items[Number(btn.dataset.i)], tip = $("#g-tip");
  const title = document.createElement("div"), meta = document.createElement("div"), dot = document.createElement("span");
  title.className = "t";
  title.textContent = it.title;
  meta.className = "m";
  dot.className = `dot c-${it.tag}`;
  meta.append(dot, `${TAGS[it.tag]} · ${TOPIC[it.topic] || it.topic} · ${whenText(it)} · ${statusText(it)}`);
  tip.replaceChildren(title, meta);
  tip.hidden = false;
  const card = $("#gantt-view").getBoundingClientRect(), r = btn.getBoundingClientRect();
  const below = r.bottom - card.top + 6;
  tip.style.left = `${Math.min(Math.max(r.left - card.left, 8), card.width - tip.offsetWidth - 8)}px`;
  tip.style.top = `${below + tip.offsetHeight > card.height ? r.top - card.top - tip.offsetHeight - 6 : below}px`;
}

function listView() {
  const items = roadItems(), rows = [];
  listView.items = [];
  const groups = [["Up next", items.filter(it => it.start && isNext(it)).sort((a, b) => a.start.localeCompare(b.start))],
    ["Ideas", items.filter(it => !it.start)],
    ["Done", items.filter(it => it.start && !isNext(it)).sort((a, b) => b.start.localeCompare(a.start))]];
  for (const [name, list] of groups) {
    if (!list.length) continue;
    rows.push(`<tr class="grp"><th colspan="6">${name} <span class="n">${list.length}</span></th></tr>`);
    for (const it of list) {
      rows.push(`<tr><td class="when">${it.start ? whenText(it) : "—"}</td>
        <td><button class="l-item" type="button" data-l="${listView.items.push(it) - 1}">${esc(it.title)}</button></td>
        <td class="tagcell"><span class="dot c-${it.tag}"></span>${TAGS[it.tag]}</td><td>${esc(TOPIC[it.topic] || it.topic)}</td>
        <td>${esc(it.owner || "—")}</td><td>${statusText(it)}</td></tr>`);
    }
  }
  $("#list-view").innerHTML = rows.length ? `<div class="list-scroll"><table class="ltable"><thead><tr><th>When</th><th>Item</th><th>Tag</th>
    <th>Topic</th><th>Owner</th><th>Status</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`
    : `<p class="gs-meta">Nothing matches these filters.</p>`;
}

function ideas() {
  const list = roadItems().filter(it => !it.start);
  ideas.list = list;
  $("#ideas-block").hidden = state.view === "list" || state.when === "done";
  $("#ideas-meta").textContent = list.length ? `${plural(list.length, "undated item")} · add dates in research/roadmap.toml` : "No undated items";
  $("#ideas").className = "ideas";
  $("#ideas").innerHTML = Object.keys(TAGS).map(t => {
    const mine = list.map((it, i) => [it, i]).filter(([it]) => it.tag === t);
    return mine.length ? `<div class="idea-col c-${t}"><div class="colhead"><span class="dot"></span>${HEADS[t]}<span class="n">${mine.length}</span></div>
      <div class="idea-list">${mine.map(([it, i]) => `<button class="idea" type="button" data-idea="${i}">${esc(it.title)}</button>`).join("")}</div></div>` : "";
  }).join("");
}

function road() {
  const list = state.view === "list";
  $("#gantt-view").hidden = list;
  $("#g-key").hidden = list;
  $("#list-view").hidden = !list;
  $("#g-tip").hidden = true;
  list ? listView() : gantt();
  ideas();
}

function roadmap() {
  $("#road-tag").textContent = `${BACK} weeks back · ${AHEAD} ahead`;
  const count = t => D.timeline.filter(it => it.tag === t).length;
  chips($("#f-tag"), [["all", "All tags"], ...Object.keys(TAGS).map(t => [t, HEADS[t], t, count(t)])], state.tag, v => { state.tag = v; road(); });
  chips($("#f-when"), [["all", "Any time"], ["next", "Up next"], ["done", "Done"]], state.when, v => { state.when = v; road(); });
  chips($("#f-view"), [["timeline", "Timeline"], ["list", "List"]], state.view, v => { state.view = v; road(); });
  $("#g-key").innerHTML = `<span><i class="k-dot"></i>Finished</span><span><i class="k-next"></i><i class="k-bar"></i>Scheduled</span>
    <span><b class="g-pass">✓</b>Passed card</span><span><i class="k-past"></i>Before today</span><span>Hover for details · click to open</span>`;
  road();
  const g = $("#gantt");
  g.addEventListener("click", e => { const b = e.target.closest(".g-item"); if (b) itemModal(gantt.items[Number(b.dataset.i)]); });
  g.addEventListener("pointerover", e => { const b = e.target.closest(".g-item"); b ? showTip(b) : ($("#g-tip").hidden = true); });
  g.addEventListener("pointerleave", () => { $("#g-tip").hidden = true; });
  g.addEventListener("focusin", e => { const b = e.target.closest(".g-item"); if (b) showTip(b); });
  g.addEventListener("focusout", () => { $("#g-tip").hidden = true; });
  g.parentElement.addEventListener("scroll", () => { $("#g-tip").hidden = true; });
  $("#list-view").addEventListener("click", e => { const b = e.target.closest("[data-l]"); if (b) itemModal(listView.items[Number(b.dataset.l)]); });
  $("#ideas").addEventListener("click", e => { const b = e.target.closest("[data-idea]"); if (b) itemModal(ideas.list[Number(b.dataset.idea)]); });
  let frame = 0;
  addEventListener("resize", () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => state.view === "timeline" && gantt()); });
  document.fonts?.ready.then(() => state.view === "timeline" && gantt());
}

/* library */
const KINDS = [["all", "All"], ["Literature report", "Literature"], ["Research note", "Notes"], ["General research", "General"], ["Paper", "Papers"]];
const KIND_C = { "Literature report": "lit", "Research note": "note", "General research": "note", Paper: "pub" };
const LIMIT = 12;

function docs() {
  const list = D.library.filter(d => state.kind === "all" || d.kind === state.kind);
  const cut = state.allDocs ? list : list.slice(0, LIMIT);
  $("#docs").innerHTML = cut.map(d => `<a class="gs-card doc" href="${esc(d.href)}" target="_blank" rel="noopener">
      <div class="doc-meta"><span class="kind c-${KIND_C[d.kind] || "note"}"><span class="dot"></span>${esc(d.kind)}</span>${d.date ? `<span class="gs-meta">${d.date}</span>` : ""}</div>
      <div class="gs-cardh">${esc(d.title)}</div>
      <div class="open">${d.kind === "Paper" ? "View on GitHub ↗" : "Open PDF ↗"}</div></a>`).join("")
    + (list.length > cut.length ? `<div class="more" style="grid-column:1/-1"><button class="gs-pill gs-pill-ghost" type="button" id="more">Show all ${list.length}</button></div>` : "");
  $("#more")?.addEventListener("click", () => { state.allDocs = true; docs(); });
}

function library() {
  const reports = D.library.filter(d => d.kind !== "Paper").length;
  $("#lib-tag").textContent = `${plural(reports, "report")} · ${plural(D.stats.papers, "paper")}`;
  const kinds = KINDS.filter(([k]) => k === "all" || D.library.some(d => d.kind === k))
    .map(([k, l]) => k === "all" ? [k, l] : [k, l, KIND_C[k], D.library.filter(d => d.kind === k).length]);
  chips($("#f-kind"), kinds, state.kind, v => { state.kind = v; state.allDocs = false; docs(); });
  docs();
}

chrome();
team();
experiments();
roadmap();
library();
$("#latest").addEventListener("click", () => D.cards.length && openCard(D.cards[0].id));
if (location.hash.startsWith("#card-")) openCard(location.hash.slice(6));
