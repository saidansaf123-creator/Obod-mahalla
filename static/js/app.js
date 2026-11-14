/* Обод маҳалла 2027 — бир бетли интерфейс */
(function () {
  "use strict";

  let D = JSON.parse(document.getElementById("app-data").textContent);
  const META = JSON.parse(document.getElementById("app-meta").textContent);
  let IS_ADMIN = !!META.admin;
  let VERSION = META.version;
  const CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const viewEl = $("[data-view]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Формат ---------- */
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (v, d = 0) => (v == null || isNaN(v)) ? "—" :
    Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })
      .replace(/,/g, " ").replace(".", ",");
  const qty = (v) => v == null ? "—" : Number.isInteger(+v) ? fmt(v, 0) : fmt(v, 3).replace(/0+$/, "").replace(/,$/, "");
  const money = (v) => v == null ? "—" : v >= 1000 ? fmt(v / 1000, 2) + " млрд сўм" : fmt(v, v < 10 ? 2 : 1) + " млн сўм";
  const bln = (v) => fmt((v || 0) / 1000, 2);
  /* Маблағ: 1 млрд дан кам бўлса млн сўмда, кўп бўлса млрд сўмда */
  const moneyPair = (v) => v == null ? ["—", ""] : Math.abs(v) >= 1000 ? [fmt(v / 1000, 2), "млрд сўм"] : [fmt(v, v < 100 ? 2 : 1), "млн сўм"];
  const moneyShort = (v) => { const [a, b] = moneyPair(v || 0); return a + " " + b.replace(" сўм", ""); };
  const moneyTag = (v) => { const [a, b] = moneyPair(v || 0); return `${a} <small>${b.replace(" сўм", "")}</small>`; };
  const mwh = (v, d = 1) => v == null ? "—" : fmt(v / 1000, d);
  const pct = (f, p) => (p ? Math.min(100, (f || 0) / p * 100) : 0);
  const fmtPct = (p) => fmt(p, p > 0 && p < 1 ? 2 : p < 10 && p % 1 ? 1 : 0);
  const loadLevel = (p) => p >= 60 ? "crit" : p >= 50 ? "warn" : "good";
  const vpos = (v) => Math.max(0, Math.min(100, (v - 200) / 60 * 100)).toFixed(2);

  const STATUS = { good: "Яшил", warn: "Сариқ", crit: "Қизил", none: "Маълумот йўқ" };
  const PRIO = { high: "Юқори", medium: "Ўрта", low: "Паст" };
  const GSTATUS = { planned: "Режалаштирилган", in_progress: "Жараёнда", done: "Бажарилди" };
  const LEVEL = { crit: "Қизил", warn: "Сариқ", info: "Маълумот" };

  /* Ёрқин палитра */
  const PALETTE = ["#38bdf8", "#f59e0b", "#22c55e", "#ef4444", "#a855f7", "#14b8a6",
                   "#f97316", "#ec4899", "#84cc16", "#6366f1", "#eab308", "#06b6d4"];
  const CAT_COLOR = { new_gktp: "#ec4899", tr_upgrade: "#f97316", hv_cable: "#6366f1", lv_cable: "#38bdf8",
                      grsh: "#22c55e", other: "#94a3b8" };
  const SC = { good: "#22c55e", warn: "#f59e0b", crit: "#ef4444", none: "#52525b" };
  const FACT_C = "#22c55e";
  const cat = (k) => D.categories[k] || { label: k, icon: "wrench", unit: "" };
  const PF = D.planFields;   // [{key,label,unit}]
  const SHORT = { lv_km: "Паст кабел", hv_km: "Юқори кабел", tr_upgrade: "Трансформатор", new_gktp: "Янги ГКТП", grsh: "ГРШ", cost: "Маблағ" };
  const CAT_SHORT = { new_gktp: "Янги ГКТП", tr_upgrade: "Трансформатор", hv_cable: "Юқори кабел", lv_cable: "Паст кабел", grsh: "ГРШ", other: "Бошқа" };

  /* ---------- Индекслар (маълумот янгиланганда қайта тузилади) ---------- */
  let dById, dBySlug, mById, wById, tById, gById, eByW;
  function indexData() {
    dById = new Map(D.districts.map((d) => [d.id, d]));
    dBySlug = new Map(D.districts.map((d) => [d.slug, d]));
    mById = new Map(D.mahallas.map((m) => [m.id, m]));
    wById = new Map(D.works.map((w) => [w.id, w]));
    tById = new Map(D.tps.map((t) => [t.id, t]));
    gById = new Map(D.goals.map((g) => [g.id, g]));
    eByW = new Map();
    D.entries.forEach((e) => { if (e.w) { if (!eByW.has(e.w)) eByW.set(e.w, []); eByW.get(e.w).push(e); } });
    D.districts.forEach((d, i) => { d.color = PALETTE[i % PALETTE.length]; });
    D.goals.sort((a, b) => mById.get(a.m).name.localeCompare(mById.get(b.m).name, "uz"));
  }
  indexData();

  const district = (id) => dById.get(id);
  const mahalla = (id) => mById.get(id);
  const progressOf = (o) => pct(o.fact.cost, o.plan.cost);

  /* ---------- Кичик компонентлар ---------- */
  const icon = (n) => `<i data-lucide="${n}"></i>`;
  const ring = (p, status, label, size = "") =>
    `<div class="ring ${size ? "ring--" + size : ""} is-${status}" style="--p:${p}"><span>${label}</span></div>`;
  const bar = (p, lvl = "good", color) =>
    `<span class="bar"><i class="is-${lvl}" style="width:${Math.max(0, Math.min(100, p))}%${color ? ";background:" + color : ""}"></i></span>`;
  const loadBar = (p) => bar(p * 1.25, loadLevel(p));
  const pill = (cls, text) => `<span class="pill pill--${cls}">${esc(text)}</span>`;
  const kpi = (ic, label, value, unit, sub, extra = "", tone = 1) => `
    <div class="kpi kpi--t${tone}">
      <div class="kpi__top"><span class="kpi__label">${label}</span><span class="kpi__ic">${icon(ic)}</span></div>
      <div class="kpi__value">${value}${unit ? `<small>${unit}</small>` : ""}</div>
      ${extra}${sub ? `<div class="kpi__sub">${sub}</div>` : ""}
    </div>`;
  const score = (s, status, label = "Саломатлик индекси") => `
    <div class="score">${ring(s, status, fmt(s), "lg")}
      <div><div class="score__label">${label}</div>${pill(status, STATUS[status])}</div></div>`;
  const progressBadge = (p, label = "Ижро") => `
    <div class="score">${ring(p, p >= 100 ? "good" : p > 0 ? "warn" : "crit", fmtPct(p) + "%", "lg")}
      <div><div class="score__label">${label}</div>${pill(p > 0 ? "warn" : "plain", p > 0 ? "Жараёнда" : "Бошланмаган")}</div></div>`;
  const catIcon = (k) => `<span class="row__badge" style="color:${CAT_COLOR[k]};border-color:${CAT_COLOR[k]}66;background:${CAT_COLOR[k]}1a">${icon(cat(k).icon)}</span>`;
  const workQty = (w) => {
    const parts = [];
    if (w.lv) parts.push(qty(w.lv) + " км (0,4 кВ)");
    if (w.hv) parts.push(qty(w.hv) + " км (6–10 кВ)");
    if (w.up) parts.push(qty(w.up) + " та трансформатор");
    if (w.gk) parts.push(qty(w.gk) + " та ГКТП");
    if (w.gr) parts.push(qty(w.gr) + " та ГРШ");
    return parts.join(" · ") || "ҳажм кўрсатилмаган";
  };
  const pfRow = (label, unit, plan, fact, color) => {
    const p = pct(fact, plan);
    const isMoney = unit === "млн сўм";
    return `<div class="pfrow"><span class="pfrow__l">${label}</span>
      <span class="pfrow__t"><i style="width:${p}%;background:${color || FACT_C}"></i></span>
      <span class="pfrow__v"><b>${isMoney ? (fact ? moneyShort(fact) : "0") : qty(fact)}</b> / ${isMoney ? moneyShort(plan) : qty(plan) + " " + unit}</span>
      <span class="pfrow__p">${fmtPct(p)}%</span></div>`;
  };
  const pfBlock = (plan, fact, onlyPlanned = false) => `<div class="pfrows">${PF.filter((f) => !onlyPlanned || f.key === "cost" || plan[f.key] > 0).map((f) =>
    pfRow(SHORT[f.key] || f.label, f.unit, plan[f.key], fact[f.key], f.key === "cost" ? "#fde047" : null)).join("")}</div>`;

  /* ---------- Графиклар ---------- */
  const charts = [];
  function clearCharts() { charts.splice(0).forEach((c) => c.destroy()); }
  /* График «рецепти» canvas'да сақланади — катталаштирилганда қайта чизиш учун */
  function mk(canvas, build) { canvas.__build = build; charts.push(new Chart(canvas, build())); }
  const C = { grid: "rgba(255,255,255,.07)", text: "#a1a1aa", panel: "#131315" };
  const tooltip = { backgroundColor: "#18181b", borderColor: "#3f3f46", borderWidth: 1, titleColor: "#fafafa", bodyColor: "#e4e4e7", padding: 10 };
  const anim = () => (reduceMotion ? false : { duration: 650 });
  const axes = () => ({
    x: { ticks: { color: C.text, font: { size: 10.5 }, autoSkip: false, maxRotation: 50 }, grid: { display: false }, border: { color: C.grid } },
    y: { ticks: { color: C.text, font: { size: 10.5 } }, grid: { color: C.grid }, border: { display: false }, beginAtZero: true },
  });

  /* Режа (рангли устун) ва амалда (яшил устун) */
  function planFactChart(canvas, labels, plan, fact, colors, unit) {
    if (!window.Chart || !canvas) return;
    mk(canvas, () => ({
      type: "bar",
      data: { labels, datasets: [
        { label: "Режа", data: plan, backgroundColor: colors.map((c) => c + "cc"), hoverBackgroundColor: colors, borderRadius: 5, maxBarThickness: 30 },
        { label: "Амалда", data: fact, backgroundColor: FACT_C, borderRadius: 5, maxBarThickness: 30, minBarLength: 2 },
      ] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: anim(), interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", align: "end", labels: { color: C.text, boxWidth: 10, boxHeight: 10, font: { size: 11 } } },
                   tooltip: Object.assign({ callbacks: { label: (c) => ` ${c.dataset.label}: ${fmt(c.parsed.y, 2)} ${unit}` } }, tooltip) },
        scales: axes(),
      },
    }));
  }

  function barChart(canvas, labels, data, colors, label, horizontal = false, fmtFn) {
    if (!window.Chart || !canvas) return;
    mk(canvas, () => ({
      type: "bar",
      data: { labels, datasets: [{ label, data, backgroundColor: colors.map((c) => c + "cc"), hoverBackgroundColor: colors, borderRadius: 5, maxBarThickness: 26 }] },
      options: {
        indexAxis: horizontal ? "y" : "x", responsive: true, maintainAspectRatio: false, animation: anim(),
        plugins: { legend: { display: false },
                   tooltip: Object.assign({ callbacks: { label: (c) => " " + (fmtFn ? fmtFn(horizontal ? c.parsed.x : c.parsed.y) : fmt(horizontal ? c.parsed.x : c.parsed.y, 1)) } }, tooltip) },
        scales: horizontal ? {
          x: { ticks: { color: C.text, font: { size: 10.5 } }, grid: { color: C.grid }, border: { display: false }, beginAtZero: true },
          y: { ticks: { color: C.text, font: { size: 10.5 }, autoSkip: false }, grid: { display: false }, border: { color: C.grid } },
        } : axes(),
      },
    }));
  }

  function donut(canvas, values, colors, labels, fmtFn) {
    if (!window.Chart || !canvas) return;
    mk(canvas, () => ({
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: C.panel, borderWidth: 3, hoverOffset: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "72%", animation: anim(),
                 plugins: { legend: { display: false },
                            tooltip: Object.assign({ callbacks: { label: (c) => " " + c.label + ": " + (fmtFn ? fmtFn(c.parsed) : fmt(c.parsed)) } }, tooltip) } },
    }));
  }

  const legend = (items, scroll = false) => `<ul class="legend ${scroll ? "legend--scroll" : ""}">${items.map(([c, l, v]) =>
    `<li><i class="dot" style="background:${c}"></i>${esc(l)}<b>${v}</b></li>`).join("")}</ul>`;

  /* =========================================================
     Бош саҳифа
     ========================================================= */
  function renderHome() {
    const c = D.city, p = c.plan, f = c.fact, t = c.tp;
    viewEl.innerHTML = `
      <div class="home">
        <div class="head head--home">
          <div>
            <span class="eyebrow">${icon("map-pin")}Тошкент шаҳри · «Обод маҳалла» 2027 манзилли дастури</span>
            <div class="city-line">
              <span><b>${c.districts}</b> та туман</span>
              <span><b>${c.mahallas}</b> та маҳалла</span>
              <span><b>${p.works}</b> та иш</span>
              <span><b>${qty(p.km)}</b> км тармоқ</span>
              <span><b>${p.tr}</b> та трансформатор</span>
              <span><b>${p.grsh}</b> та ГРШ</span>
              <span><b>${bln(p.cost)}</b> млрд сўм</span>
            </div>
          </div>
          <div class="head__right">${progressBadge(progressOf(c), "Ижро (маблағ)")}</div>
        </div>
        <div class="kpis kpis--4">
          ${kpi("coins", "Зарур маблағ", bln(p.cost), "млрд сўм", "", bar(progressOf(c), "good", "#fde047"), 7)}
          ${kpi("plug-zap", "Паст кучланишли кабел", qty(p.lv_km), "км", "", bar(pct(f.lv_km, p.lv_km), "good"), 1)}
          ${kpi("cable", "Юқори кучланишли кабел", qty(p.hv_km), "км", "", bar(pct(f.hv_km, p.hv_km), "good"), 3)}
          ${kpi("circle-arrow-up", "Трансформатор алмаштириш", qty(p.tr_upgrade), "та", "", bar(pct(f.tr_upgrade, p.tr_upgrade), "good"), 6)}
          ${kpi("square-plus", "Янги ГКТП", qty(p.new_gktp), "та", "", bar(pct(f.new_gktp, p.new_gktp), "good"), 8)}
          ${kpi("server", "ГРШ модернизацияси", qty(p.grsh), "та", "", bar(pct(f.grsh, p.grsh), "good"), 2)}
          ${kpi("zap", "ТП секциялари", fmt(t.count), "та", "", "", 4)}
          ${kpi("users", "Истеъмолчилар (ТП)", fmt(t.consumers), "та", "", `<span class="bar bar--split"><i style="width:${t.household_pct || 0}%"></i></span>`, 5)}
        </div>
        <div class="home__grid">
          <div class="card">
            <div class="card__head"><h3>Туманлар бўйича маблағ: режа ва амалда</h3><span class="muted hide-narrow">млн сўм</span></div>
            <div class="chart"><canvas id="ch-districts"></canvas></div>
          </div>
          <div class="card status-card">
            <div class="card__head"><h3>Ишлар таркиби</h3><span class="muted">${p.works} та</span></div>
            <div class="donut"><canvas id="ch-cats"></canvas><div class="donut__c"><b>${bln(p.cost)}</b><span>млрд сўм</span></div></div>
            ${legend(c.cats.map((k) => [CAT_COLOR[k.kind], CAT_SHORT[k.kind] + " (" + k.count + ")", moneyShort(k.cost)]), true)}
          </div>
          <div class="card">
            <div class="card__head"><h3>Режа ижроси</h3><a class="muted" href="#/progress">Батафсил</a></div>
            <div class="card__body">${pfBlock(p, f)}
              <p class="muted small" style="margin-top:12px">${f.done} / ${p.works} иш тўлиқ бажарилган · амалдаги қийматлар админ панелдан киритилади</p>
            </div>
          </div>
        </div>
      </div>`;
    planFactChart($("#ch-districts"), D.districts.map((d) => d.name), D.districts.map((d) => d.plan.cost),
      D.districts.map((d) => d.fact.cost), D.districts.map((d) => d.color), "млн сўм");
    donut($("#ch-cats"), c.cats.map((k) => k.cost), c.cats.map((k) => CAT_COLOR[k.kind]), c.cats.map((k) => cat(k.kind).label), money);
    return [["Тошкент шаҳри"]];
  }

  /* =========================================================
     Рўйхат + батафсил (умумий механизм)
     ========================================================= */
  const listState = {};

  const LISTS = {
    districts: {
      title: "Туманлар",
      items: () => D.districts,
      key: (d) => d.slug,
      find: (k) => dBySlug.get(k),
      search: (d) => d.name + " " + d.lat + " " + d.res,
      tools: () => sortSelect([["order", "Файл тартиби"], ["name", "Номи бўйича"], ["cost", "Маблағ"], ["works", "Ишлар сони"], ["km", "Тармоқ, км"]]),
      sort: { order: null, name: (a, b) => a.name.localeCompare(b.name, "uz"), cost: (a, b) => b.plan.cost - a.plan.cost,
              works: (a, b) => b.plan.works - a.plan.works, km: (a, b) => b.plan.km - a.plan.km },
      row: (d) => `
        <span class="row__badge" style="color:${d.color};border-color:${d.color}66;background:${d.color}1a">${esc(d.roman)}</span>
        <div class="row__body"><span class="row__title">${esc(d.name)}</span>
          <span class="row__sub">${d.mahallas.length} маҳалла · ${d.plan.works} иш · ${qty(d.plan.km)} км</span></div>
        <div class="row__side"><span class="t-money nowrap">${moneyTag(d.plan.cost)}</span></div>`,
      detail: districtDetail,
      total: {
        row: () => `
          <span class="row__badge row__badge--total">${icon("building-2")}</span>
          <div class="row__body"><span class="row__title">Тошкент шаҳри</span>
            <span class="row__sub">Жами · ${D.city.mahallas} маҳалла · ${D.city.plan.works} иш</span></div>
          <div class="row__side"><span class="t-money nowrap">${moneyTag(D.city.plan.cost)}</span></div>`,
        detail: cityDetail,
      },
      summary: () => `${D.districts.length} та туман`,
    },
    mahallas: {
      title: "Маҳаллалар",
      items: () => D.mahallas,
      key: (m) => String(m.id),
      find: (k) => mById.get(+k),
      search: (m) => m.name + " " + m.lat + " " + district(m.d).name,
      filters: { district: (m, v) => String(m.d) === v },
      tools: () => districtSelect() + sortSelect([["order", "Файл тартиби"], ["name", "Номи бўйича"], ["cost", "Маблағ"], ["works", "Ишлар сони"], ["km", "Тармоқ, км"], ["tps", "ТП секциялари"]]),
      sort: { order: null, name: (a, b) => a.name.localeCompare(b.name, "uz"), cost: (a, b) => b.plan.cost - a.plan.cost,
              works: (a, b) => b.plan.works - a.plan.works, km: (a, b) => b.plan.km - a.plan.km, tps: (a, b) => b.tps.length - a.tps.length },
      row: (m) => {
        const g = gById.get(m.goal);
        return `
          ${g ? `<i class="dot dot--${g.priority}" title="${PRIO[g.priority]} устуворлик"></i>` : `<i class="dot dot--muted"></i>`}
          <div class="row__body"><span class="row__title">${esc(m.name)}</span>
            <span class="row__sub">${esc(district(m.d).name)} · ${m.plan.works} иш · ${m.tps.length} ТП</span></div>
          <div class="row__side"><span class="t-money nowrap">${moneyTag(m.plan.cost)}</span></div>`;
      },
      detail: mahallaDetail,
      total: {
        row: () => `
          <span class="row__badge row__badge--total">${icon("sigma")}</span>
          <div class="row__body"><span class="row__title">Жами</span>
            <span class="row__sub">Барча ${D.mahallas.length} маҳалла · ${D.city.plan.works} иш</span></div>
          <div class="row__side"><span class="t-money nowrap">${moneyTag(D.city.plan.cost)}</span></div>`,
        detail: mahallaTotal,
      },
      summary: () => `${D.mahallas.length} та маҳалла`,
    },
    works: {
      title: "Ишлар",
      items: () => D.works,
      key: (w) => String(w.id),
      find: (k) => wById.get(+k),
      search: (w) => `№${w.no} ${w.text} ${mahalla(w.m).name} ${mahalla(w.m).lat} ${district(w.d).name} ${w.tp} ${w.cable}`,
      filters: { district: (w, v) => String(w.d) === v, cat: (w, v) => w.cat === v,
                 flag: (w, v) => (v === "tp" ? w.secs.length > 0 : v === "cost" ? w.cost != null : true) },
      tools: () => districtSelect() +
        `<div class="tools__row"><label class="field">${icon("layers")}<select data-f="cat" aria-label="Тоифа">
          <option value="">Барча тоифалар</option>${Object.keys(D.categories).filter((k) => D.works.some((w) => w.cat === k))
            .map((k) => `<option value="${k}">${esc(cat(k).label)}</option>`).join("")}</select></label></div>` +
        segFilter("flag", [["", "Ҳаммаси"], ["tp", "ТП маълумоти бор"]]) +
        sortSelect([["order", "Файл тартиби"], ["cost", "Маблағ (кўпдан)"], ["km", "Тармоқ, км"], ["mahalla", "Маҳалла"]]),
      sort: { order: null, cost: (a, b) => (b.cost || 0) - (a.cost || 0), km: (a, b) => ((b.lv || 0) + (b.hv || 0)) - ((a.lv || 0) + (a.hv || 0)),
              mahalla: (a, b) => mahalla(a.m).name.localeCompare(mahalla(b.m).name, "uz") },
      row: (w) => `
        ${catIcon(w.cat)}
        <div class="row__body"><span class="row__title">№${w.no} · ${esc(w.title)}</span>
          <span class="row__sub">${esc(mahalla(w.m).name)} · ${esc(district(w.d).name)}</span></div>
        <div class="row__side"><span class="t-money nowrap">${w.cost == null ? "—" : moneyTag(w.cost)}</span></div>`,
      detail: workDetail,
      summary: () => `${D.works.length} та · ${moneyShort(D.city.plan.cost)}`,
    },
    tps: {
      title: "Трансформаторлар",
      items: () => D.tps,
      key: (t) => String(t.id),
      find: (k) => tById.get(+k),
      search: (t) => `тп-${t.n} tp-${t.n} ${t.n} ${mahalla(t.m).name} ${mahalla(t.m).lat} ${t.ps} ${t.fd} ${t.mtr}`,
      filters: { district: (t, v) => String(t.d) === v, status: (t, v) => t.status === v },
      tools: () => districtSelect() + segFilter("status", [["", "Барчаси"], ["good", "Яшил"], ["warn", "Сариқ"], ["crit", "Қизил"]]) +
        sortSelect([["order", "Файл тартиби"], ["load", "Юкланиш"], ["score", "Саломатлик (пастдан)"], ["consumers", "Истеъмолчилар"], ["kwh", "Кунлик истеъмол"]]),
      sort: { order: null, load: (a, b) => (b.lf || 0) - (a.lf || 0), consumers: (a, b) => b.ct - a.ct,
              score: (a, b) => (a.score == null ? 999 : a.score) - (b.score == null ? 999 : b.score), kwh: (a, b) => (b.dk || 0) - (a.dk || 0) },
      row: (t) => `
        ${ring(Math.min(100, (t.lf || 0) * 100), t.status, t.data ? Math.round((t.lf || 0) * 100) + "%" : "—", "xs")}
        <div class="row__body"><span class="row__title">ТП-${esc(t.n)}</span>
          <span class="row__sub">${t.cap ? t.cap + " кВА · " : ""}${esc(mahalla(t.m).name)} · ${esc(district(t.d).name)}</span></div>
        <div class="row__side">${pill(t.status, STATUS[t.status])}</div>`,
      detail: tpDetail,
      summary: () => `${D.tps.length} та`,
    },
    goals: {
      title: "Мақсадлар",
      items: () => D.goals,
      key: (g) => String(g.id),
      find: (k) => gById.get(+k),
      search: (g) => g.title + " " + mahalla(g.m).name + " " + mahalla(g.m).lat + " " + district(mahalla(g.m).d).name,
      filters: { district: (g, v) => String(mahalla(g.m).d) === v, priority: (g, v) => g.priority === v },
      tools: () => districtSelect() + segFilter("priority", [["", "Барчаси"], ["high", "Юқори"], ["medium", "Ўрта"], ["low", "Паст"]]) +
        sortSelect([["name", "Маҳалла номи"], ["budget", "Бюджет"], ["prio", "Устуворлик"]]),
      sort: { name: null, budget: (a, b) => b.budget - a.budget,
              prio: (a, b) => ({ high: 0, medium: 1, low: 2 }[a.priority] - { high: 0, medium: 1, low: 2 }[b.priority]) },
      row: (g) => {
        const m = mahalla(g.m);
        return `
          <i class="dot dot--${g.priority}" title="${PRIO[g.priority]} устуворлик"></i>
          <div class="row__body"><span class="row__title">${esc(m.name)} <span class="muted small">· ${esc(district(m.d).name)}</span></span>
            <span class="row__sub">${esc(g.title)}</span></div>
          <div class="row__side"><span class="t-money nowrap">${moneyTag(g.budget)}</span></div>`;
      },
      detail: goalDetail,
      summary: () => `${D.goals.length} та мақсад`,
    },
  };

  LISTS.admin = {
    title: "Ижро киритиш",
    items: () => D.works,
    key: (w) => String(w.id),
    find: (k) => wById.get(+k),
    search: (w) => `№${w.no} ${w.text} ${mahalla(w.m).name} ${mahalla(w.m).lat} ${district(w.d).name}`,
    filters: { district: (w, v) => String(w.d) === v, st: (w, v) => workState(w) === v },
    tools: () => districtSelect() +
      `<div class="tools__row"><label class="field">${icon("list-filter")}<select data-f="st" aria-label="Ҳолат">
        <option value="">Барча ҳолатлар</option><option value="todo">Бошланмаган</option><option value="doing">Жараёнда</option><option value="done">Бажарилган</option></select></label></div>` +
      sortSelect([["order", "Файл тартиби"], ["cost", "Маблағ (кўпдан)"], ["recent", "Охирги киритилган"], ["progress", "Ижро % (кўпдан)"]]),
    sort: { order: null, cost: (a, b) => (b.cost || 0) - (a.cost || 0),
            recent: (a, b) => (b.upd || "").localeCompare(a.upd || ""),
            progress: (a, b) => pct(b.f.cost, b.cost) - pct(a.f.cost, a.cost) },
    row: (w) => {
      const st = workState(w), pr = pct(w.f.cost, w.cost);
      return `
        <i class="dot dot--${st === "done" ? "low" : st === "doing" ? "medium" : "muted"}" title="${WSTATE[st][0]}"></i>
        <div class="row__body"><span class="row__title">№${w.no} · ${esc(mahalla(w.m).name)}</span>
          <span class="row__sub">${esc(w.title)}</span></div>
        <div class="row__side row__side--col"><span class="t-money nowrap">${w.cost == null ? "—" : moneyTag(w.cost)}</span><span class="muted small">${fmtPct(pr)}%</span></div>`;
    },
    detail: adminDetail,
    summary: () => `${D.works.filter((w) => workState(w) === "done").length} / ${D.works.length} бажарилган`,
  };

  function districtSelect() {
    return `<div class="tools__row"><label class="field">${icon("map")}<select data-f="district" aria-label="Туман">
      <option value="">Барча туманлар</option>
      ${D.districts.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("")}</select></label></div>`;
  }
  function sortSelect(opts) {
    return `<div class="tools__row"><label class="field">${icon("arrow-up-down")}<select data-sort aria-label="Саралаш">
      ${opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label></div>`;
  }
  function segFilter(field, opts) {
    return `<div class="seg" role="group">${opts.map(([v, l], i) =>
      `<button type="button" data-seg="${field}" data-v="${v}" class="${i === 0 ? "is-active" : ""}">${l}</button>`).join("")}</div>`;
  }

  function filtered(name) {
    const cfg = LISTS[name], st = listState[name];
    const q = st.q.trim().toLowerCase();
    let items = cfg.items().filter((it) => {
      if (q && !cfg.search(it).toLowerCase().includes(q)) return false;
      for (const f in st.f) if (st.f[f] && !cfg.filters[f](it, st.f[f])) return false;
      return true;
    });
    const sorter = cfg.sort && cfg.sort[st.sort];
    if (sorter) items = items.slice().sort(sorter);
    return items;
  }

  function renderMD(name, key) {
    const cfg = LISTS[name];
    const st = listState[name] || (listState[name] = { q: "", f: {}, sort: Object.keys(cfg.sort)[0] });
    viewEl.innerHTML = `
      <div class="md">
        <section class="pane">
          <div class="pane__head">
            <div class="pane__title"><h2>${cfg.title}</h2><span>${cfg.summary()}</span></div>
            <div class="tools">
              <label class="field">${icon("search")}<input type="search" data-q placeholder="Рўйхатдан қидириш…" value="${esc(st.q)}"></label>
              ${cfg.tools ? cfg.tools() : ""}
            </div>
          </div>
          <div class="list" data-list tabindex="-1"></div>
          <div class="list-foot"><span data-shown></span><span>↑ ↓ — танлаш</span></div>
        </section>
        <section class="detail" data-detail></section>
      </div>`;
    $$("[data-f]", viewEl).forEach((s) => { s.value = st.f[s.dataset.f] || ""; });
    $$("[data-seg]", viewEl).forEach((b) => b.classList.toggle("is-active", (st.f[b.dataset.seg] || "") === b.dataset.v));
    const sortEl = $("[data-sort]", viewEl);
    if (sortEl) sortEl.value = st.sort;

    $("[data-q]", viewEl).addEventListener("input", (e) => { st.q = e.target.value; fillList(name); });
    $$("[data-f]", viewEl).forEach((s) => s.addEventListener("change", () => { st.f[s.dataset.f] = s.value; fillList(name); }));
    $$("[data-seg]", viewEl).forEach((b) => b.addEventListener("click", () => {
      $$(`[data-seg="${b.dataset.seg}"]`, viewEl).forEach((x) => x.classList.toggle("is-active", x === b));
      st.f[b.dataset.seg] = b.dataset.v; fillList(name);
    }));
    if (sortEl) sortEl.addEventListener("change", () => { st.sort = sortEl.value; fillList(name); });

    fillList(name);
    return showDetail(name, key);
  }

  function fillList(name) {
    const cfg = LISTS[name];
    const items = filtered(name);
    const list = $("[data-list]", viewEl);
    const total = cfg.total ? `<a href="#/${name}/all" class="row row--total" data-key="all">${cfg.total.row()}</a>` : "";
    list.innerHTML = total + (items.length
      ? items.map((it) => `<a href="#/${name}/${cfg.key(it)}" class="row" data-key="${cfg.key(it)}">${cfg.row(it)}</a>`).join("")
      : `<div class="empty">${icon("search-x")}<span>Ҳеч нарса топилмади</span></div>`);
    $("[data-shown]", viewEl).textContent = `${items.length} та кўрсатилмоқда`;
    markActive(name);
    icons();
  }

  function markActive(name) {
    const key = listState[name].active;
    $$(".row", viewEl).forEach((r) => {
      const on = r.dataset.key === key;
      r.classList.toggle("is-active", on);
      if (on) r.scrollIntoView({ block: "nearest" });
    });
  }

  function showDetail(name, key) {
    const cfg = LISTS[name];
    clearCharts();
    const det = $("[data-detail]", viewEl);
    let crumbs;
    if (cfg.total && (!key || key === "all")) {
      listState[name].active = "all";
      crumbs = cfg.total.detail(det);
    } else {
      let item = key ? cfg.find(key) : null;
      if (!item) item = filtered(name)[0] || cfg.items()[0];
      listState[name].active = cfg.key(item);
      crumbs = cfg.detail(item, det);
    }
    markActive(name);
    det.scrollTop = 0;
    return crumbs;
  }

  /* ---------- Умумий бўлаклар ---------- */
  const planKpis = (p, f, extra = "") => `
    ${kpi("coins", "Зарур маблағ", moneyPair(p.cost)[0], moneyPair(p.cost)[1], `амалда ${moneyShort(f.cost)}`, "", 7)}
    ${kpi("plug-zap", "Паст кучланишли кабел", qty(p.lv_km), "км", `амалда ${qty(f.lv_km)} км`, "", 1)}
    ${kpi("cable", "Юқори кучланишли кабел", qty(p.hv_km), "км", `амалда ${qty(f.hv_km)} км`, "", 3)}
    ${kpi("circle-arrow-up", "Трансформаторлар", qty(p.tr), "та", `${qty(p.tr_upgrade)} алмаштириш · ${qty(p.new_gktp)} ГКТП`, "", 6)}
    ${kpi("server", "ГРШ", qty(p.grsh), "та", `амалда ${qty(f.grsh)}`, "", 2)}
    ${extra}`;

  const worksTable = (ws, showMahalla = false) => ws.length ? `
    <table class="tbl tbl--wrap"><thead><tr><th>№</th>${showMahalla ? "<th>Маҳалла</th>" : ""}<th>Иш</th><th>Ҳажм</th><th class="r">Маблағ, млн</th></tr></thead>
      <tbody>${ws.map((w) => `<tr data-href="#/works/${w.id}">
        <td class="muted">${w.no}</td>${showMahalla ? `<td><b>${esc(mahalla(w.m).name)}</b></td>` : ""}
        <td class="titlecell"><span class="wcell"><i class="dot" style="background:${CAT_COLOR[w.cat]}"></i>${esc(w.title)}</span></td>
        <td class="qtycell">${esc(workQty(w))}</td><td class="r t-money nowrap">${w.cost == null ? "—" : fmt(w.cost, 2)}</td></tr>`).join("")}</tbody></table>`
    : `<div class="empty">Ишлар йўқ</div>`;

  const tpTable = (tps, compact = false) => tps.length ? `
    <table class="tbl"><thead><tr><th>ТП</th><th class="r">Қувват</th>${compact ? "" : '<th class="r">Истеъм.</th>'}<th class="r">Юкланиш</th></tr></thead>
      <tbody>${tps.map((t) => `<tr data-href="#/tps/${t.id}">
        <td class="nowrap"><i class="dot" style="background:${SC[t.status]}"></i> <b>ТП-${esc(t.n)}</b></td><td class="r">${t.cap ? t.cap + " кВА" : "—"}</td>${compact ? "" : `<td class="r">${t.ct}</td>`}
        <td class="r t-${t.status}">${t.data ? fmt((t.lf || 0) * 100, 1) + "%" : "—"}${t.after ? ` <span class="muted">→ ${fmt(t.after.lf * 100, 1)}%</span>` : ""}</td></tr>`).join("")}</tbody></table>`
    : `<div class="empty">${icon("cable")}<span>ТП тизим маълумоти бириктирилмаган.</span></div>`;

  function catBars(cats) {
    const max = Math.max(...cats.map((c) => c.cost), 1);
    return `<div class="catbars">${cats.map((c) => `
      <div class="catbar"><span class="catbar__l" title="${esc(cat(c.kind).label)}"><i class="dot" style="background:${CAT_COLOR[c.kind]}"></i>${esc(CAT_SHORT[c.kind])}</span>
        <span class="catbar__t"><i style="width:${(c.cost / max * 100).toFixed(1)}%;background:${CAT_COLOR[c.kind]}"></i></span>
        <b>${fmt(c.cost, c.cost < 100 ? 1 : 0)}</b></div>`).join("")}</div>`;
  }

  /* Варақалар (ТП, маҳалла) */
  const tabState = {};
  function tabs(el, name, defs) {
    const st = tabState[name] && defs.some((d) => d[0] === tabState[name]) ? tabState[name] : defs[0][0];
    const btns = `<div class="seg seg--tabs">${defs.map(([k, l]) => `<button type="button" data-tabbtn="${k}" class="${k === st ? "is-active" : ""}">${l}</button>`).join("")}</div>`;
    const bind = () => $$("[data-tabbtn]", el).forEach((btn) => btn.addEventListener("click", () => {
      tabState[name] = btn.dataset.tabbtn;
      $$("[data-tabbtn]", el).forEach((x) => x.classList.toggle("is-active", x === btn));
      $$("[data-tab]", el).forEach((x) => { x.hidden = x.dataset.tab !== tabState[name]; });
    }));
    return { btns, bind, hidden: (k) => (k === st ? "" : "hidden") };
  }

  /* ---------- Тошкент шаҳри (жами) ---------- */
  function cityDetail(el) {
    const c = D.city, p = c.plan, f = c.fact;
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("building-2")}Жами · ${c.districts} та туман</span>
          <h1>Тошкент шаҳри</h1>
          <div class="head__sub">${c.mahallas} та маҳалла · ${p.works} та иш · ${D.tps.length} та ТП секцияси · ${fmt(c.tp.consumers)} истеъмолчи</div>
        </div>
        <div class="head__right">${progressBadge(progressOf(c))}</div>
      </div>
      <div class="kpis kpis--6">${planKpis(p, f, kpi("users", "Истеъмолчилар (ТП)", fmt(c.tp.consumers), "", `${c.tp.with_data} секция · юкланиш ${fmt(c.tp.load_pct, 1)}%`, "", 5))}</div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Туманлар</h3><span class="muted">Туманни танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Туман</th><th class="r">Маҳалла</th><th class="r">Ишлар</th><th class="r">Км</th><th class="r">Тр.</th><th class="r">Маблағ, млн</th></tr></thead>
              <tbody>${D.districts.map((d) => `<tr data-href="#/districts/${d.slug}">
                <td><i class="dot" style="background:${d.color}"></i> <b>${esc(d.name)}</b></td><td class="r">${d.mahallas.length}</td>
                <td class="r">${d.plan.works}</td><td class="r">${qty(d.plan.km)}</td><td class="r">${d.plan.tr}</td>
                <td class="r t-money">${fmt(d.plan.cost, 1)}</td></tr>`).join("")}
                <tr class="tr-total"><td><b>Жами</b></td><td class="r"><b>${c.mahallas}</b></td><td class="r"><b>${p.works}</b></td>
                  <td class="r"><b>${qty(p.km)}</b></td><td class="r"><b>${p.tr}</b></td><td class="r t-money"><b>${fmt(p.cost, 1)}</b></td></tr></tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Туманлар маблағи: режа ва амалда</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-city"></canvas></div>
        </div>
      </div>`;
    planFactChart($("#ch-city", el), D.districts.map((d) => d.name), D.districts.map((d) => d.plan.cost),
      D.districts.map((d) => d.fact.cost), D.districts.map((d) => d.color), "млн сўм");
    return [["Тошкент", "#/home"], ["Туманлар", "#/districts"], ["Тошкент шаҳри (жами)"]];
  }

  /* ---------- Туман ---------- */
  function districtDetail(d, el) {
    const p = d.plan, f = d.fact;
    const ms = d.mahallas.map(mahalla);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("map")}${esc(d.roman)} · Туман</span>
          <h1>${esc(d.name)} тумани</h1>
          <div class="head__sub">${d.res ? "РЭС: " + esc(d.res) + " · " : ""}${ms.length} та маҳалла · ${p.works} та иш · ${d.tp.count} та ТП секцияси</div>
        </div>
        <div class="head__right">${progressBadge(progressOf(d))}</div>
      </div>
      <div class="kpis kpis--6">${planKpis(p, f, kpi("users", "Истеъмолчилар (ТП)", d.tp.consumers ? fmt(d.tp.consumers) : "—", "", d.tp.with_data ? `${d.tp.with_data} секция · юкланиш ${fmt(d.tp.load_pct, 1)}%` : "ТП маълумоти йўқ", "", 5))}</div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Маҳаллалар</h3><span class="muted">Маҳаллани танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Маҳалла</th><th class="r">Ишлар</th><th class="r">Км</th><th class="r">Тр.</th><th class="r hide-narrow">ГРШ</th><th class="r">Маблағ, млн</th></tr></thead>
              <tbody>${ms.map((m) => {
                const g = gById.get(m.goal);
                return `<tr data-href="#/mahallas/${m.id}">
                  <td>${g ? `<i class="dot dot--${g.priority}"></i> ` : ""}<b>${esc(m.name)}</b></td><td class="r">${m.plan.works}</td>
                  <td class="r">${qty(m.plan.km)}</td><td class="r">${m.plan.tr || "—"}</td><td class="r hide-narrow">${m.plan.grsh || "—"}</td>
                  <td class="r t-money">${fmt(m.plan.cost, 1)}</td></tr>`;
              }).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Маҳаллалар маблағи: режа ва амалда</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-d"></canvas></div>
        </div>
      </div>`;
    planFactChart($("#ch-d", el), ms.map((m) => m.name), ms.map((m) => m.plan.cost), ms.map((m) => m.fact.cost),
      ms.map((_, i) => PALETTE[i % PALETTE.length]), "млн сўм");
    return [["Тошкент", "#/home"], ["Туманлар", "#/districts"], [d.name]];
  }

  /* ---------- Барча маҳаллалар (жами) ---------- */
  function mahallaTotal(el) {
    const c = D.city, p = c.plan, f = c.fact;
    const pr = { high: 0, medium: 0, low: 0 };
    D.goals.forEach((g) => { pr[g.priority]++; });
    const ms = D.mahallas.slice().sort((a, b) => b.plan.cost - a.plan.cost);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("sigma")}Жами · «Обод маҳалла» 2027</span>
          <h1>Барча маҳаллалар</h1>
          <div class="head__sub">${c.mahallas} та маҳалла · ${p.works} та иш · ўртача ${fmt(p.cost / c.mahallas, 1)} млн сўм / маҳалла</div>
        </div>
        <div class="head__right">${progressBadge(progressOf(c))}</div>
      </div>
      <div class="kpis kpis--6">${planKpis(p, f, kpi("list-checks", "Юқори устуворлик", pr.high, "та", `${pr.medium} ўрта · ${pr.low} паст`, "", 8))}</div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Маҳаллалар (маблағ бўйича)</h3><span class="muted">Маҳаллани танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Маҳалла</th><th class="hide-narrow">Туман</th><th class="r">Ишлар</th><th class="r">Км</th><th class="r">Маблағ, млн</th></tr></thead>
              <tbody>${ms.map((m) => {
                const g = gById.get(m.goal);
                return `<tr data-href="#/mahallas/${m.id}"><td>${g ? `<i class="dot dot--${g.priority}"></i> ` : ""}<b>${esc(m.name)}</b></td>
                  <td class="hide-narrow">${esc(district(m.d).name)}</td><td class="r">${m.plan.works}</td><td class="r">${qty(m.plan.km)}</td>
                  <td class="r t-money">${fmt(m.plan.cost, 1)}</td></tr>`;
              }).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Маблағи энг катта 12 маҳалла</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-mt"></canvas></div>
        </div>
      </div>`;
    const top = ms.slice(0, 12);
    barChart($("#ch-mt", el), top.map((m) => m.name), top.map((m) => m.plan.cost), top.map((m) => district(m.d).color), "Маблағ", true, money);
    return [["Тошкент", "#/home"], ["Маҳаллалар", "#/mahallas"], ["Жами"]];
  }

  /* ---------- Маҳалла ---------- */
  function mahallaDetail(m, el) {
    const p = m.plan, f = m.fact, d = district(m.d), g = gById.get(m.goal);
    const ws = m.works.map((id) => wById.get(id));
    const tps = m.tps.map((id) => tById.get(id));
    const t = tabs(el, "mahalla", [["works", `Ишлар (${ws.length})`], ["tps", `ТП (${tps.length})`], ["goal", "Мақсад"]]);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("house")}Маҳалла</span>
          <h1>${esc(m.name)} маҳалласи</h1>
          <div class="head__sub"><a href="#/districts/${d.slug}">${esc(d.name)} тумани</a> · ${ws.length} та иш · ${tps.length} та ТП секцияси
            ${g ? pill(g.priority, PRIO[g.priority] + " устуворлик") : ""}</div>
        </div>
        <div class="head__right">${t.btns}${progressBadge(progressOf(m))}</div>
      </div>
      <div class="kpis kpis--6">${planKpis(p, f, kpi("users", "Истеъмолчилар (ТП)", m.tp.consumers ? fmt(m.tp.consumers) : "—", "", m.tp.with_data ? `юкланиш ${fmt(m.tp.load_pct, 1)}%` : "ТП маълумоти йўқ", "", 5))}</div>
      <div class="dgrid dgrid--2" data-tab="works" ${t.hidden("works")}>
        <div class="card"><div class="card__head"><h3>Режадаги ишлар</h3><span class="muted">Ишни танланг</span></div>
          <div class="card__body">${worksTable(ws)}</div></div>
        <div class="card"><div class="card__head"><h3>Режа ижроси</h3></div>
          <div class="card__body">${pfBlock(p, f, true)}<div style="margin-top:14px">${catBars(m.cats)}</div></div></div>
      </div>
      <div class="dgrid dgrid--2" data-tab="tps" ${t.hidden("tps")}>
        <div class="card"><div class="card__head"><h3>ТП секциялари</h3><span class="muted">${tps.length ? "ТП ни танланг" : ""}</span></div>
          <div class="card__body">${tpTable(tps)}</div></div>
        <div class="card"><div class="card__head"><h3>ТП кўрсаткичлари</h3></div>
          <div class="card__body">${m.tp.with_data ? `<div class="facts">
            <div><span>Ўрнатилган қувват</span><b>${fmt(m.tp.capacity_kva)} кВА</b></div>
            <div><span>Жами юклама</span><b>${fmt(m.tp.actual_kva, 1)} кВА</b></div>
            <div><span>Кунлик истеъмол</span><b>${fmt(m.tp.daily_kwh, 0)} кВт·с</b></div>
            <div><span>Ойлик истеъмол</span><b>${mwh(m.tp.monthly_kwh)} МВт·с</b></div>
            <div><span>Ўртача кучланиш</span><b>${fmt(m.tp.avg_voltage, 1)} В</b></div>
            <div><span>Ўртача cos φ</span><b>${fmt(m.tp.avg_pf, 3)}</b></div>
            <div><span>Аҳоли / саноат</span><b>${fmt(m.tp.household)} / ${fmt(m.tp.commercial)}</b></div>
            <div><span>Яшил / сариқ / қизил</span><b>${m.tp.good} / ${m.tp.warn} / ${m.tp.crit}</b></div></div>`
            : `<div class="empty">${icon("cable")}<span>Бу маҳалла ишларида ТП тизим маълумоти берилмаган.</span></div>`}</div></div>
      </div>
      <div class="dgrid dgrid--2" data-tab="goal" ${t.hidden("goal")}>
        <div class="card"><div class="card__head"><h3>Маҳалла мақсади · 2027</h3>${g ? pill(g.priority, PRIO[g.priority]) : ""}</div>
          ${g ? `<div class="card__body goal-brief"><h2>${esc(g.title)}</h2><p class="quote">${esc(g.summary)}</p>
            <div><a class="btn btn--gold" href="#/goals/${g.id}">${icon("arrow-right")}Мақсад батафсил</a></div></div>` : `<div class="empty">Мақсад йўқ</div>`}</div>
        <div class="card"><div class="card__head"><h3>Кутилаётган натижалар</h3></div>
          <div class="card__body">${g ? `<ul class="effects">${g.effects.map((e) => `<li>${icon("circle-check")}<span>${esc(e)}</span></li>`).join("")}</ul>` : ""}</div></div>
      </div>`;
    t.bind();
    return [["Тошкент", "#/home"], [d.name, "#/districts/" + d.slug], [m.name]];
  }

  /* ---------- Иш ---------- */
  function workDetail(w, el) {
    const m = mahalla(w.m), d = district(w.d);
    const secs = w.secs.map((id) => tById.get(id));
    const p = { lv_km: w.lv || 0, hv_km: w.hv || 0, tr_upgrade: w.up || 0, new_gktp: w.gk || 0, grsh: w.gr || 0, cost: w.cost || 0 };
    const f = w.f;
    const kv = (k, v) => `<tr><th>${k}</th><td>${v == null || v === "" ? "—" : v}</td></tr>`;
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow" style="color:${CAT_COLOR[w.cat]}">${icon(cat(w.cat).icon)}${esc(cat(w.cat).label)}</span>
          <h1>Иш №${w.no}</h1>
          <div class="head__sub"><a href="#/mahallas/${m.id}">${esc(m.name)} маҳалласи</a> · <a href="#/districts/${d.slug}">${esc(d.name)} тумани</a>
            · файл қатори ${w.rows.join(", ")}</div>
        </div>
        <div class="head__right">${progressBadge(pct(f.cost, p.cost))}</div>
      </div>
      <div class="kpis kpis--6">
        ${kpi("coins", "Зарур маблағ", moneyPair(w.cost)[0], moneyPair(w.cost)[1], w.cost == null ? "файлда кўрсатилмаган" : `амалда ${moneyShort(f.cost)}`, "", 7)}
        ${kpi("plug-zap", "Паст кучл. кабел", qty(w.lv), w.lv ? "км" : "", "G устуни", "", 1)}
        ${kpi("cable", "Юқори кучл. кабел", qty(w.hv), w.hv ? "км" : "", "H устуни", "", 3)}
        ${kpi("circle-arrow-up", "Трансформатор", qty(w.up), w.up ? "та" : "", "J устуни", "", 6)}
        ${kpi("square-plus", "Янги ГКТП", qty(w.gk), w.gk ? "та" : "", "K устуни", "", 8)}
        ${kpi("server", "ГРШ", qty(w.gr), w.gr ? "та" : "", "L устуни", "", 2)}
      </div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Бажариладиган иш</h3><span class="muted">B устуни</span></div>
          <div class="card__body">
            <p class="quote">${esc(w.text)}</p>
            <table class="kv">
              ${kv("Маҳалла", esc(m.name))}
              ${kv("ТП (C устуни)", esc(w.tp))}${kv("Матнда тилга олинган ТП лар", w.tpm.length ? w.tpm.map((x) => "ТП-" + esc(x)).join(", ") : "")}
              ${kv("Кабел маркаси (матндан)", esc(w.cable))}${kv("Янги трансформатор қуввати", w.tkva ? w.tkva + " кВА" : "")}
              ${kv("Жами км (F устуни)", qty(w.kmf))}${kv("Жами трансформатор (I устуни)", qty(w.trf))}
              ${kv("Тоифалар", w.cats.map((k) => esc(cat(k).label)).join(", "))}
            </table>

          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Режа ва амалда</h3></div>
          <div class="card__body">
            ${pfBlock(p, f, true)}
            ${w.fn ? `<p class="muted small" style="margin-top:8px">${esc(w.fn)}</p>` : ""}
            <h4 class="sub-h">ТП секциялари (${secs.length})</h4>
            ${tpTable(secs, true)}
            <h4 class="sub-h">Ижро тарихи</h4>
            ${entriesTable(eByW.get(w.id) || [])}
            ${IS_ADMIN ? `<div style="margin-top:12px"><a class="btn btn--gold" href="#/admin/${w.id}">${icon("square-pen")}Ижро киритиш</a></div>` : ""}
          </div>
        </div>
      </div>`;
    return [["Тошкент", "#/home"], ["Ишлар", "#/works"], [m.name + " · №" + w.no]];
  }

  /* ---------- ТП ---------- */
  function tpDetail(t, el) {
    const m = mahalla(t.m), d = district(t.d), w = wById.get(t.w);
    const sib = D.tps.map((x) => x.id);
    const idx = sib.indexOf(t.id);
    const prev = idx > 0 ? sib[idx - 1] : null, next = idx < sib.length - 1 ? sib[idx + 1] : null;
    const lp = (t.lf || 0) * 100, ll = loadLevel(lp);
    const phases = [["L1", t.va], ["L2", t.vb], ["L3", t.vc]];
    const dev = t.avgv == null ? null : t.avgv - 230;
    const hhPct = t.ct ? t.ch / t.ct * 100 : 0;
    const kvRow = (k, v) => `<tr><th>${k}</th><td>${v == null || v === "" ? "—" : v}</td></tr>`;
    const n = (v, dd = 1) => (v == null ? null : fmt(v, dd));
    const list3 = (a, dd) => a.map((x) => (x == null ? "—" : fmt(x, dd))).join(" / ");
    const tb = tabs(el, "tp", [["main", "Таҳлил"], ["data", "Барча маълумотлар"]]);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("utility-pole")}ТП секцияси</span>
          <h1>ТП-${esc(t.n)}</h1>
          <div class="head__sub"><a href="#/mahallas/${m.id}">${esc(m.name)} маҳалласи</a> · <a href="#/districts/${d.slug}">${esc(d.name)} тумани</a>
            · <a href="#/works/${w.id}">Иш №${w.no}</a> ${pill(t.status, "Юкланиш: " + STATUS[t.status])}</div>
        </div>
        <div class="head__right">
          ${tb.btns}
          <a class="btn" href="#/tps/${prev}" ${prev ? "" : 'aria-disabled="true"'} title="Олдинги">${icon("chevron-left")}</a>
          <a class="btn" href="#/tps/${next}" ${next ? "" : 'aria-disabled="true"'} title="Кейинги">${icon("chevron-right")}</a>
          ${t.data ? score(t.score, t.hs) : ""}
        </div>
      </div>
      ${!t.data ? `<div class="alert">${icon("triangle-alert")}<span>Бу секция бўйича файлда қувват, истеъмол ва кучланиш маълумотлари бўш.</span></div>` : ""}
      <div class="dgrid dgrid--tp" data-tab="main" ${tb.hidden("main")}>
        <div class="card">
          <div class="card__head"><h3>Юкланиш</h3><span class="muted">«Нагрузки ТП»</span></div>
          <div class="gauge is-${ll}" style="--p:${lp.toFixed(1)}"><div class="gauge__arc"></div>
            <div class="gauge__v"><b>${fmt(lp, 1)}%</b><span>${fmt(t.kva, 1)} / ${t.cap} кВА</span></div></div>
          <div class="facts">
            <div><span>Қувват захираси</span><b>${fmt(t.reserve, 1)} кВА</b></div>
            <div><span>Кеча (жами)</span><b>${fmt(t.kvay, 1)} кВА</b></div>
            <div><span>cos φ</span><b class="${t.pf != null && t.pf < 0.92 ? "t-warn" : ""}">${t.pf == null ? "—" : fmt(t.pf, 3)}</b></div>
            <div><span>Зичлик</span><b>${t.cap ? fmt(t.ct / t.cap, 2) : "—"} / кВА</b></div>
          </div>
          ${t.after ? `<div class="after">${icon("circle-arrow-up")}<div><b>Ишдан кейин (ҳисоб)</b>
            <span>Қувват ${t.cap} → ${t.after.cap} кВА · юкланиш ${fmt(lp, 1)}% → <b class="t-good">${fmt(t.after.lf * 100, 1)}%</b></span></div></div>` : ""}
        </div>
        <div class="card">
          <div class="card__head"><h3>Кучланиш сифати</h3><span class="muted">меъёр 218,5–241,5 В</span></div>
          <div class="vscale">
            ${phases.map(([p, v]) => `<div class="vrow"><span class="vrow__ph vrow__ph--${p}">${p}</span>
              <div class="vrow__track"><span class="vrow__lim"></span><span class="vrow__norm"></span><span class="vrow__nom"></span>
                ${v == null ? "" : `<span class="vrow__mk is-${t.ph[p]}" style="left:${vpos(v)}%"></span>`}</div>
              <b class="t-${t.ph[p]}">${v == null ? "—" : fmt(v, 1) + " В"}</b></div>`).join("")}
            <div class="vaxis"><span>200</span><span>215</span><span>230</span><span>245</span><span>260</span></div>
          </div>
          <div class="facts facts--3" style="margin-top:12px">
            <div><span>Ток L1 / L2 / L3</span><b>${list3([t.ia, t.ib, t.ic], 0)} А</b></div>
            <div><span>Фазалар фарқи</span><b>${fmt(t.imb, 1)}%</b></div>
            <div><span>Оғиш</span><b>${dev == null ? "—" : (dev > 0 ? "+" : "") + fmt(dev, 1) + " В"}</b></div>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Электр истеъмоли</h3></div>
          ${t.anomaly ? `<div class="alert">${icon("cpu")}<span>Кунлик истеъмол манфий/нол — ҳисоблагич маълумоти нотўғри, йиғиндиларга қўшилмаган.</span></div>` : ""}
          <div class="facts facts--3">
            <div><span>Кунлик, кВт·с</span><b>${fmt(t.dk, 1)}</b></div>
            <div><span>Ойлик, МВт·с</span><b>${mwh(t.mk)}</b></div>
            <div><span>Йиллик, МВт·с</span><b>${mwh(t.yk)}</b></div>
          </div>
          <div class="facts facts--3" style="margin-top:8px">
            <div><span>Счётчиклар</span><b>${t.ct}</b></div>
            <div><span>Аҳоли</span><b>${t.ch} (${fmt(hhPct)}%)</b></div>
            <div><span>Саноат</span><b>${t.cc}</b></div>
          </div>
          ${t.kpc != null ? `<div class="muted small" style="margin-top:10px">1 истеъмолчига ойига <b class="t-money">${fmt(t.kpc)}</b> кВт·соат · лойиҳа ўртачаси ${fmt(D.city.tp.kwh_per_consumer)}</div>` : ""}
        </div>
        <div class="card">
          <div class="card__head"><h3>Таҳлил ва тавсиялар</h3><span class="muted">${t.issues.length} та</span></div>
          <div class="card__body">
            ${t.issues.length ? `<ul class="issues">${t.issues.map((i) => `
              <li class="issue is-${i.level}">${icon(i.icon)}<div>
                <div class="issue__t">${esc(i.title)} ${pill(i.level, LEVEL[i.level])}</div>
                <p>${esc(i.text)}</p><p class="issue__a">→ ${esc(i.advice)}</p></div></li>`).join("")}</ul>`
            : t.data ? `<div class="ok-box">${icon("circle-check")}<div><b>Барча кўрсаткичлар меъёрда</b><span>Кучланиш, юкланиш, зичлик ва cos φ бўйича муаммо аниқланмади.</span></div></div>`
            : `<div class="empty">Маълумот йўқ</div>`}
          </div>
        </div>
      </div>
      <div class="dgrid dgrid--data" data-tab="data" ${tb.hidden("data")}>
        <div class="card"><div class="card__head"><h3>Жойлашув ва ҳисоб</h3><span class="muted">N–S, X–Y, AN–AO</span></div>
          <div class="card__body"><table class="kv">${kvRow("Название РЭС", esc(t.res))}${kvRow("Подстанция", esc(t.ps))}${kvRow("Фидер", esc(t.fd))}
            ${kvRow("Номер ТП", esc(t.n))}${kvRow("ТП (C устуни)", esc(t.base))}${kvRow("Tr Владелец", esc(t.own))}${kvRow("Мастер Тр", esc(t.mst))}
            ${kvRow("Номер счетчика баланса", esc(t.mtr))}${kvRow("Коэффициент КТ", n(t.kt, 0))}${kvRow("Состояние счетчика", esc(t.st))}
            ${kvRow("Примечание", esc(t.note))}${kvRow("Файл қатори", t.row)}</table></div></div>
        <div class="card"><div class="card__head"><h3>Истеъмолчи ва юклама</h3><span class="muted">T–AB, AM</span></div>
          <div class="card__body"><table class="kv">${kvRow("Счётчиклар: всего / бытовые / промышленные", `${t.ct} / ${t.ch} / ${t.cc}`)}${kvRow("Мощность", t.cap + " кВА")}
            ${kvRow("Среднесуточное потребление", n(t.dk, 3) == null ? null : n(t.dk, 3) + " кВт·соат")}
            ${kvRow("Ойлик / йиллик (ҳисоб)", t.mk == null ? null : `${fmt(t.mk, 0)} / ${fmt(t.yk, 0)} кВт·соат`)}
            ${kvRow("Вчера итого", n(t.kvay) == null ? null : n(t.kvay) + " кВА")}${kvRow("Всего", n(t.kva) == null ? null : n(t.kva) + " кВА")}
            ${kvRow("Нагрузки ТП", t.lf == null ? null : `${fmt(t.lf, 3)} (${fmt(lp, 1)}%)`)}${kvRow("Юкланиш тоифаси", STATUS[t.status] + " (0–50% яшил, 50–60% сариқ, 60%+ қизил)")}</table></div></div>
        <div class="card"><div class="card__head"><h3>Фазалар</h3><span class="muted">AC–AL</span></div>
          <div class="card__body"><table class="kv">${kvRow("Фактор силы (PF)", n(t.pf, 3))}${kvRow("PF L1 / L2 / L3", list3([t.pf1, t.pf2, t.pf3], 3))}
            ${kvRow("Средний ток L1 / L2 / L3", list3([t.ia, t.ib, t.ic], 2) + " А")}
            ${kvRow("Среднее напряжение L1 / L2 / L3", list3([t.va, t.vb, t.vc], 1) + " В")}
            ${kvRow("Фазалар фарқи", fmt(t.imb, 2) + "%")}</table></div></div>
        <div class="card"><div class="card__head"><h3>Ҳисобланган кўрсаткичлар</h3></div>
          <div class="card__body"><table class="kv">${kvRow("Ҳақиқий юклама", fmt(t.actual, 1) + " кВА")}${kvRow("Қувват захираси", fmt(t.reserve, 1) + " кВА")}
            ${kvRow("Чўққи юкланиш (тахминий)", "~" + t.peak + "%")}${kvRow("1 истеъмолчига ойига", t.kpc == null ? null : fmt(t.kpc, 1) + " кВт·соат")}
            ${kvRow("Саломатлик индекси", t.score == null ? null : t.score + " / 100")}
            ${t.after ? kvRow("Ишдан кейин (ҳисоб)", `${t.after.cap} кВА, юкланиш ${fmt(t.after.lf * 100, 1)}%`) : ""}</table></div></div>
      </div>`;
    tb.bind();
    return [["Тошкент", "#/home"], [d.name, "#/districts/" + d.slug], [m.name, "#/mahallas/" + m.id], ["ТП-" + t.n]];
  }

  /* ---------- Мақсад ---------- */
  function goalDetail(g, el) {
    const m = mahalla(g.m), d = district(m.d);
    const ws = m.works.map((id) => wById.get(id));
    el.innerHTML = `
      <div class="head goal-head">
        <div>
          <span class="eyebrow">${icon("target")}Маҳалла мақсади · «Обод маҳалла» ${g.year}</span>
          <h1>${esc(g.title)}</h1>
          <div class="head__sub"><a href="#/mahallas/${m.id}">${esc(m.name)} маҳалласи</a> · <a href="#/districts/${d.slug}">${esc(d.name)} тумани</a></div>
        </div>
        <div class="head__right badges">${pill(g.priority, PRIO[g.priority] + " устуворлик")}${pill("plain", GSTATUS[g.status])}</div>
      </div>
      <div class="kpis kpis--4">
        ${kpi("wallet", "Бюджет", moneyPair(g.budget)[0], moneyPair(g.budget)[1], "манзилли дастур бўйича", "", 7)}
        ${kpi("list-checks", "Ишлар", ws.length, "та", `${m.cats.length} йўналиш`, "", 1)}
        ${kpi("zap", "ТП секциялари", m.tps.length, "та", "ишларга бириктирилган", "", 3)}
        ${kpi("users", "Истеъмолчилар", g.benef ? fmt(g.benef) : "—", g.benef ? "истеъмолчи" : "", g.benef ? "шу ТП лар орқали" : "ТП маълумоти йўқ", "", 2)}
      </div>
      <div class="dgrid dgrid--goal">
        <div class="card">
          <div class="card__head"><h3>Режадаги ишлар</h3><span class="muted">${ws.length} та · ${money(g.budget)}</span></div>
          <div class="card__body">
            <ol class="tasks">${ws.map((w) => `
              <li class="task"><span class="task__i" style="color:${CAT_COLOR[w.cat]};border-color:${CAT_COLOR[w.cat]}55;background:${CAT_COLOR[w.cat]}14">${icon(cat(w.cat).icon)}</span>
                <div class="task__b"><a href="#/works/${w.id}"><b>№${w.no} · ${esc(w.title)}</b></a><p><span style="color:${CAT_COLOR[w.cat]}">${esc(cat(w.cat).label)}</span> · ${esc(workQty(w))}</p></div>
                <div class="task__m"><b>${w.cost == null ? "—" : fmt(w.cost, 2)}</b><span>млн сўм</span></div></li>`).join("")}
            </ol>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Йўналишлар ва натижалар</h3></div>
          <div class="card__body">
            <p class="quote">${esc(g.summary)}</p>
            ${catBars(m.cats)}
            <ul class="effects" style="margin-top:14px">${g.effects.map((e) => `<li>${icon("circle-check")}<span>${esc(e)}</span></li>`).join("")}</ul>
          </div>
        </div>
      </div>`;
    return [["Тошкент", "#/home"], ["Мақсадлар", "#/goals"], [m.name]];
  }

  /* =========================================================
     Ижро (режа ва амалда)
     ========================================================= */
  function renderProgress() {
    const c = D.city, p = c.plan, f = c.fact;
    const catPlan = Object.keys(D.categories).map((k) => {
      const ws = D.works.filter((w) => w.cat === k);
      return { k, n: ws.length, plan: ws.reduce((s, w) => s + (w.cost || 0), 0), fact: ws.reduce((s, w) => s + (w.f.cost || 0), 0) };
    }).filter((x) => x.n);
    const ICONS = { lv_km: "plug-zap", hv_km: "cable", tr_upgrade: "circle-arrow-up", new_gktp: "square-plus", grsh: "server", cost: "coins" };
    const TONES = { lv_km: 1, hv_km: 3, tr_upgrade: 6, new_gktp: 8, grsh: 2, cost: 7 };
    viewEl.innerHTML = `
      <div class="page">
        <div class="head">
          <div>
            <span class="eyebrow">${icon("calendar-check")}Режа ва амалда · 2027</span>
            <h1>Дастур ижроси</h1>
            <div class="head__sub">Режа — манзилли дастур файлидан; амалдаги ҳажмлар ҳар куни админ томонидан киритилади${D.entries.length ? ` · ${D.entries.length} та ёзув, охиргиси ${D.entries[0].at}` : " (ҳали киритилмаган)"}.</div>
          </div>
          <div class="head__right">${progressBadge(progressOf(c), "Маблағ ўзлаштириш")}</div>
        </div>
        <div class="kpis kpis--6 kpis--row">
          ${PF.map((x) => kpi(ICONS[x.key], SHORT[x.key], fmtPct(pct(f[x.key], p[x.key])), "%",
            x.key === "cost" ? `${f.cost ? moneyShort(f.cost) : "0"} / ${moneyShort(p.cost)}` : `${qty(f[x.key])} / ${qty(p[x.key])} ${x.unit}`,
            bar(pct(f[x.key], p[x.key]), "good", x.key === "cost" ? "#fde047" : null), TONES[x.key])).join("")}
        </div>
        <div class="pgrid">
          <div class="card">
            <div class="card__head"><h3>Туманлар: маблағ режаси ва амалда</h3><span class="muted">млн сўм</span></div>
            <div class="chart"><canvas id="ch-pd"></canvas></div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Иш турлари: режа ва амалда</h3><span class="muted">млн сўм</span></div>
            <div class="chart"><canvas id="ch-pc"></canvas></div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Кунлик ижро</h3><span class="muted">${D.entries.length} та ёзув</span></div>
            ${D.entries.length ? `<div class="chart"><canvas id="ch-pt"></canvas></div>` : `<div class="empty">${icon("calendar-days")}<span>Ҳали ижро киритилмаган. Админ киритган ҳар бир ёзув шу ерда кунлар бўйича кўринади.</span></div>`}
          </div>
          <div class="card pgrid__wide">
            <div class="card__head"><h3>Туманлар кесимида ижро</h3><span class="muted">амалда / режа · ${f.done} / ${p.works} иш бажарилган</span></div>
            <div class="card__body">
              <table class="tbl"><thead><tr><th>Туман</th><th class="r">Ишлар</th><th class="r">Паст кабел, км</th><th class="r">Юқори кабел, км</th>
                <th class="r">Трансформатор</th><th class="r">ГКТП</th><th class="r">ГРШ</th><th class="r">Маблағ, млн</th><th>Ижро</th></tr></thead>
                <tbody>${D.districts.map((d) => {
                  const a = d.plan, b = d.fact, pr = progressOf(d);
                  const cell = (k) => `<td class="r">${qty(b[k])} / ${qty(a[k])}</td>`;
                  return `<tr data-href="#/districts/${d.slug}"><td><i class="dot" style="background:${d.color}"></i> <b>${esc(d.name)}</b></td>
                    <td class="r">${b.done} / ${a.works}</td>${cell("lv_km")}${cell("hv_km")}${cell("tr_upgrade")}${cell("new_gktp")}${cell("grsh")}
                    <td class="r t-money">${fmt(b.cost, 1)} / ${fmt(a.cost, 1)}</td><td class="nowrap pcell">${bar(pr, "good")}<span>${fmtPct(pr)}%</span></td></tr>`;
                }).join("")}</tbody></table>
            </div>
          </div>
        </div>
      </div>`;
    planFactChart($("#ch-pd"), D.districts.map((d) => d.name), D.districts.map((d) => d.plan.cost), D.districts.map((d) => d.fact.cost),
      D.districts.map((d) => d.color), "млн сўм");
    timelineChart($("#ch-pt"));
    planFactChart($("#ch-pc"), catPlan.map((x) => CAT_SHORT[x.k]), catPlan.map((x) => x.plan), catPlan.map((x) => x.fact),
      catPlan.map((x) => CAT_COLOR[x.k]), "млн сўм");
    return [["Тошкент", "#/home"], ["Ижро"]];
  }

  /* =========================================================
     Таҳлил
     ========================================================= */
  function renderAnalytics() {
    const c = D.city, e = c.expected, t = c.tp;
    const byPs = new Map();
    D.tps.filter((x) => x.data).forEach((x) => {
      const k = x.ps || "—";
      const o = byPs.get(k) || { ps: k, res: x.res, n: 0, ct: 0, cap: 0, kva: 0 };
      o.n++; o.ct += x.ct; o.cap += x.cap; o.kva += x.kva || 0;
      byPs.set(k, o);
    });
    const ps = [...byPs.values()].sort((a, b) => b.ct - a.ct);
    const bins = [[0, 10], [10, 20], [20, 30], [30, 40], [40, 50], [50, 60], [60, 1000]];
    const hist = bins.map(([a, b]) => D.tps.filter((x) => x.data && (x.lf || 0) * 100 >= a && (x.lf || 0) * 100 < b).length);
    const binLbl = bins.map(([a, b]) => (b > 100 ? `${a}%+` : `${a}–${b}%`));
    const upgraded = D.tps.filter((x) => x.after);
    const avgBefore = upgraded.length ? upgraded.reduce((s, x) => s + (x.lf || 0), 0) / upgraded.length * 100 : 0;
    const avgAfter = upgraded.length ? upgraded.reduce((s, x) => s + x.after.lf, 0) / upgraded.length * 100 : 0;
    const cables = {};
    D.works.forEach((w) => {
      if (!w.cable) return;
      const k = w.cable.replace(/мм2?$/i, "").replace("*", "х").replace(/^АПВПу/i, "АПвПУ");
      const o = cables[k] || (cables[k] = { n: 0, km: 0 });
      o.n++; o.km += (w.lv || 0) + (w.hv || 0);
    });
    const ck = Object.entries(cables).sort((a, b) => b[1].n - a[1].n);
    const ckMax = Math.max(1, ...ck.map((x) => x[1].n));
    const kvr = (k, v) => `<tr><th>${k}</th><td>${v}</td></tr>`;
    viewEl.innerHTML = `
      <div class="page">
        <div class="head">
          <div>
            <span class="eyebrow">${icon("chart-no-axes-combined")}Таҳлил · файл маълумотларидан ҳисобланган</span>
            <h1>Таҳлил ва ҳисоб-китоблар</h1>
            <div class="head__sub">Бирлик нархлари, подстанциялар, юкланиш тақсимоти ва ишлардан кейинги кутилаётган ҳолат</div>
          </div>
          <div class="head__right">${t.with_data ? score(Math.round(t.health), t.status, "ТП саломатлиги") : ""}</div>
        </div>
        <div class="kpis kpis--6 kpis--row">
          ${kpi("battery-charging", "Янги қувват", fmt(e.total_kva / 1000, 2), "МВА", "алмаштириш + янги ГКТП", "", 3)}
          ${kpi("circle-arrow-up", "Алмаштириш", e.upgraded, "та", `юкланиш ${fmt(avgBefore, 1)}% → ${fmt(avgAfter, 1)}%`, "", 6)}
          ${kpi("square-plus", "ГКТП қуввати", fmt(e.gktp_kva), "кВА", `${c.plan.new_gktp} та ГКТП`, "", 8)}
          ${kpi("gauge", "Юкланиш", fmt(t.load_pct, 1), "%", `${t.with_data} та ТП ўртачаси`, "", 4)}
          ${kpi("activity", "Ойлик истеъмол", mwh(t.monthly_kwh, 0), "МВт·соат", `кунлик ${mwh(t.daily_kwh, 1)} МВт·с`, "", 5)}
          ${kpi("coins", "Маҳаллага ўртача", moneyPair(c.plan.cost / c.mahallas)[0], moneyPair(c.plan.cost / c.mahallas)[1], `1 ишга ${moneyShort(c.plan.cost / c.plan.works)}`, "", 7)}
        </div>
        <div class="agrid">
          <div class="card">
            <div class="card__head"><h3>Бирлик нархлари</h3><span class="muted">млн сўм</span></div>
            <div class="card__body">
              <table class="tbl tbl--wrap tbl--compact"><thead><tr><th>Иш тури</th><th class="r">Нархи</th><th class="r">Ишлар</th></tr></thead>
                <tbody>${D.unitCosts.map((u) => `<tr title="Оралиқ: ${fmt(u.min, 2)}–${fmt(u.max, 2)} млн сўм"><td><span class="wcell"><i class="dot" style="background:${CAT_COLOR[u.kind]}"></i><span>${esc(CAT_SHORT[u.kind])}<br><span class="muted small">1 ${u.unit} учун</span></span></span></td>
                  <td class="r t-money">${fmt(u.median, 2)}</td><td class="r">${u.n}</td></tr>`).join("")}</tbody></table>
              <p class="muted small" style="margin-top:8px">Медиана, млн сўм: бир турдаги ишлар бўйича маблағ ÷ ҳажм.</p>
            </div>
          </div>
          <div class="card">
            <div class="card__head"><h3>ТП юкланиш тақсимоти</h3><span class="muted">${t.with_data} та ТП</span></div>
            <div class="chart"><canvas id="ch-hist"></canvas></div>
          </div>
          <div class="card">
            <div class="card__head"><h3>ТП ҳолати</h3><span class="muted">${t.with_data} та</span></div>
            <div class="card__body"><table class="kv">
              ${kvr("Яшил / сариқ / қизил", `<span class="t-good">${t.good}</span> / <span class="t-warn">${t.warn}</span> / <span class="t-crit">${t.crit}</span>`)}
              ${kvr("Кучланиш меъёрдан ташқари", t.voltage_issues + " та")}
              ${kvr("Фазалар носимметрияси", t.imbalance + " та")}
              ${kvr("cos φ 0,92 дан паст", t.low_pf + " та")}
              ${kvr("Ўртача кучланиш", fmt(t.avg_voltage, 1) + " В")}
              ${kvr("Ўртача cos φ", fmt(t.avg_pf, 3))}
              ${kvr("1 истеъмолчига ойига", fmt(t.kwh_per_consumer, 0) + " кВт·соат")}
            </table></div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Подстанциялар</h3><span class="muted">${ps.length} та</span></div>
            <div class="card__body">
              <table class="tbl tbl--wrap tbl--compact"><thead><tr><th>Подстанция</th><th class="r">ТП</th><th class="r">Истеъм.</th><th class="r">Юкл.</th></tr></thead>
                <tbody>${ps.map((o) => `<tr><td><b>${esc(o.ps)}</b></td><td class="r">${o.n}</td>
                  <td class="r">${fmt(o.ct)}</td><td class="r">${o.cap ? fmt(o.kva / o.cap * 100, 1) + "%" : "—"}</td></tr>`).join("")}</tbody></table>
            </div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Энг юкланган ТП лар</h3><span class="muted">ҳозир → ишдан кейин</span></div>
            <div class="card__body">
              <table class="tbl tbl--compact"><thead><tr><th>ТП</th><th>Маҳалла</th><th class="r">Ҳозир</th><th class="r">Кейин</th></tr></thead>
                <tbody>${D.tps.filter((x) => x.data).sort((a, b) => (b.lf || 0) - (a.lf || 0)).slice(0, 20).map((x) => `<tr data-href="#/tps/${x.id}">
                  <td><b>ТП-${esc(x.n)}</b></td><td class="ellip">${esc(mahalla(x.m).name)}</td><td class="r t-${x.status}">${fmt((x.lf || 0) * 100, 1)}%</td>
                  <td class="r">${x.after ? `<span class="t-good">${fmt(x.after.lf * 100, 1)}%</span>` : "—"}</td></tr>`).join("")}</tbody></table>
            </div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Кабел маркалари</h3><span class="muted">${ck.reduce((a, x) => a + x[1].n, 0)} та иш</span></div>
            <div class="card__body"><div class="mbars">${ck.map(([k, o], i) => `
              <div class="mbar"><span class="mbar__l">${esc(k)}</span>
                <span class="mbar__t"><i style="width:${(o.n / ckMax * 100).toFixed(1)}%;background:${PALETTE[i % PALETTE.length]}"></i></span>
                <span class="mbar__v"><b>${o.n}</b> иш · ${qty(+o.km.toFixed(2))} км</span></div>`).join("")}</div></div>
          </div>
        </div>
      </div>`;
    barChart($("#ch-hist"), binLbl, hist, bins.map(([a]) => (a >= 60 ? SC.crit : a >= 50 ? SC.warn : SC.good)), "ТП", false, (v) => fmt(v) + " та");
    return [["Тошкент", "#/home"], ["Таҳлил"]];
  }

  /* =========================================================
     Катталаштириш: карточка ёки график устига босилганда
     ========================================================= */
  const zoomEl = document.createElement("div");
  zoomEl.className = "zoom";
  zoomEl.hidden = true;
  document.body.appendChild(zoomEl);
  const zoomCharts = [];

  function openZoom(card) {
    const clone = card.cloneNode(true);
    clone.classList.add("card--zoom");
    clone.removeAttribute("hidden");
    zoomEl.innerHTML = `<div class="zoom__box" role="dialog" aria-modal="true">
      <button type="button" class="zoom__x" data-zoom-close aria-label="Ёпиш" title="Ёпиш (Esc)">${icon("x")}</button></div>`;
    zoomEl.firstElementChild.appendChild(clone);
    if (!card.querySelector("canvas")) zoomEl.firstElementChild.classList.add("zoom__box--auto");
    zoomEl.hidden = false;
    document.body.classList.add("is-zoom");
    const src = $$("canvas", card), dst = $$("canvas", clone);
    dst.forEach((cv, i) => {
      const build = src[i] && src[i].__build;
      const fresh = document.createElement("canvas");
      cv.replaceWith(fresh);
      if (build && window.Chart) zoomCharts.push(new Chart(fresh, build()));
    });
    icons();
    $("[data-zoom-close]", zoomEl).focus();
  }

  function closeZoom() {
    if (zoomEl.hidden) return;
    zoomCharts.splice(0).forEach((c) => c.destroy());
    zoomEl.hidden = true;
    zoomEl.innerHTML = "";
    document.body.classList.remove("is-zoom");
  }

  function initZoom() {
    // Рўйхат панеллари (туманлар, маҳаллалар, мақсадлар …) катталашмайди; ҳавола, тугма ва жадвал қаторлари ўз ишини қилади
    viewEl.addEventListener("click", (e) => {
      if (e.defaultPrevented || e.target.closest("a, button, input, select, textarea, label, tr[data-href], .seg, .pane, .chips, .card--form, .login")) return;
      const card = e.target.closest(".card");
      if (card && viewEl.contains(card)) openZoom(card);
    });
    zoomEl.addEventListener("click", (e) => {
      if (e.target === zoomEl || e.target.closest("[data-zoom-close]")) { closeZoom(); return; }
      const tr = e.target.closest("tr[data-href]");
      if (tr) { closeZoom(); location.hash = tr.dataset.href; }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeZoom(); });
    window.addEventListener("hashchange", closeZoom);
  }

  /* =========================================================
     Сервер билан алоқа: ҳолат, маълумотни янгилаш, админ
     ========================================================= */
  async function post(url, body, isForm = false) {
    let r;
    try {
      r = await fetch(url, {
        method: "POST", credentials: "same-origin",
        headers: isForm ? { "X-CSRFToken": CSRF } : { "Content-Type": "application/json", "X-CSRFToken": CSRF },
        body: isForm ? body : JSON.stringify(body || {}),
      });
    } catch (e) { return { ok: false, error: "Сервер билан алоқа йўқ. Интернетни текширинг." }; }
    let j;
    try { j = await r.json(); } catch (e) { j = { ok: false, error: `Сервер хатоси (${r.status})` }; }
    if (r.status === 403 && IS_ADMIN && /парол/i.test(j.error || "")) { IS_ADMIN = false; applyAdminUI(); route(); }
    return j;
  }

  const toastEl = $("[data-toast]");
  let toastTimer;
  function toast(msg, kind = "ok") {
    toastEl.className = "toast toast--" + kind;
    toastEl.innerHTML = `${icon(kind === "ok" ? "circle-check" : "triangle-alert")}<span>${esc(msg)}</span>`;
    toastEl.hidden = false;
    icons();
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
  }

  /* Бошқа фойдаланувчиларда «Маълумотлар ўзгартирилмоқда» */
  const busyEl = $("[data-busy]");
  function toggleBusy(on, reason) {
    if (on) {
      $("[data-busy-reason]", busyEl).textContent = reason || "Администратор маълумот киритмоқда";
      busyEl.hidden = false;
      document.body.classList.add("is-busy");
    } else if (!busyEl.hidden) {
      busyEl.hidden = true;
      document.body.classList.remove("is-busy");
    }
  }

  function setData(next) {
    D = next;
    indexData();
    initSidebar();
    route();
  }

  let refreshing = false;
  async function refreshData(silent = false) {
    if (refreshing) return;
    refreshing = true;
    try {
      const r = await fetch("api/data", { cache: "no-store", credentials: "same-origin" });
      const j = await r.json();
      VERSION = j.version;
      setData(j.data);
      if (!silent) toast("Маълумотлар янгиланди");
    } catch (e) { console.error(e); }
    refreshing = false;
  }

  async function poll() {
    try {
      const r = await fetch("api/state", { cache: "no-store", credentials: "same-origin" });
      const st = await r.json();
      if (st.admin !== IS_ADMIN) { IS_ADMIN = st.admin; applyAdminUI(); }
      toggleBusy(st.busy && !IS_ADMIN, st.reason);
      if (st.version !== VERSION && !st.busy) await refreshData(IS_ADMIN);
    } catch (e) { /* тармоқ узилса кейинги сафар */ }
    setTimeout(poll, document.hidden ? 10000 : 3000);
  }

  /* ---------- Админ: махфий сўз, кириш, бўлимлар ---------- */
  const fnv = (str) => { let x = 0x811c9dc5; for (const ch of str) { x ^= ch.codePointAt(0); x = Math.imul(x, 0x01000193) >>> 0; } return x.toString(36); };
  const SECRET = ["ejawd3", "epsoxa", "1dnujrl"];   // махфий сўз хеши (кирилл ва лотин ёзувида)
  const isSecret = (q) => SECRET.includes(fnv(q.toLowerCase().replace(/\s+/g, "")));
  const ADMIN_VIEWS = ["admin", "admin-log", "admin-upload"];

  function applyAdminUI() {
    $$("[data-admin-only]").forEach((el) => { el.hidden = !IS_ADMIN; });
    document.body.classList.toggle("is-admin", IS_ADMIN);
    const c = $('[data-count="entries"]');
    if (c) c.textContent = D.entries.length;
  }

  const today = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  const dmy = (iso) => (iso ? iso.split("-").reverse().join(".") : "—");
  const ENTRY_KEYS = ["lv_km", "hv_km", "tr_upgrade", "new_gktp", "grsh", "cost"];
  const EKEY = { lv_km: "lv", hv_km: "hv", tr_upgrade: "up", new_gktp: "gk", grsh: "gr", cost: "cost" };
  const planOf = (w) => ({ lv_km: w.lv || 0, hv_km: w.hv || 0, tr_upgrade: w.up || 0, new_gktp: w.gk || 0, grsh: w.gr || 0, cost: w.cost || 0 });
  function workState(w) {
    const p = planOf(w), keys = ENTRY_KEYS.filter((k) => k !== "cost" && p[k] > 0);
    const any = ENTRY_KEYS.some((k) => (w.f[k] || 0) > 0);
    if (keys.length && keys.every((k) => (w.f[k] || 0) >= p[k] - 1e-9)) return "done";
    return any ? "doing" : "todo";
  }
  const WSTATE = { todo: ["Бошланмаган", "muted"], doing: ["Жараёнда", "warn"], done: ["Бажарилган", "good"] };
  const entryText = (e) => {
    const parts = [];
    if (e.lv) parts.push(qty(e.lv) + " км паст кабел");
    if (e.hv) parts.push(qty(e.hv) + " км юқори кабел");
    if (e.up) parts.push(qty(e.up) + " та трансформатор");
    if (e.gk) parts.push(qty(e.gk) + " та ГКТП");
    if (e.gr) parts.push(qty(e.gr) + " та ГРШ");
    return parts.join(", ") || "—";
  };
  const entriesTable = (list, withWork = false, canDelete = false) => list.length ? `
    <table class="tbl tbl--wrap tbl--compact"><thead><tr><th>Сана</th>${withWork ? "<th>Иш</th>" : ""}<th>Бажарилди</th><th class="r">Маблағ</th><th>Изоҳ</th>${canDelete ? "<th></th>" : ""}</tr></thead>
      <tbody>${list.map((e) => {
        const w = e.w ? wById.get(e.w) : null;
        return `<tr ${withWork && w ? `data-href="#/admin/${w.id}"` : ""}><td class="nowrap">${dmy(e.date)}<br><span class="muted small">${esc(e.at)}</span></td>
          ${withWork ? `<td>${w ? `<b>${esc(mahalla(w.m).name)}</b> · №${w.no}<br><span class="muted small">${esc(w.title.slice(0, 70))}</span>` : `<span class="t-warn">Иш топилмади</span> · №${e.no}`}</td>` : ""}
          <td>${esc(entryText(e))}</td><td class="r t-money nowrap">${e.cost ? moneyShort(e.cost) : "—"}</td>
          <td class="small">${esc(e.note)}</td>
          ${canDelete ? `<td class="r"><button type="button" class="btn btn--icon btn--danger" data-del="${e.id}" title="Ўчириш">${icon("trash-2")}</button></td>` : ""}</tr>`;
      }).join("")}</tbody></table>` : `<div class="empty">${icon("history")}<span>Ҳали ижро киритилмаган</span></div>`;

  function bindDelete(root) {
    $$("[data-del]", root).forEach((b) => b.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm("Бу ёзувни ўчирасизми? «Амалда» қийматлари қайта ҳисобланади.")) return;
      b.disabled = true;
      const j = await post(`panel/entry/${b.dataset.del}/delete`);
      if (j.ok) { toast("Ёзув ўчирилди"); await refreshData(true); } else { toast(j.error, "err"); b.disabled = false; }
    }));
  }

  /* Кириш (парол) */
  function renderLogin() {
    viewEl.innerHTML = `
      <div class="login">
        <form class="login__card" data-login autocomplete="off">
          <svg class="bolt-anim bolt-anim--sm" viewBox="0 0 120 120" aria-hidden="true">
            <circle class="bolt-anim__track" cx="60" cy="60" r="52"/>
            <g class="bolt-anim__spin"><circle class="bolt-anim__arc" cx="60" cy="60" r="52"/></g>
            <path class="bolt-anim__bolt" d="M67 16 L35 66 H57 L50 104 L86 50 H63 Z"/>
          </svg>
          <h2>Админ панели</h2>
          <p class="muted">Давом этиш учун паролни киритинг</p>
          <label class="field field--lg">${icon("key-round")}<input type="password" inputmode="numeric" data-pass placeholder="Парол" aria-label="Парол" required></label>
          <div class="login__err" data-err hidden></div>
          <button class="btn btn--gold btn--wide" type="submit">${icon("log-in")}Кириш</button>
          <a href="#/home" class="muted small">Бош саҳифага қайтиш</a>
        </form>
      </div>`;
    const form = $("[data-login]", viewEl), inp = $("[data-pass]", viewEl), err = $("[data-err]", viewEl);
    setTimeout(() => inp.focus(), 50);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      const btn = $("button", form);
      btn.disabled = true;
      const j = await post("panel/login", { password: inp.value });
      btn.disabled = false;
      if (j.ok) {
        IS_ADMIN = true;
        applyAdminUI();
        toast("Хуш келибсиз! Админ панели очилди");
        current = null;
        route();
      } else {
        err.textContent = j.error || "Парол нотўғри";
        err.hidden = false;
        inp.select();
        form.classList.remove("shake"); void form.offsetWidth; form.classList.add("shake");
      }
    });
    return [["Тошкент", "#/home"], ["Админ панели"]];
  }

  /* «Ўзгартирилмоқда» белгисини ушлаб туриш (админ форма билан ишлаётганда) */
  const lockState = { on: false, timer: null, reason: "" };
  function holdLock(reason) {
    lockState.reason = reason;
    if (lockState.on) return;
    lockState.on = true;
    post("panel/lock", { reason });
    lockState.timer = setInterval(() => post("panel/lock", { reason: lockState.reason }), 10000);
  }
  function releaseLock(sendUnlock = true) {
    if (!lockState.on) return;
    lockState.on = false;
    clearInterval(lockState.timer);
    if (sendUnlock) post("panel/unlock");
  }
  window.addEventListener("beforeunload", () => {
    if (!lockState.on) return;
    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", CSRF);
    navigator.sendBeacon("panel/unlock", fd);
  });

  /* Иш бўйича ижро киритиш */
  function adminDetail(w, el) {
    const m = mahalla(w.m), d = district(w.d), g = gById.get(m.goal);
    const p = planOf(w), f = w.f;
    const keys = ENTRY_KEYS.filter((k) => k === "cost" || p[k] > 0);
    const rem = Object.fromEntries(ENTRY_KEYS.map((k) => [k, Math.max(0, +(p[k] - (f[k] || 0)).toFixed(4))]));
    const st = workState(w);
    const list = eByW.get(w.id) || [];
    const unitOf = (k) => (k === "cost" ? "млн сўм" : PF.find((x) => x.key === k).unit);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow" style="color:${CAT_COLOR[w.cat]}">${icon("square-pen")}Ижро киритиш · ${esc(cat(w.cat).label)}</span>
          <h1>Иш №${w.no} · ${esc(m.name)}</h1>
          <div class="head__sub"><a href="#/districts/${d.slug}">${esc(d.name)} тумани</a> · <a href="#/works/${w.id}">сайтда кўриш</a>
            ${pill(WSTATE[st][1], WSTATE[st][0])} ${w.upd ? `<span class="muted">охирги ёзув: ${dmy(w.upd)}</span>` : ""}</div>
        </div>
        <div class="head__right">${progressBadge(pct(f.cost, p.cost))}</div>
      </div>
      <div class="dgrid dgrid--admin">
        <div class="card card--form">
          <div class="card__head"><h3>Бугунги ижрони киритиш</h3><span class="muted">қолган ҳажм кўрсатилган</span></div>
          <div class="card__body">
            <p class="quote quote--sm">${esc(w.text)}</p>
            ${g ? `<p class="muted small" style="margin:-6px 0 12px">Мақсад: <b>${esc(g.title)}</b></p>` : ""}
            <form class="eform" data-eform autocomplete="off">
              <label class="eform__row"><span>Сана</span><input type="date" name="date" value="${today()}" max="${today()}" required></label>
              ${keys.map((k) => `<label class="eform__row"><span>${SHORT[k]}, ${unitOf(k)}<small>режа ${k === "cost" ? moneyShort(p[k]) : qty(p[k])} · қолган <b>${k === "cost" ? moneyShort(rem[k]) : qty(rem[k])}</b></small></span>
                <input type="number" name="${k}" min="0" step="any" inputmode="decimal" placeholder="0"></label>`).join("")}
              <label class="eform__row eform__row--note"><span>Изоҳ</span><textarea name="note" rows="2" maxlength="1000" placeholder="Масалан: 2-уйгача кабел ётқизилди"></textarea></label>
              <div class="eform__msg" data-msg hidden></div>
              <div class="eform__btns">
                <button type="submit" class="btn btn--gold">${icon("save")}Сақлаш</button>
                <button type="button" class="btn" data-complete ${st === "done" ? "disabled" : ""}>${icon("check-check")}Қолганини бажарилди деб белгилаш</button>
                <button type="reset" class="btn btn--ghost">Тозалаш</button>
              </div>
            </form>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Режа ва амалда</h3><span class="muted">${list.length} та ёзув</span></div>
          <div class="card__body">
            ${pfBlock(p, f, true)}
            <h4 class="sub-h">Ижро тарихи</h4>
            ${entriesTable(list, false, true)}
          </div>
        </div>
      </div>`;
    const form = $("[data-eform]", el), msg = $("[data-msg]", el);
    const reason = `${m.name} маҳалласи · иш №${w.no} бўйича маълумот киритилмоқда`;
    form.addEventListener("input", () => holdLock(reason));
    form.addEventListener("reset", () => { msg.hidden = true; releaseLock(); });
    const show = (text, kind) => { msg.className = "eform__msg eform__msg--" + kind; msg.textContent = text; msg.hidden = false; };
    async function send(body, btn) {
      btn.disabled = true;
      holdLock(reason);
      const j = await post("panel/entry", body);
      btn.disabled = false;
      if (!j.ok) { show(j.error || "Хатолик", "err"); return; }
      releaseLock(false);   // сервер версияни янгилаб, белгини ўзи олиб ташлади
      toast("Сақланди — сайт барча фойдаланувчилар учун янгиланди");
      await refreshData(true);
    }
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = { work: w.id, date: fd.get("date"), note: fd.get("note") || "" };
      const over = [];
      for (const k of keys) {
        const v = parseFloat(String(fd.get(k) || "0").replace(",", ".")) || 0;
        if (v < 0) { show("Манфий қиймат киритиб бўлмайди", "err"); return; }
        body[k] = v;
        if (v > rem[k] + 1e-9) over.push(SHORT[k]);
      }
      if (!keys.some((k) => body[k] > 0) && !body.note.trim()) { show("Камида битта қиймат ёки изоҳ киритинг", "err"); return; }
      if (over.length && !confirm(`${over.join(", ")}: киритилган қиймат қолган режадан катта. Сақлайсизми?`)) return;
      send(body, $("button[type=submit]", form));
    });
    $("[data-complete]", el).addEventListener("click", (e) => {
      if (!confirm("Ишнинг қолган барча ҳажми ва маблағи бугунги сана билан «бажарилди» деб ёзилади. Давом этасизми?")) return;
      const fd = new FormData(form);
      send({ work: w.id, date: fd.get("date") || today(), complete: true, note: fd.get("note") || "Иш тўлиқ бажарилди" }, e.currentTarget);
    });
    bindDelete(el);
    return [["Админ", "#/admin"], ["Ижро киритиш", "#/admin"], [m.name + " · №" + w.no]];
  }

  /* Ижро журнали */
  let logFilter = { date: "", d: "" };
  function renderAdminLog() {
    const E = D.entries;
    const t = today();
    const sum = (list) => list.reduce((s, e) => s + (e.cost || 0), 0);
    const d7 = new Date(); d7.setDate(d7.getDate() - 6);
    const iso7 = `${d7.getFullYear()}-${String(d7.getMonth() + 1).padStart(2, "0")}-${String(d7.getDate()).padStart(2, "0")}`;
    const todayE = E.filter((e) => e.date === t), weekE = E.filter((e) => e.date >= iso7);
    const shown = E.filter((e) => (!logFilter.date || e.date === logFilter.date) && (!logFilter.d || String(e.do) === logFilter.d));
    viewEl.innerHTML = `
      <div class="page">
        <div class="head">
          <div>
            <span class="eyebrow">${icon("history")}Админ · ижро журнали</span>
            <h1>Ижро журнали</h1>
            <div class="head__sub">Ҳар бир киритилган «амалда» ёзуви. Ўчирилган ёзув жамлардан ҳам олиб ташланади.</div>
          </div>
          <div class="head__right"><a class="btn btn--gold" href="export.xlsx">${icon("download")}Excel (журнал билан)</a></div>
        </div>
        <div class="kpis kpis--6 kpis--row">
          ${kpi("history", "Жами ёзувлар", fmt(E.length), "та", "", "", 1)}
          ${kpi("calendar-days", "Бугун", fmt(todayE.length), "та", moneyShort(sum(todayE)), "", 3)}
          ${kpi("activity", "Охирги 7 кун", moneyPair(sum(weekE))[0], moneyPair(sum(weekE))[1], `${weekE.length} та ёзув`, "", 5)}
          ${kpi("coins", "Жами ўзлаштирилган", moneyPair(D.city.fact.cost)[0], moneyPair(D.city.fact.cost)[1], `режа ${moneyShort(D.city.plan.cost)}`, "", 7)}
          ${kpi("check-check", "Бажарилган ишлар", D.works.filter((w) => workState(w) === "done").length, `/ ${D.works.length}`, `${D.works.filter((w) => workState(w) === "doing").length} та жараёнда`, "", 2)}
          ${kpi("calendar-check", "Охирги ёзув", E[0] ? dmy(E[0].date) : "—", "", E[0] ? E[0].at : "", "", 8)}
        </div>
        <div class="lgrid">
          <div class="card">
            <div class="card__head"><h3>Кунлик ўзлаштириш</h3><span class="muted">млн сўм</span></div>
            <div class="chart"><canvas id="ch-log"></canvas></div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Ёзувлар</h3>
              <div class="tools tools--inline">
                <label class="field">${icon("calendar-days")}<input type="date" data-lf="date" value="${logFilter.date}" max="${t}" aria-label="Сана"></label>
                <label class="field">${icon("map")}<select data-lf="d" aria-label="Туман"><option value="">Барча туманлар</option>
                  ${D.districts.map((d, i) => `<option value="${i + 1}" ${logFilter.d === String(i + 1) ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select></label>
              </div></div>
            <div class="card__body">${entriesTable(shown, true, true)}</div>
          </div>
        </div>
      </div>`;
    $$("[data-lf]", viewEl).forEach((x) => x.addEventListener("change", () => { logFilter[x.dataset.lf] = x.value; route(); }));
    bindDelete(viewEl);
    timelineChart($("#ch-log"));
    return [["Админ", "#/admin"], ["Ижро журнали"]];
  }

  /* Кунлар бўйича ўзлаштириш (журналдан) */
  function timelineChart(canvas, days = 30) {
    const byDay = new Map();
    D.entries.forEach((e) => byDay.set(e.date, (byDay.get(e.date) || 0) + (e.cost || 0)));
    const labels = [], vals = [], cum = [];
    const end = new Date();
    const first = D.entries.length ? new Date(D.entries[D.entries.length - 1].date) : end;
    const start = new Date(Math.max(first.getTime(), end.getTime() - (days - 1) * 864e5));
    let run = D.entries.filter((e) => new Date(e.date) < start).reduce((s, e) => s + (e.cost || 0), 0);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const v = byDay.get(iso) || 0;
      run += v;
      labels.push(iso.slice(8) + "." + iso.slice(5, 7)); vals.push(+v.toFixed(2)); cum.push(+run.toFixed(2));
    }
    if (!window.Chart || !canvas) return;
    mk(canvas, () => ({
      data: { labels, datasets: [
        { type: "bar", label: "Кунлик", data: vals, backgroundColor: "#22c55ecc", hoverBackgroundColor: "#22c55e", borderRadius: 4, maxBarThickness: 22, minBarLength: 2 },
        { type: "line", label: "Жами (ўсиб бориш)", data: cum, yAxisID: "y1", borderColor: "#fde047", backgroundColor: "#fde047", borderWidth: 2, tension: .25, pointRadius: 0 },
      ] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: anim(), interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", align: "end", labels: { color: C.text, boxWidth: 10, boxHeight: 10, font: { size: 11 } } },
                   tooltip: Object.assign({ callbacks: { label: (c) => ` ${c.dataset.label}: ${moneyShort(c.parsed.y)}` } }, tooltip) },
        scales: Object.assign(axes(), { y1: { position: "right", beginAtZero: true, ticks: { color: "#fde047", font: { size: 10.5 } }, grid: { display: false }, border: { display: false } } }),
      },
    }));
  }

  /* Excel юклаш */
  function renderAdminUpload() {
    const s = D.source, p = D.city.plan;
    viewEl.innerHTML = `
      <div class="page page--upload">
        <div class="head">
          <div>
            <span class="eyebrow">${icon("file-up")}Админ · маълумотлар базасини янгилаш</span>
            <h1>Excel файл юклаш</h1>
            <div class="head__sub">Манзилли дастур файли (охирги файл билан бир хил шаклда). Юклангач, барча бўлимлар, графиклар ва матнлар янги маълумот асосида қайта тузилади.</div>
          </div>
        </div>
        <div class="ugrid">
          <div class="card card--form">
            <div class="card__head"><h3>Янги файл</h3><span class="muted">.xlsx · 15 МБ гача</span></div>
            <div class="card__body">
              <label class="drop" data-drop>
                <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" data-file hidden>
                ${icon("file-spreadsheet")}<b data-fname>Файлни шу ерга ташланг ёки танланг</b>
                <span class="muted small">Устунлар: № · Бажариладиган ишлар · ТП · Маҳалла · F–M (режа ва маблағ) · N–AO (ТП маълумотлари)</span>
              </label>
              <ul class="checklist">
                <li>${icon("circle-check")}Ижро журнали сақланади ва янги ишларга қайта боғланади</li>
                <li>${icon("circle-check")}Юклаш пайтида бошқа фойдаланувчиларда «Маълумотлар ўзгартирилмоқда» белгиси чиқади</li>
                <li>${icon("circle-check")}Файл формати мос келмаса, база ўзгармайди</li>
              </ul>
              <div class="eform__msg" data-umsg hidden></div>
              <div class="eform__btns"><button type="button" class="btn btn--gold" data-upload disabled>${icon("upload")}Юклаш ва янгилаш</button></div>
              <div class="uresult" data-uresult hidden></div>
            </div>
          </div>
          <div class="card">
            <div class="card__head"><h3>Ҳозирги маълумотлар</h3></div>
            <div class="card__body">
              <table class="kv">
                <tr><th>Файл</th><td>${esc(s.file)}</td></tr><tr><th>Юкланган</th><td>${esc(s.imported)}</td></tr>
                <tr><th>Туманлар / маҳаллалар</th><td>${D.districts.length} / ${D.mahallas.length}</td></tr>
                <tr><th>Ишлар / ТП</th><td>${p.works} / ${D.tps.length}</td></tr>
                <tr><th>Зарур маблағ</th><td class="t-money">${money(p.cost)}</td></tr>
                <tr><th>Ижро журнали</th><td>${D.entries.length} та ёзув</td></tr>
              </table>
              <h4 class="sub-h">Юклашлар тарихи</h4>
              <div data-uhist><div class="muted small">Юкланмоқда…</div></div>
            </div>
          </div>
        </div>
      </div>`;
    const input = $("[data-file]", viewEl), drop = $("[data-drop]", viewEl), btn = $("[data-upload]", viewEl);
    const msg = $("[data-umsg]", viewEl), out = $("[data-uresult]", viewEl);
    let file = null;
    const pick = (f) => {
      file = f || null;
      $("[data-fname]", viewEl).textContent = file ? `${file.name} · ${fmt(file.size / 1024, 0)} КБ` : "Файлни шу ерга ташланг ёки танланг";
      btn.disabled = !file;
      msg.hidden = true;
    };
    input.addEventListener("change", () => pick(input.files[0]));
    ["dragover", "dragenter"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
    ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("is-over")));
    drop.addEventListener("drop", (e) => { e.preventDefault(); pick(e.dataTransfer.files[0]); });
    btn.addEventListener("click", async () => {
      if (!file) return;
      if (!confirm("Барча маълумотлар шу файл асосида янгиланади. Давом этасизми?")) return;
      btn.disabled = true;
      btn.innerHTML = `<span class="spin"></span>Юкланмоқда…`;
      const fd = new FormData();
      fd.append("file", file);
      const j = await post("panel/upload", fd, true);
      btn.innerHTML = `${icon("upload")}Юклаш ва янгилаш`;
      icons();
      if (!j.ok) { msg.className = "eform__msg eform__msg--err"; msg.textContent = j.error || "Хатолик"; msg.hidden = false; btn.disabled = false; return; }
      toast("База янгиланди — сайт барча фойдаланувчилар учун янгиланди");
      await refreshData(true);
      const r = $("[data-uresult]", viewEl);
      if (r) {
        r.innerHTML = `<b>${icon("circle-check")}Муваффақиятли юкланди</b>
          <table class="kv"><tr><th>Ишлар</th><td>${j.before.works} → <b>${j.works}</b></td></tr>
          <tr><th>Маблағ</th><td>${moneyShort(j.before.cost)} → <b>${moneyShort(j.cost)}</b></td></tr>
          <tr><th>Туман / маҳалла / ТП</th><td>${j.districts} / ${j.mahallas} / ${j.sections}</td></tr>
          <tr><th>Журнал ёзувлари</th><td>${j.entries_linked} та боғланди${j.entries_orphan ? `, <span class="t-warn">${j.entries_orphan} та иш топилмади</span>` : ""}</td></tr></table>`;
        r.hidden = false;
        icons();
      }
    });
    fetch("panel/uploads", { credentials: "same-origin" }).then((r) => r.json()).then((j) => {
      const el = $("[data-uhist]", viewEl);
      if (!el) return;
      el.innerHTML = (j.items || []).length ? `<table class="tbl tbl--compact"><thead><tr><th>Файл</th><th>Сана</th><th class="r">Ишлар</th></tr></thead><tbody>${j.items.map((x) =>
        `<tr><td>${esc(x.name)}</td><td class="nowrap">${new Date(x.at).toLocaleString("ru-RU").slice(0, 17)}</td><td class="r">${x.summary.works || "—"}</td></tr>`).join("")}</tbody></table>`
        : `<div class="muted small">Ҳали файл юкланмаган — маълумотлар дастлабки файлдан олинган.</div>`;
    }).catch(() => {});
    return [["Админ", "#/admin"], ["Excel юклаш"]];
  }

  /* =========================================================
     Маршрутлаш
     ========================================================= */
  const PAGES = { home: renderHome, progress: renderProgress, analytics: renderAnalytics,
                  "admin-log": renderAdminLog, "admin-upload": renderAdminUpload };
  let current = null;

  function parse() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
    const view = LISTS[parts[0]] || PAGES[parts[0]] ? parts[0] : "home";
    return { view, key: parts[1] || null };
  }

  function showError(err) {
    console.error(err);
    clearCharts();
    current = null;
    viewEl.innerHTML = `<div class="crash">${icon("triangle-alert")}<div><b>Саҳифани кўрсатишда хатолик юз берди</b>
      <p>${esc(err && err.message ? err.message : err)}</p>
      <p class="muted small">Саҳифани янгиланг (Ctrl+F5). Хато такрорланса, шу матнни юборинг.</p>
      <a class="btn btn--gold" href="#/home">${icon("house")}Бош саҳифага қайтиш</a></div></div>`;
    icons();
  }

  function route() {
    try { routeInner(); } catch (err) { showError(err); }
  }

  let lastRoute = "";
  function routeInner() {
    const { view, key } = parse();
    // Админ бошқа саҳифага ўтса — «ўзгартирилмоқда» белгиси олинади
    if (lockState.on && location.hash !== lastRoute) releaseLock();
    lastRoute = location.hash;
    let crumbs;
    if (ADMIN_VIEWS.includes(view) && !IS_ADMIN) {
      clearCharts();
      crumbs = renderLogin();
      current = "login";
    } else if (PAGES[view]) {
      clearCharts();
      crumbs = PAGES[view]();
      current = view;
    } else if (current === view && $("[data-detail]", viewEl)) {
      crumbs = showDetail(view, key);
    } else {
      crumbs = renderMD(view, key);
      current = view;
    }
    $$("[data-nav]").forEach((a) => a.classList.toggle("is-active", a.dataset.nav === view));
    $("[data-crumbs]").innerHTML = crumbs.map(([label, href], i) =>
      (i ? icon("chevron-right") : "") + (href ? `<a href="${href}">${esc(label)}</a>` : `<span>${esc(label)}</span>`)).join("");
    icons();
  }

  function icons() { if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } }); }

  /* ---------- Глобал қидирув ---------- */
  function initSearch() {
    const box = $("[data-search]"), input = $("[data-search-input]"), out = $("[data-search-results]");
    let items = [], active = -1;
    const close = () => { out.hidden = true; active = -1; };
    const hl = () => items.forEach((el, i) => el.classList.toggle("is-active", i === active));

    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      if (isSecret(q)) {          // махфий сўз — админ панелига
        input.value = ""; close(); input.blur();
        location.hash = "#/admin";
        return;
      }
      if (q.length < 2) { close(); return; }
      const res = [];
      D.districts.forEach((d) => { if ((d.name + " " + d.lat).toLowerCase().includes(q)) res.push(["map", d.name + " тумани", `${d.mahallas.length} маҳалла`, "Туман", "#/districts/" + d.slug]); });
      D.mahallas.forEach((m) => { if ((m.name + " " + m.lat).toLowerCase().includes(q)) res.push(["house", m.name, district(m.d).name + " тумани", "Маҳалла", "#/mahallas/" + m.id]); });
      D.tps.forEach((t) => { if (("тп-" + t.n + " tp-" + t.n + " " + t.ps + " " + t.fd).toLowerCase().includes(q)) res.push(["zap", "ТП-" + t.n, mahalla(t.m).name + ", " + district(t.d).name, "ТП", "#/tps/" + t.id]); });
      D.works.forEach((w) => { if (w.text.toLowerCase().includes(q)) res.push([cat(w.cat).icon, "№" + w.no + " · " + w.title.slice(0, 60), mahalla(w.m).name + ", " + district(w.d).name, "Иш", "#/works/" + w.id]); });
      out.innerHTML = res.length ? res.slice(0, 16).map(([ic, t, s, type, href]) =>
        `<a class="sr" href="${href}">${icon(ic)}<span class="sr__body"><b>${esc(t)}</b><span>${esc(s)}</span></span><span class="sr__type">${type}</span></a>`).join("")
        : `<div class="sr-empty">Ҳеч нарса топилмади</div>`;
      items = $$(".sr", out); active = -1; out.hidden = false; icons();
    });
    input.addEventListener("keydown", (e) => {
      if (out.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, items.length - 1); hl(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); hl(); }
      else if (e.key === "Enter") { const t = items[Math.max(active, 0)]; if (t) { e.preventDefault(); location.hash = t.getAttribute("href"); close(); input.value = ""; input.blur(); } }
      else if (e.key === "Escape") { close(); input.blur(); }
    });
    out.addEventListener("click", (e) => { if (e.target.closest(".sr")) { close(); input.value = ""; } });
    document.addEventListener("click", (e) => { if (!box.contains(e.target)) close(); });
  }

  /* ---------- Клавиатура ва жадвал қаторлари ---------- */
  function initKeys() {
    document.addEventListener("keydown", (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (e.key === "/") { e.preventDefault(); $("[data-search-input]").focus(); return; }
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && LISTS[current]) {
        const rows = $$(".row", viewEl);
        if (!rows.length) return;
        e.preventDefault();
        let i = rows.findIndex((r) => r.classList.contains("is-active"));
        i = e.key === "ArrowDown" ? Math.min(i + 1, rows.length - 1) : Math.max(i - 1, 0);
        location.hash = rows[i].getAttribute("href");
      }
    });
    viewEl.addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-href]");
      if (tr && !e.target.closest("a")) location.hash = tr.dataset.href;
    });
  }

  /* ---------- Ишга тушириш ---------- */
  function initSidebar() {
    const counts = { districts: D.districts.length, mahallas: D.mahallas.length, works: D.works.length, tps: D.tps.length,
                     goals: D.goals.length, entries: D.entries.length };
    $$("[data-count]").forEach((el) => { el.textContent = counts[el.dataset.count]; });
    const c = D.city, pr = progressOf(c);
    $("[data-side-health]").innerHTML = `${ring(pr, pr > 0 ? "warn" : "crit", fmtPct(pr) + "%")}
      <div><b>Дастур ижроси</b><span>Режа ${moneyShort(c.plan.cost)} · амалда ${c.fact.cost ? moneyShort(c.fact.cost) : "0"}</span></div>`;
    $("[data-source]").textContent = `Манба: ${D.source.file} · ${D.source.imported}` +
      (D.entries.length ? ` · охирги ижро: ${D.entries[0].at}` : "");
    applyAdminUI();
  }

  if (window.Chart) {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.color = C.text;
  }
  window.addEventListener("error", (e) => { if ($(".boot", viewEl)) showError(e.error || e.message); });
  try { initSidebar(); } catch (err) { console.error(err); }
  initSearch();
  initKeys();
  initZoom();
  $("[data-logout]").addEventListener("click", async () => {
    releaseLock();
    await post("panel/logout");
    IS_ADMIN = false;
    applyAdminUI();
    toast("Админ панелидан чиқилди");
    location.hash = "#/home";
  });
  window.addEventListener("hashchange", route);
  route();
  setTimeout(poll, 3000);
})();
