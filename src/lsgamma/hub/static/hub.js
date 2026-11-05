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
const ICON = {
  github: `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>`,
  linkedin: `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>`,
};
const TOPIC_C = { RV_Forecasting: "rv", Deep_Hedging: "dh", Agentic_Routing: "ar", Risk_Management: "rm" };
const TOPIC_KEY = Object.fromEntries(D.topics.map(([k, l]) => [l, k]));
const RESULT = { passed: ["✓", "pass"], promoted: ["✓", "pass"], failed: ["✕", "fail"], inconclusive: ["–", "neutral"], running: ["◐", "neutral"], planned: ["○", "neutral"] };
const state = { topic: "all", verdict: "all", tag: "all", when: "all", view: innerWidth <= 760 ? "list" : "timeline", kind: "all", allDocs: false, allCards: false, allDone: false, q: "", eq: "" };
const DONE_LIMIT = 8;
const PHONE = innerWidth <= 760;
const CARD_LIMIT = PHONE ? 8 : 15;
const topicChip = (key, label) => `<span class="kind c-${TOPIC_C[key] || "rv"}"><span class="dot"></span>${esc(label)}</span>`;
const resultPill = v => `<span class="result r-${RESULT[v][1]}"><span class="ri" aria-hidden="true">${RESULT[v][0]}</span>${VERDICTS[v]}</span>`;

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
  $("#repo").href = $("#menu-repo").href = D.repo;
  const btn = $("#menu-btn"), menu = $("#menu");
  const set = open => {
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", open);
    btn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };
  btn.addEventListener("click", () => set(menu.hidden));
  menu.addEventListener("click", e => { if (e.target.closest("a")) set(false); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !menu.hidden) { set(false); btn.focus(); } });
  document.addEventListener("click", e => { if (!menu.hidden && !e.target.closest(".gs-nav")) set(false); });
  addEventListener("resize", () => { if (innerWidth > 900) set(false); });
  const sha = D.build.commit.replace("-dirty", "");
  $("#built").innerHTML = `Built from <a href="${D.repo}/commit/${esc(sha)}" target="_blank" rel="noopener">${esc(D.build.commit)}</a> · ${esc(D.build.date)}`;
}

/* team */
function memberHtml(m) {
  const pm = m.role === "PM";
  const initials = m.name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const topics = pm ? "" : `<div class="topics${m.topics.length ? "" : " none"}">${m.topics.length
    ? m.topics.map(t => topicChip(TOPIC_KEY[t], t)).join(" ") : "Topic not picked yet"}</div>`;
  return `<article class="gs-card member${pm ? " pm" : ""}">
    ${m.photo ? `<img class="avatar" src="${esc(m.photo)}" alt="${esc(m.name)}" loading="lazy">` : `<div class="avatar" aria-hidden="true">${esc(initials)}</div>`}
    <div class="gs-cardh">${esc(m.name)}</div>
    <span class="vpill ${pm ? "v-pm" : "v-analyst"}">${pm ? "Portfolio manager" : "Analyst"}</span>
    ${topics}
    <div class="mfoot"><div class="links">${m.github ? `<a class="icon-link" href="https://github.com/${esc(m.github)}" target="_blank" rel="noopener" aria-label="${esc(m.name)} on GitHub" title="@${esc(m.github)} on GitHub">${ICON.github}</a>` : ""}${m.linkedin ? `<a class="icon-link" href="${esc(m.linkedin)}" target="_blank" rel="noopener" aria-label="${esc(m.name)} on LinkedIn" title="${esc(m.name)} on LinkedIn">${ICON.linkedin}</a>` : ""}</div></div>
  </article>`;
}

function team() {
  $("#team-grid").innerHTML = D.team.map(memberHtml).join("");
}

/* experiments */
function cardHtml(c) {
  const when = date(c.started).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const done = c.stages.filter(Boolean).length;
  const search = [c.id.slice(11), c.title, c.topicLabel, VERDICTS[c.verdict], c.detail, c.owner].join(" ").toLowerCase();
  return `<article class="xrow" id="card-${c.id}" data-id="${c.id}" data-topic="${c.topic}" data-verdict="${c.verdict}" data-search="${esc(search)}">
    <button class="xhead" type="button" aria-expanded="false" aria-controls="body-${c.id}">
      ${topicChip(c.topic, c.topicLabel)}
      <span class="xmain"><span class="xname">${esc(c.id.slice(11))}</span><span class="hyp">${esc(c.title)}</span></span>
      <span class="dots" role="img" aria-label="${done} of 7 stages">${c.stages.map(on => `<i class="${on ? "on" : ""}"></i>`).join("")}</span>
      <span class="ldate">${when}</span>
      ${resultPill(c.verdict)}
      <span class="chev" aria-hidden="true">›</span>
    </button>
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
  const n = c.trials.length, done = c.stages.filter(Boolean).length;
  const bits = [c.owner && esc(c.owner), n ? plural(n, "trial") : "no trials logged", c.figures.length && plural(c.figures.length, "chart"), c.report && "report"].filter(Boolean);
  return `<div class="xinfo"><ol class="stepper" aria-label="Lifecycle, ${done} of 7 stages">${STAGES.map((s, i) => `<li class="${c.stages[i] ? "done" : ""}">${s}</li>`).join("")}</ol>
      <div class="stage-text">${done} of 7 stages · ${STAGES[c.stages.lastIndexOf(true)]}</div><span class="gs-meta">${bits.join(" · ")}</span></div>
    ${c.detail ? `<p class="xresult"><span class="lab">Result</span>${esc(c.detail)}</p>` : ""}
    <div class="gs-segment chips tabs" role="tablist">${tabs.map(([k, l], i) =>
      `<button type="button" role="tab" data-tab="${k}" class="${i ? "" : "is-active"}" aria-selected="${!i}">${l}</button>`).join("")}</div>
    <div class="pane">${tabs.map(([k], i) => `<div data-pane="${k}" role="tabpanel"${i ? " hidden" : ""}>${paneHtml(c, k)}</div>`).join("")}</div>
    <div class="pane-foot gs-meta"><span>${c.summaryHtml ? "" : "Summary not written yet · "}${esc(c.id)}</span><a href="${c.github}" target="_blank" rel="noopener">Folder on GitHub ↗</a></div>`;
}

function toggle(el, open) {
  const body = $(".xbody", el), btn = $(".xhead", el);
  open = open ?? body.hidden;
  if (open && !body.dataset.ready) { body.innerHTML = bodyHtml(byId[el.dataset.id]); body.dataset.ready = "1"; }
  body.hidden = !open;
  el.classList.toggle("open", open);
  btn.setAttribute("aria-expanded", open);
}

function showTab(btn) {
  const body = btn.closest(".xbody");
  $$("[data-tab]", body).forEach(b => { b.classList.toggle("is-active", b === btn); b.setAttribute("aria-selected", b === btn); });
  $$("[data-pane]", body).forEach(p => { p.hidden = p.dataset.pane !== btn.dataset.tab; });
  const frame = $(`[data-pane="${btn.dataset.tab}"] iframe[data-src]`, body);
  if (frame && !frame.getAttribute("src")) frame.src = frame.dataset.src;
}

function filterCards() {
  const words = state.eq.toLowerCase().split(/\s+/).filter(Boolean);
  let match = 0;
  $$(".xrow").forEach(el => {
    const ok = (state.topic === "all" || el.dataset.topic === state.topic) && (state.verdict === "all" || el.dataset.verdict === state.verdict)
      && words.every(w => el.dataset.search.includes(w));
    match += ok;
    el.hidden = !ok || (!state.allCards && !words.length && match > CARD_LIMIT);
    if (ok) {
      const c = byId[el.dataset.id];
      $(".xname", el).innerHTML = marked(c.id.slice(11), words);
      $(".hyp", el).innerHTML = marked(c.title, words);
    }
  });
  const capped = !state.allCards && !words.length && match > CARD_LIMIT;
  $("#exp-count").textContent = words.length ? `${match} of ${D.cards.length} match “${state.eq.trim()}”`
    : `${plural(match, "experiment")}${capped ? `, newest ${CARD_LIMIT} shown` : ""}`;
  $("#cards-empty").hidden = match > 0;
  $("#cards-more").hidden = !capped;
  $("#cards-more button").textContent = `Show all ${match}`;
}

function experimentFilters() {
  const count = (k, v) => D.cards.filter(c => c[k] === v).length;
  const topics = D.topics.filter(([t]) => count("topic", t)).map(([t, l]) => [t, l, TOPIC_C[t], count("topic", t)]);
  chips($("#f-topic"), [["all", "All topics"], ...topics], state.topic, v => { state.topic = v; filterCards(); });
  const verdicts = Object.keys(VERDICTS).filter(v => count("verdict", v)).map(v => [v, VERDICTS[v], RESULT[v][1], count("verdict", v)]);
  chips($("#f-verdict"), [["all", "Any result"], ...verdicts], state.verdict, v => { state.verdict = v; filterCards(); });
}

function experiments() {
  experimentFilters();
  $("#cards").innerHTML = D.cards.map(cardHtml).join("") + `<p class="gs-meta empty" id="cards-empty" hidden>No experiments match. Try fewer words or another filter.</p>
    <div class="more" id="cards-more" hidden><button class="gs-pill gs-pill-ghost" type="button">Show all</button></div>`;
  filterCards();
  $("#cards-more button").addEventListener("click", () => { state.allCards = true; filterCards(); });
  const q = $("#exp-q");
  q.addEventListener("input", () => { state.eq = q.value; filterCards(); });
  q.addEventListener("keydown", e => { if (e.key === "Escape") { q.value = state.eq = ""; filterCards(); } });
  $("#cards").addEventListener("click", e => {
    const t = e.target.closest(".xhead");
    if (t) {
      const el = t.closest(".xrow");
      toggle(el);
      return el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    const tab = e.target.closest("[data-tab]");
    if (tab) return showTab(tab);
    const fig = e.target.closest("[data-fig]");
    if (fig) lightbox(byId[fig.closest(".xrow").dataset.id], Number(fig.dataset.fig));
  });
}

function openCard(id) {
  const el = document.getElementById(`card-${id}`);
  if (!el) return;
  if (el.hidden) {
    state.topic = state.verdict = "all";
    state.eq = $("#exp-q").value = "";
    state.allCards = true;
    experimentFilters();
    filterCards();
  }
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
    const cut = name === "Done" && !state.allDone ? list.slice(0, DONE_LIMIT) : list;
    for (const it of cut) {
      const result = it.verdict ? `<span class="ri r-${RESULT[it.verdict][1]}" aria-hidden="true">${RESULT[it.verdict][0]}</span> ` : "";
      rows.push(`<tr><td class="when${it.start ? "" : " nodate"}">${it.start ? whenText(it) : "—"}</td>
        <td><button class="l-item" type="button" data-l="${listView.items.push(it) - 1}">${esc(it.short || it.title)}</button></td>
        <td class="tagcell"><span class="dot c-${it.tag}"></span>${TAGS[it.tag]}</td><td>${esc(TOPIC[it.topic] || it.topic)}</td>
        <td>${esc(it.owner || "—")}</td><td>${result}${statusText(it)}</td></tr>`);
    }
    if (cut.length < list.length) {
      rows.push(`<tr class="more-row"><td colspan="6"><button class="gs-pill gs-pill-ghost" type="button" data-all-done>Show all ${list.length} done</button></td></tr>`);
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
    return mine.length ? `<div class="idea-col c-${t}"><div class="colhead">${HEADS[t]}<span class="n">${mine.length}</span></div>
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
  $("#list-view").addEventListener("click", e => {
    if (e.target.closest("[data-all-done]")) { state.allDone = true; return listView(); }
    const b = e.target.closest("[data-l]");
    if (b) itemModal(listView.items[Number(b.dataset.l)]);
  });
  $("#ideas").addEventListener("click", e => { const b = e.target.closest("[data-idea]"); if (b) itemModal(ideas.list[Number(b.dataset.idea)]); });
  let frame = 0;
  addEventListener("resize", () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => state.view === "timeline" && gantt()); });
  document.fonts?.ready.then(() => state.view === "timeline" && gantt());
}

/* library */
const KINDS = [["all", "All"], ["Literature report", "Literature"], ["Research note", "Notes"], ["General research", "General"], ["Paper", "Papers"]];
const KIND_C = { "Literature report": "lit", "Research note": "note", "General research": "note", Paper: "pub" };
const LIMIT = PHONE ? 8 : 15;

const reEsc = w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function marked(text, words) {
  if (!words.length) return esc(text);
  const re = new RegExp(`(${words.map(reEsc).join("|")})`, "gi");
  return text.split(re).map((part, i) => i % 2 ? `<mark>${esc(part)}</mark>` : esc(part)).join("");
}

function docs() {
  const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  const list = D.library.filter(d => (state.kind === "all" || d.kind === state.kind)
    && words.every(w => `${d.title} ${d.kind}`.toLowerCase().includes(w)));
  const cut = state.allDocs || words.length ? list : list.slice(0, LIMIT);
  const scope = state.kind === "all" ? "items" : `${state.kind.toLowerCase()}s`;
  $("#lib-count").textContent = words.length ? `${list.length} of ${D.library.length} match “${state.q.trim()}”`
    : `${list.length} ${scope}${cut.length < list.length ? `, newest ${cut.length} shown` : ""}`;
  $("#docs").innerHTML = cut.map(d => `<a class="lrow" href="${esc(d.href)}" target="_blank" rel="noopener">
      <span class="kind c-${KIND_C[d.kind] || "note"}"><span class="dot"></span>${esc(d.kind)}</span>
      <span class="ltitle">${marked(d.title, words)}</span>
      <span class="ldate">${d.date ? short_day(d.date) + ", " + d.date.slice(0, 4) : "—"}</span>
      <span class="lopen">${d.kind === "Paper" ? "GitHub ↗" : "Open PDF ↗"}</span></a>`).join("")
    + (list.length ? "" : `<p class="gs-meta empty">No matches. Try fewer words or another filter.</p>`)
    + (list.length > cut.length ? `<div class="more"><button class="gs-pill gs-pill-ghost" type="button" id="more">Show all ${list.length}</button></div>` : "");
  $("#more")?.addEventListener("click", () => { state.allDocs = true; docs(); });
}

function library() {
  const kinds = KINDS.filter(([k]) => k === "all" || D.library.some(d => d.kind === k))
    .map(([k, l]) => k === "all" ? [k, l] : [k, l, KIND_C[k], D.library.filter(d => d.kind === k).length]);
  chips($("#f-kind"), kinds, state.kind, v => { state.kind = v; state.allDocs = false; docs(); });
  const q = $("#lib-q");
  q.addEventListener("input", () => { state.q = q.value; docs(); });
  q.addEventListener("keydown", e => { if (e.key === "Escape") { q.value = state.q = ""; docs(); } });
  document.addEventListener("keydown", e => {
    if (e.key === "/" && !e.target.closest("input, textarea") && modal.hidden) { e.preventDefault(); q.focus(); }
  });
  docs();
}

/* this week */
const short_day = s => date(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });
const long_day = s => date(s).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
const signed = v => v == null ? "—" : `${Math.round(v) < 0 ? "−" : Math.round(v) > 0 ? "+" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
const contract = t => `${t.side} ${+t.strike} ${t.right === "P" ? "put" : "call"} (${short_day(t.expiry)})`;
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function weekTile(href, n, label, sub) {
  return `<a class="wstat" href="${href}"><div class="dnum">${esc(n)}</div><div class="wlab">${esc(label)}</div><div class="gs-meta">${esc(sub)}</div></a>`;
}

function week() {
  const start = new Date(today);
  start.setDate(start.getDate() - 6);
  const lo = iso(start), hi = iso(today);
  const inside = s => s && s >= lo && s <= hi;
  const done = D.cards.filter(c => inside(c.finished));
  const passed = done.filter(c => c.verdict === "passed" || c.verdict === "promoted").length;
  const failed = done.filter(c => c.verdict === "failed").length;
  const other = done.length - passed - failed;
  const runDay = r => `${r.slice(0, 4)}-${r.slice(4, 6)}-${r.slice(6, 8)}`;
  const trials = D.cards.flatMap(c => c.trials).filter(t => t.run && inside(runDay(t.run))).length;
  const reports = D.library.filter(d => d.kind !== "Paper" && inside(d.date));
  const lit = reports.filter(d => d.kind === "Literature report").length;
  const trades = (D.desk?.trades || []).filter(t => inside(t.date));
  const opened = trades.filter(t => t.action === "open").length;
  const book = D.desk?.book || [];
  const before = book.filter(b => b.date < lo).at(-1)?.total ?? 0;
  const now = book.filter(b => b.date <= hi).at(-1)?.total;
  $("#week-meta").textContent = `${short_day(lo)} – ${short_day(hi)}`;
  $("#week-stats").innerHTML = [
    weekTile("#experiments", done.length, done.length === 1 ? "experiment finished" : "experiments finished",
      `${passed} passed · ${failed} failed${other ? ` · ${other} other` : ""}`),
    weekTile("#experiments", trials, trials === 1 ? "trial logged" : "trials logged", "backtest and forecast runs"),
    weekTile("#library", reports.length, reports.length === 1 ? "report published" : "reports published",
      `${lit} literature · ${reports.length - lit} notes`),
    weekTile("#desk", trades.length, trades.length === 1 ? "paper trade" : "paper trades", `${opened} opened · ${trades.length - opened} closed`),
    weekTile("#desk", now == null ? "—" : signed(now - before), "book P&L this week", "realized + open, paper"),
  ].join("");
}

/* live desk */
const SIDE = { short: "Short gamma", long: "Long gamma", flat: "Flat" };
const pts = v => `${v < 0 ? "−" : "+"}${Math.abs(v * 100).toFixed(1)} pts`;
const pct = v => `${(v * 100).toFixed(1)}%`;

function deskChart(k, W) {
  const S = k.signals, r = k.rules, H = 250, L = 44, R = 12, T = 14, B = 30;
  if (!S.length) return `<p class="gs-meta empty">No signals logged yet.</p>`;
  const vals = S.map(s => s.vrp * 100), top = Math.max(...vals, r.short_band * 100) + 2, bot = Math.min(...vals, r.long_band * 100) - 2;
  const x = i => L + (S.length === 1 ? (W - L - R) / 2 : i * (W - L - R) / (S.length - 1));
  const y = v => T + (top - v) * (H - T - B) / (top - bot);
  const sb = y(r.short_band * 100), lb = y(r.long_band * 100), zero = y(0);
  const ticks = [[r.short_band * 100, `+${r.short_band * 100}`], [0, "0"], [r.long_band * 100, `${r.long_band * 100}`.replace("-", "−")]];
  const labels = [0, Math.floor((S.length - 1) / 2), S.length - 1].filter((v, i, a) => a.indexOf(v) === i);
  return `<svg class="dchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="VRP over the last ${S.length} signals with the short and long bands">
    <rect x="${L}" y="${T}" width="${W - L - R}" height="${sb - T}" class="zone"/>
    <rect x="${L}" y="${lb}" width="${W - L - R}" height="${H - B - lb}" class="zone"/>
    <text x="${L + 8}" y="${T + 14}" class="zlab">Short gamma zone</text>
    <text x="${L + 8}" y="${H - B - 8}" class="zlab">Long gamma zone</text>
    <line x1="${L}" x2="${W - R}" y1="${zero}" y2="${zero}" class="base"/>
    <line x1="${L}" x2="${W - R}" y1="${sb}" y2="${sb}" class="band"/>
    <line x1="${L}" x2="${W - R}" y1="${lb}" y2="${lb}" class="band"/>
    ${ticks.map(([v, t]) => `<text x="${L - 8}" y="${y(v) + 4}" class="tick" text-anchor="end">${t}</text>`).join("")}
    ${labels.map(i => `<text x="${x(i)}" y="${H - 9}" class="tick" text-anchor="${i === 0 ? "start" : i === S.length - 1 ? "end" : "middle"}">${short_day(S[i].date)}</text>`).join("")}
    <polyline points="${S.map((s, i) => `${x(i)},${y(s.vrp * 100)}`).join(" ")}" class="vline"/>
    ${S.map((s, i) => `<circle cx="${x(i)}" cy="${y(s.vrp * 100)}" r="4.5" class="pt${s.signal === "flat" ? " flat" : ""}"/>
      <circle cx="${x(i)}" cy="${y(s.vrp * 100)}" r="13" class="hit" data-s="${i}" tabindex="0"/>`).join("")}
  </svg>`;
}

function gauge(p) {
  const hi = p.take ?? -p.stop, lo = p.stop, at = Math.min(Math.max(p.pnl ?? 0, lo), hi);
  const pos = v => ((v - lo) / (hi - lo)) * 100, z = pos(0), m = pos(at);
  const cls = (p.pnl ?? 0) >= 0 ? "r-pass" : "r-fail";
  return `<div class="gauge" aria-label="P&L ${signed(p.pnl)} between stop ${signed(p.stop)} and ${p.take == null ? "no profit take" : `take ${signed(p.take)}`}">
    <div class="gtrack"><span class="gfill ${cls}" style="left:${Math.min(z, m)}%;width:${Math.abs(m - z)}%"></span>
      <span class="gzero" style="left:${z}%"></span><span class="gmark" style="left:${m}%"></span></div>
    <div class="gends"><span>Stop ${signed(p.stop)}</span><span class="gnow ${cls}"><span class="ri">${(p.pnl ?? 0) >= 0 ? "▲" : "▼"}</span> ${signed(p.pnl)}</span>
      <span>${p.take == null ? "No profit take" : `Take ${signed(p.take)}`}</span></div>
  </div>`;
}

function positionHtml(k) {
  const p = k.position;
  const trades = k.trades.map(t => `<tr><td>${short_day(t.date)}</td><td>${t.action === "open" ? "Open" : "Close"}</td>
    <td>${esc(contract(t))}</td><td class="num">$${t.price}</td><td class="num">${t.action === "close" ? signed(t.pnl) : "—"}</td></tr>`).join("");
  const table = k.trades.length ? `<table class="trials dtrades"><thead><tr><th>Date</th><th>Action</th><th>Contract</th><th class="num">Price</th>
    <th class="num">P&amp;L</th></tr></thead><tbody>${trades}</tbody></table>` : `<p class="gs-meta">No trades yet.</p>`;
  const marked = p?.mark_ts ? new Date(p.mark_ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }) + " ET" : "—";
  const head = p ? `<h3 class="colh">Open position</h3>
    <div class="pos-name">${esc(SIDE[p.side].split(" ")[0])} ${+p.strike} ${p.right === "P" ? "put" : "call"} · ${short_day(p.expiry)}</div>
    <dl class="drows"><dt>Entry</dt><dd>$${p.entry_price} on ${short_day(p.entry_date)}</dd><dt>Size</dt><dd>${plural(p.qty, "contract")} · hedge ${p.hedge_shares > 0 ? "+" : "−"}${Math.abs(p.hedge_shares)} SPY</dd>
      <dt>P&amp;L</dt><dd>option ${signed(p.option_pnl)} · hedge ${signed(p.hedge_pnl)} · <b>total ${signed(p.pnl)}</b></dd><dt>Marked</dt><dd>${marked}</dd></dl>
    ${gauge(p)}`
    : `<h3 class="colh">Open position</h3><div class="pos-name">Flat: no open position</div>`;
  return `${head}<h3 class="colh sub">Trades</h3>${table}<p class="gs-meta realized">Realized P&amp;L ${signed(k.realized)}</p>`;
}

function bookChart(B, W) {
  const H = 230, L = 64, R = 70, T = 16, Bm = 30;
  if (!B.length) return `<p class="gs-meta empty">No book history yet.</p>`;
  const vals = B.map(b => b.total ?? 0), span = Math.max(...vals, 0) - Math.min(...vals, 0);
  const pad = Math.max(10, span * 0.25), top = Math.max(...vals, 0) + pad, bot = Math.min(...vals, 0) - pad;
  const x = i => L + (B.length === 1 ? (W - L - R) / 2 : i * (W - L - R) / (B.length - 1));
  const y = v => T + (top - v) * (H - T - Bm) / (top - bot);
  const line = B.map((b, i) => `${x(i)},${y(b.total ?? 0)}`).join(" ");
  const area = `M${x(0)},${y(0)} L${line.replaceAll(" ", " L")} L${x(B.length - 1)},${y(0)} Z`;
  const ticks = [...new Set([0, Math.max(...vals), Math.min(...vals)].map(v => Math.round(v)))];
  const labels = [0, Math.floor((B.length - 1) / 2), B.length - 1].filter((v, i, a) => a.indexOf(v) === i);
  const lastV = vals.at(-1);
  return `<svg class="dchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Book P&L over ${B.length} days, now ${signed(lastV)}">
    ${ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="${v === 0 ? "band" : "base"}"/>
      <text x="${L - 8}" y="${y(v) + 4}" class="tick" text-anchor="end">${signed(v)}</text>`).join("")}
    ${labels.map(i => `<text x="${x(i)}" y="${H - 9}" class="tick" text-anchor="${i === 0 ? "start" : i === B.length - 1 ? "end" : "middle"}">${short_day(B[i].date)}</text>`).join("")}
    <path d="${area}" class="barea ${lastV < 0 ? "neg" : "pos"}"/>
    <polyline points="${line}" class="vline"/>
    <circle cx="${x(B.length - 1)}" cy="${y(lastV)}" r="5" class="pt"/>
    <text x="${x(B.length - 1) + 10}" y="${y(lastV) + 4}" class="endlab">${signed(lastV)}</text>
    ${B.map((b, i) => `<circle cx="${x(i)}" cy="${y(b.total ?? 0)}" r="12" class="hit" data-b="${i}" tabindex="0"/>`).join("")}
  </svg>`;
}

function hoverTip(box, tip, render) {
  const show = el => {
    const [head, body] = render(el), title = document.createElement("div"), meta = document.createElement("div");
    title.className = "t";
    title.textContent = head;
    meta.className = "m";
    meta.textContent = body;
    tip.replaceChildren(title, meta);
    tip.hidden = false;
    const c = box.getBoundingClientRect(), b = el.getBoundingClientRect();
    tip.style.left = `${Math.min(Math.max(b.left - c.left - 40, 8), c.width - tip.offsetWidth - 8)}px`;
    tip.style.top = `${b.top - c.top - tip.offsetHeight - 6}px`;
  };
  box.addEventListener("pointerover", e => { const h = e.target.closest(".hit"); h ? show(h) : (tip.hidden = true); });
  box.addEventListener("pointerleave", () => { tip.hidden = true; });
  box.addEventListener("focusin", e => { const h = e.target.closest(".hit"); if (h) show(h); });
  box.addEventListener("focusout", () => { tip.hidden = true; });
}

function desk() {
  const k = D.desk;
  if (!k) return;
  $("#desk").hidden = false;
  const last = k.signals.at(-1), p = k.position, r = k.rules, book = k.book || [];
  const total = book.at(-1)?.total ?? k.realized;
  const when = k.asof ? new Date(k.asof).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }) + " ET" : "—";
  $("#desk-meta").textContent = `Paper account · updated ${when}`;
  const tiles = [
    [last ? SIDE[last.signal] : "—", last ? `${long_day(last.date)} · VRP ${pts(last.vrp)}` : "no signal yet"],
    [last ? `${pct(last.iv)} vs ${pct(last.rv_forecast)}` : "—", "implied vol vs RV forecast"],
    [p ? `${SIDE[p.side].split(" ")[0]} ${+p.strike} ${p.right === "P" ? "put" : "call"}` : "Flat", p ? `${short_day(p.expiry)} expiry · ${p.dte} DTE` : "no open position"],
    [signed(total), `book P&L · realized ${signed(k.realized)} · open ${signed(p ? p.pnl : 0)}`],
  ];
  $("#desk-stats").innerHTML = tiles.map(([n, l]) => `<div class="dstat"><div class="dnum">${esc(n)}</div><div class="gs-meta">${esc(l)}</div></div>`).join("");
  $("#book-note").textContent = book.length ? `Realized plus open P&L, option and hedge, since ${short_day(book[0].date)}. Days without a position count realized only.` : "";
  const draw = () => {
    $("#book-chart").innerHTML = bookChart(book, Math.max(300, Math.round($("#book-chart").clientWidth || 900)));
    $("#desk-chart").innerHTML = deskChart(k, Math.max(300, Math.round($("#desk-chart").clientWidth || 560)));
  };
  draw();
  let frame = 0;
  addEventListener("resize", () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(draw); });
  $("#desk-rule-box").open = !PHONE;
  $("#desk-rule").textContent = `Short gamma when implied vol is more than ${r.short_band * 100} pts above the ${r.forecaster.toUpperCase()} forecast, long gamma when more than ${-r.long_band * 100} pts below, otherwise flat. Options near ${r.target_dte} DTE, closed at ${r.exit_dte} DTE; stop at ${r.short_stop_mult}× the credit, profit take at ${r.short_profit_frac * 100}% on shorts.`;
  $("#desk-pos").innerHTML = positionHtml(k);
  hoverTip($(".desk-chart"), $("#d-tip"), el => {
    const s = k.signals[Number(el.dataset.s)];
    return [`${long_day(s.date)} · ${SIDE[s.signal]}`, `VRP ${pts(s.vrp)} · IV ${pct(s.iv)} vs forecast ${pct(s.rv_forecast)} · ${s.dte} DTE`];
  });
  hoverTip($(".desk-book"), $("#b-tip"), el => {
    const b = book[Number(el.dataset.b)];
    return [`${long_day(b.date)} · ${signed(b.total)}`, `realized ${signed(b.realized)} · open ${signed(b.open)}`];
  });
}

chrome();
team();
week();
desk();
experiments();
roadmap();
library();
if (location.hash.startsWith("#card-")) openCard(location.hash.slice(6));
