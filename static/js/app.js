/* Обод маҳалла — бир бетли интерфейс */
(function () {
  "use strict";

  const D = JSON.parse(document.getElementById("app-data").textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const viewEl = $("[data-view]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Формат ---------- */
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (v, d = 0) => (v == null || isNaN(v)) ? "—" :
    Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })
      .replace(/,/g, " ").replace(".", ",");
  const money = (v) => v >= 1000 ? fmt(v / 1000, 1) + " млрд сўм" : fmt(v, v < 10 ? 1 : 0) + " млн сўм";
  const qty = (v) => v == null ? "" : Number.isInteger(v) ? fmt(v, 0) : fmt(v, 3).replace(/0+$/, "").replace(/,$/, "");
  const mwh = (v, d = 1) => v == null ? "—" : fmt(v / 1000, d);
  const gwh = (v, d = 2) => v == null ? "—" : fmt(v / 1e6, d);
  /* ТП тоифаси юкланиш бўйича: 0–50% яшил, 50–60% сариқ, 60% дан юқори қизил */
  const loadLevel = (p) => p >= 60 ? "crit" : p >= 50 ? "warn" : "good";
  const vpos = (v) => Math.max(0, Math.min(100, (v - 200) / 60 * 100)).toFixed(2);

  const STATUS = { good: "Яшил", warn: "Сариқ", crit: "Қизил", none: "Маълумот йўқ" };
  const PRIO = { high: "Юқори", medium: "Ўрта", low: "Паст" };
  const GSTATUS = { planned: "Режалаштирилган", in_progress: "Жараёнда", done: "Бажарилди" };
  const LEVEL = { crit: "Қизил", warn: "Сариқ", info: "Маълумот" };

  /* Ёрқин палитра */
  const PALETTE = ["#38bdf8", "#f59e0b", "#22c55e", "#ef4444", "#a855f7", "#14b8a6",
                   "#f97316", "#ec4899", "#84cc16", "#6366f1", "#eab308", "#06b6d4"];
  const CAT_COLOR = { tp_capital: "#f97316", tp_current: "#facc15", upgrade: "#a855f7", new_gktp: "#ec4899",
                      lv_cable: "#38bdf8", hv_cable: "#6366f1", air_capital: "#22c55e", air_current: "#84cc16",
                      air_new: "#14b8a6", grsh: "#06b6d4", other: "#94a3b8" };
  const SC = { good: "#22c55e", warn: "#f59e0b", crit: "#ef4444" };
  const catLabel = (k) => (D.categories[k] || {}).label || k;

  /* ---------- Индекслар ---------- */
  const dById = new Map(D.districts.map((d) => [d.id, d]));
  const dBySlug = new Map(D.districts.map((d) => [d.slug, d]));
  const mById = new Map(D.mahallas.map((m) => [m.id, m]));
  const tById = new Map(D.tps.map((t) => [t.id, t]));
  const gById = new Map(D.goals.map((g) => [g.id, g]));
  D.goals.sort((a, b) => mById.get(a.m).name.localeCompare(mById.get(b.m).name, "uz"));
  D.districts.forEach((d, i) => { d.color = PALETTE[i % PALETTE.length]; });

  const district = (id) => dById.get(id);
  const mahalla = (id) => (id == null ? null : mById.get(id));
  const mName = (t) => (t.m == null ? "Маҳалла аниқланмаган" : mahalla(t.m).name);

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
  const score = (s, status) => `
    <div class="score">${ring(s, status, fmt(s), "lg")}
      <div><div class="score__label">Саломатлик индекси</div>${pill(status, STATUS[status])}</div></div>`;

  /* ---------- Графиклар ---------- */
  const charts = [];
  function clearCharts() { charts.splice(0).forEach((c) => c.destroy()); }
  const C = { line: "#f8fafc", grid: "rgba(255,255,255,.07)", text: "#a1a1aa", panel: "#131315" };
  const tooltip = { backgroundColor: "#18181b", borderColor: "#3f3f46", borderWidth: 1, titleColor: "#fafafa", bodyColor: "#e4e4e7", padding: 10 };

  function comboChart(canvas, labels, bars, barLabel, line, lineLabel, colors) {
    if (!window.Chart || !canvas) return;
    const datasets = [{ type: "bar", label: barLabel, data: bars, backgroundColor: colors.map((c) => c + "cc"),
                        hoverBackgroundColor: colors, borderRadius: 5, maxBarThickness: 36 }];
    if (line) datasets.push({ type: "line", label: lineLabel, data: line, yAxisID: "y1", borderColor: "#fde047",
                              backgroundColor: "#fde047", borderWidth: 2, tension: .3, pointRadius: 4,
                              pointBackgroundColor: colors, pointBorderColor: "#fde047", pointBorderWidth: 1.5 });
    charts.push(new Chart(canvas, {
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: reduceMotion ? false : { duration: 650 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: !!line, position: "top", align: "end", labels: { color: C.text, boxWidth: 10, boxHeight: 10, font: { size: 11 } } },
          tooltip: Object.assign({ callbacks: { label: (c) => " " + c.dataset.label + ": " + fmt(c.parsed.y, 1) } }, tooltip),
        },
        scales: Object.assign({
          x: { ticks: { color: C.text, font: { size: 10.5 }, autoSkip: false, maxRotation: 50 }, grid: { display: false }, border: { color: C.grid } },
          y: { ticks: { color: C.text, font: { size: 10.5 } }, grid: { color: C.grid }, border: { display: false } },
        }, line ? { y1: { position: "right", min: 0, suggestedMax: 40, ticks: { color: "#fde047", font: { size: 10.5 }, callback: (v) => v + "%" }, grid: { display: false }, border: { display: false } } } : {}),
      },
    }));
  }

  function donut(canvas, values, colors, labels, fmtFn) {
    if (!window.Chart || !canvas) return;
    charts.push(new Chart(canvas, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: C.panel, borderWidth: 3, hoverOffset: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "72%", animation: reduceMotion ? false : { duration: 700 },
                 plugins: { legend: { display: false },
                            tooltip: Object.assign({ callbacks: { label: (c) => " " + c.label + ": " + (fmtFn ? fmtFn(c.parsed) : fmt(c.parsed)) } }, tooltip) } },
    }));
  }

  /* =========================================================
     Бош саҳифа
     ========================================================= */
  function renderHome() {
    const c = D.city, p = D.program, j = D.project;
    viewEl.innerHTML = `
      <div class="home">
        <div class="head head--home">
          <div>
            <span class="eyebrow">${icon("map-pin")}Тошкент шаҳри · «Обод маҳалла» лойиҳаси</span>
            <div class="city-line">
              <span><b>${D.districts.length}</b> та туман</span>
              <span><b>${fmt(c.tp_count)}</b> та трансформатор</span>
              <span><b>${fmt(c.consumers)}</b> та истеъмолчи</span>
              <span><b>${fmt(c.capacity_mva, 1)}</b> МВА қувват</span>
              <span>кунлик <b>${mwh(c.daily_kwh, 0)}</b> МВт·соат</span>
              <span>йиллик <b>${fmt(c.yearly_kwh / 1e9, 2)}</b> ТВт·соат</span>
            </div>
          </div>
          <div class="head__right">${score(Math.round(j.health), j.status)}</div>
        </div>
        <div class="kpis kpis--4">
          ${kpi("zap", "Трансформаторлар", fmt(j.tp_count), "та", "", "", 1)}
          ${kpi("users", "Истеъмолчилар", fmt(j.consumers), "та", "", `<span class="bar bar--split"><i style="width:${j.household_pct}%"></i></span>`, 2)}
          ${kpi("battery-charging", "Ўрнатилган қувват", fmt(j.capacity_mva, 1), "МВА", "", bar(j.load_pct * 1.25, "cyan"), 3)}
          ${kpi("gauge", "Ўртача юкланиш", fmt(j.load_pct, 1), "%", "", loadBar(j.load_pct), 4)}
          ${kpi("activity", "Кунлик истеъмол", mwh(j.daily_kwh, 0), "МВт·соат", "", "", 5)}
          ${kpi("chart-column", "Йиллик истеъмол", gwh(j.yearly_kwh, 1), "ГВт·соат", "", "", 6)}
          ${kpi("house", "Маҳаллалар", fmt(p.mahallas), "та", "", "", 1)}
          ${kpi("coins", "Дастур бюджети", fmt(p.budget / 1000, 1), "млрд сўм", "", "", 7)}
        </div>
        <div class="home__grid">
          <div class="card">
            <div class="card__head"><h3>Туманлар кесимида лойиҳа ТП лари</h3><span class="muted hide-narrow">Йиллик ГВт·соат · юкланиш %</span></div>
            <div class="chart"><canvas id="ch-districts"></canvas></div>
          </div>
          <div class="card status-card">
            <div class="card__head"><h3>ТП ҳолати (юкланиш)</h3><span class="muted">${fmt(j.tp_count)} та</span></div>
            <div class="donut"><canvas id="ch-status"></canvas><div class="donut__c"><b>${fmt(j.good)}</b><span>яшил</span></div></div>
            <ul class="legend">
              <li><i class="dot" style="background:${SC.good}"></i>Яшил · 0–50%<b>${fmt(j.good)}</b></li>
              <li><i class="dot" style="background:${SC.warn}"></i>Сариқ · 50–60%<b>${fmt(j.warn)}</b></li>
              <li><i class="dot" style="background:${SC.crit}"></i>Қизил · 60%+<b>${fmt(j.crit)}</b></li>
            </ul>
          </div>
          <div class="card status-card">
            <div class="card__head"><h3>Дастур ишлари таркиби</h3><span class="muted">${money(p.budget)}</span></div>
            <div class="donut"><canvas id="ch-cats"></canvas><div class="donut__c"><b>${p.works}</b><span>та иш</span></div></div>
            <ul class="legend legend--scroll">
              ${p.cats.map((k) => `<li><i class="dot" style="background:${CAT_COLOR[k.kind]}"></i>${esc(catLabel(k.kind))}<b>${money(k.cost)}</b></li>`).join("")}
            </ul>
          </div>
        </div>
      </div>`;
    comboChart($("#ch-districts"), D.districts.map((d) => d.name), D.districts.map((d) => +((d.proj.yearly_kwh || 0) / 1e6).toFixed(1)),
      "Йиллик истеъмол, ГВт·соат", D.districts.map((d) => d.proj.load_pct || 0), "Юкланиш, %", D.districts.map((d) => d.color));
    donut($("#ch-status"), [j.good, j.warn, j.crit], [SC.good, SC.warn, SC.crit], ["Яшил", "Сариқ", "Қизил"]);
    donut($("#ch-cats"), p.cats.map((k) => k.cost), p.cats.map((k) => CAT_COLOR[k.kind]), p.cats.map((k) => catLabel(k.kind)), (v) => money(v));
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
      search: (d) => d.name + " " + d.lat,
      tools: () => sortSelect([["name", "Номи бўйича"], ["consumers", "Истеъмолчилар"], ["yearly", "Йиллик истеъмол"], ["budget", "Дастур бюджети"], ["health", "Саломатлик (пастдан)"]]),
      sort: { name: (a, b) => a.name.localeCompare(b.name, "uz"), consumers: (a, b) => b.sys.consumers - a.sys.consumers,
              yearly: (a, b) => b.sys.yearly_kwh - a.sys.yearly_kwh, budget: (a, b) => b.budget - a.budget,
              health: (a, b) => a.sys.health - b.sys.health },
      row: (d) => `
        <span class="row__badge" style="color:${d.color};border-color:${d.color}66;background:${d.color}1a">${esc(d.name[0])}</span>
        <div class="row__body"><span class="row__title">${esc(d.name)}</span>
          <span class="row__sub">${fmt(d.sys.tp_count)} ТП · ${d.mahallas.length} маҳалла · ${money(d.budget)}</span></div>
        <div class="row__side">${ring(Math.round(d.sys.health), d.sys.status, fmt(d.sys.health), "xs")}</div>`,
      detail: districtDetail,
      total: {
        row: () => `
          <span class="row__badge row__badge--total">${icon("building-2")}</span>
          <div class="row__body"><span class="row__title">Тошкент шаҳри</span>
            <span class="row__sub">Жами · ${fmt(D.city.tp_count)} ТП · ${D.mahallas.length} маҳалла · ${money(D.program.budget)}</span></div>
          <div class="row__side">${ring(Math.round(D.city.health), D.city.status, fmt(D.city.health), "xs")}</div>`,
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
      tools: () => districtSelect() + sortSelect([["name", "Номи бўйича"], ["budget", "Дастур бюджети"], ["tps", "ТП сони"], ["consumers", "Истеъмолчилар"]]),
      sort: { name: (a, b) => a.name.localeCompare(b.name, "uz"), budget: (a, b) => b.budget - a.budget,
              tps: (a, b) => b.tps.length - a.tps.length, consumers: (a, b) => (b.stats.consumers || 0) - (a.stats.consumers || 0) },
      row: (m) => {
        const g = gById.get(m.goal);
        return `
          ${g ? `<i class="dot dot--${g.priority}" title="${PRIO[g.priority]} устуворлик"></i>` : `<i class="dot dot--muted"></i>`}
          <div class="row__body"><span class="row__title">${esc(m.name)}</span>
            <span class="row__sub">${esc(district(m.d).name)} · ${m.tps.length} ТП · ${m.works} иш</span></div>
          <div class="row__side"><span class="t-money nowrap">${fmt(m.budget, m.budget < 100 ? 1 : 0)} <small>млн</small></span></div>`;
      },
      detail: mahallaDetail,
      total: {
        row: () => `
          <span class="row__badge row__badge--total">${icon("sigma")}</span>
          <div class="row__body"><span class="row__title">Жами</span>
            <span class="row__sub">Барча ${D.mahallas.length} маҳалла · ${fmt(D.mtotal.tp_count || 0)} ТП · ${D.program.works} иш</span></div>
          <div class="row__side"><span class="t-money nowrap">${fmt(D.program.budget / 1000, 1)} <small>млрд</small></span></div>`,
        detail: mahallaTotal,
      },
      summary: () => `${D.mahallas.length} та маҳалла`,
    },
    tps: {
      title: "Трансформаторлар",
      items: () => D.tps,
      key: (t) => String(t.id),
      find: (k) => tById.get(+k),
      search: (t) => "тп-" + t.n + " tp-" + t.n + " " + mName(t) + " " + (t.m ? mahalla(t.m).lat : "") + " " + t.ps + " " + t.fd,
      filters: { district: (t, v) => String(t.d) === v, status: (t, v) => t.status === v,
                 src: (t, v) => (v === "prog" ? t.prog : v === "obod" ? t.obod : v === "none" ? t.m == null : true) },
      tools: () => districtSelect() + segFilter("status", [["", "Барчаси"], ["good", "Яшил"], ["warn", "Сариқ"], ["crit", "Қизил"]]) +
        segFilter("src", [["", "Ҳаммаси"], ["prog", "Дастур"], ["obod", "Обод"], ["none", "Маҳалласиз"]]) +
        sortSelect([["name", "Тартиб бўйича"], ["score", "Саломатлик (пастдан)"], ["load", "Юкланиш"], ["consumers", "Истеъмолчилар"]]),
      sort: { name: null, load: (a, b) => b.lf - a.lf, consumers: (a, b) => b.ct - a.ct, score: (a, b) => a.score - b.score },
      row: (t) => `
        ${ring(Math.min(100, t.lf * 100), t.status, Math.round(t.lf * 100) + "%", "xs")}
        <div class="row__body"><span class="row__title">ТП-${esc(t.n)}</span>
          <span class="row__sub">${t.cap} кВА · ${esc(mName(t))} · ${esc(district(t.d).name)}</span></div>
        <div class="row__side">${pill(t.status, STATUS[t.status])}</div>`,
      detail: tpDetail,
      summary: () => `${D.tps.length} та ТП`,
    },
    goals: {
      title: "Мақсадлар",
      items: () => D.goals,
      key: (g) => String(g.id),
      find: (k) => gById.get(+k),
      search: (g) => g.title + " " + mahalla(g.m).name + " " + mahalla(g.m).lat + " " + district(mahalla(g.m).d).name,
      filters: { district: (g, v) => String(mahalla(g.m).d) === v, priority: (g, v) => g.priority === v },
      tools: () => districtSelect() + segFilter("priority", [["", "Барчаси"], ["high", "Юқори"], ["medium", "Ўрта"], ["low", "Паст"]]) +
        sortSelect([["name", "Маҳалла номи"], ["budget", "Бюджет"], ["works", "Ишлар сони"], ["prio", "Устуворлик"]]),
      sort: { name: null, budget: (a, b) => b.budget - a.budget, works: (a, b) => b.tasks.length - a.tasks.length,
              prio: (a, b) => ({ high: 0, medium: 1, low: 2 }[a.priority] - { high: 0, medium: 1, low: 2 }[b.priority]) },
      row: (g) => {
        const m = mahalla(g.m);
        return `
          <i class="dot dot--${g.priority}" title="${PRIO[g.priority]} устуворлик"></i>
          <div class="row__body"><span class="row__title">${esc(m.name)} <span class="muted small">· ${esc(district(m.d).name)}</span></span>
            <span class="row__sub">${esc(g.title)}</span></div>
          <div class="row__side"><span class="t-money nowrap">${fmt(g.budget, g.budget < 100 ? 1 : 0)} <small>млн</small></span></div>`;
      },
      detail: goalDetail,
      summary: () => `${D.goals.length} та · ${money(D.program.budget)}`,
    },
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
    const st = listState[name] || (listState[name] = { q: "", f: {}, sort: "name" });
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
    if (cfg.total && (!key || key === "all")) {
      listState[name].active = "all";
      markActive(name);
      clearCharts();
      const det = $("[data-detail]", viewEl);
      const crumbs = cfg.total.detail(det);
      det.scrollTop = 0;
      return crumbs;
    }
    let item = key ? cfg.find(key) : null;
    if (!item) item = filtered(name)[0] || cfg.items()[0];
    listState[name].active = cfg.key(item);
    markActive(name);
    clearCharts();
    const det = $("[data-detail]", viewEl);
    const crumbs = cfg.detail(item, det);
    det.scrollTop = 0;
    return crumbs;
  }

  /* ---------- Туман ---------- */
  function districtDetail(d, el) {
    const s = d.sys;
    const ms = d.mahallas.map(mahalla);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("map")}Туман</span>
          <h1>${esc(d.name)} тумани</h1>
          <div class="head__sub">РЭС: ${esc(d.res)} · ${fmt(s.tp_count)} та трансформатор · дастурда ${ms.length} та маҳалла, ${d.prog_tps} та ТП</div>
        </div>
        <div class="head__right">${score(Math.round(s.health), s.status)}</div>
      </div>
      <div class="kpis kpis--6">
        ${kpi("users", "Истеъмолчилар", fmt(s.consumers), "", `${fmt(s.household)} аҳоли · ${fmt(s.commercial)} улгуржи`, "", 2)}
        ${kpi("battery-charging", "Қувват", fmt(s.capacity_mva, 1), "МВА", `Юкланиш ${fmt(s.load_pct, 1)}%`, bar(s.load_pct * 1.25, "cyan"), 3)}
        ${kpi("activity", "Кунлик истеъмол", mwh(s.daily_kwh, 0), "МВт·соат", `Йиллик: ${gwh(s.yearly_kwh, 1)} ГВт·соат`, "", 5)}
        ${kpi("triangle-alert", "Сариқ ва қизил ТП", fmt(s.problems), `/ ${fmt(s.tp_count)}`, `${fmt(s.warn)} сариқ · ${fmt(s.crit)} қизил`, "", 4)}
        ${kpi("target", "Дастур бюджети", fmt(d.budget / 1000, 2), "млрд сўм", `${d.works} та иш · ${ms.length} маҳалла`, "", 7)}
        ${kpi("coins", "2-илова бўйича", fmt(d.budget_official / 1000, 2), "млрд сўм", d.unassigned ? `${d.unassigned} та ТП маҳалласиз (Обод файли)` : "расмий жами", "", 8)}
      </div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Дастурдаги маҳаллалар</h3><span class="muted">Маҳаллани танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Маҳалла</th><th class="r">ТП</th><th class="r hide-narrow">Истеъмолчи</th><th class="r">Ишлар</th><th class="r">Бюджет, млн</th><th>Устуворлик</th></tr></thead>
              <tbody>${ms.map((m) => {
                const g = gById.get(m.goal);
                return `<tr data-href="#/mahallas/${m.id}">
                  <td><b>${esc(m.name)}</b></td><td class="r">${m.tps.length}</td><td class="r hide-narrow">${fmt(m.stats.consumers || 0)}</td>
                  <td class="r">${m.works}</td><td class="r t-money">${fmt(m.budget, 1)}</td>
                  <td>${g ? pill(g.priority, PRIO[g.priority]) : "—"}</td></tr>`;
              }).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Маҳаллалар бюджети</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-d"></canvas></div>
        </div>
      </div>`;
    comboChart($("#ch-d", el), ms.map((m) => m.name), ms.map((m) => m.budget), "Бюджет, млн сўм", null, null,
      ms.map((_, i) => PALETTE[i % PALETTE.length]));
    return [["Тошкент", "#/home"], ["Туманлар", "#/districts"], [d.name]];
  }

  /* ---------- Тошкент шаҳри (жами) ---------- */
  function cityDetail(el) {
    const s = D.city, p = D.program;
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("building-2")}Жами · ${D.districts.length} та туман</span>
          <h1>Тошкент шаҳри</h1>
          <div class="head__sub">Тизим ҳисоботи бўйича ${fmt(s.tp_count)} та трансформатор · дастурда ${p.mahallas} та маҳалла, ${p.tps} та ТП</div>
        </div>
        <div class="head__right">${score(Math.round(s.health), s.status)}</div>
      </div>
      <div class="kpis kpis--6">
        ${kpi("users", "Истеъмолчилар", fmt(s.consumers), "", `${fmt(s.household)} аҳоли · ${fmt(s.commercial)} улгуржи`, "", 2)}
        ${kpi("battery-charging", "Қувват", fmt(s.capacity_mva, 1), "МВА", `Юкланиш ${fmt(s.load_pct, 1)}%`, bar(s.load_pct * 1.25, "cyan"), 3)}
        ${kpi("activity", "Кунлик истеъмол", mwh(s.daily_kwh, 0), "МВт·соат", `Йиллик: ${gwh(s.yearly_kwh, 1)} ГВт·соат`, "", 5)}
        ${kpi("triangle-alert", "Сариқ ва қизил ТП", fmt(s.problems), `/ ${fmt(s.tp_count)}`, `${fmt(s.warn)} сариқ · ${fmt(s.crit)} қизил`, "", 4)}
        ${kpi("target", "Дастур бюджети", fmt(p.budget / 1000, 2), "млрд сўм", `${p.works} та иш · ${p.mahallas} маҳалла`, "", 7)}
        ${kpi("coins", "2-илова бўйича", fmt(p.budget_official / 1000, 2), "млрд сўм", "расмий жами", "", 8)}
      </div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Туманлар</h3><span class="muted">Туманни танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Туман</th><th class="r">ТП</th><th class="r hide-narrow">Истеъмолчи</th><th class="r">Маҳалла</th><th class="r">Бюджет, млн</th></tr></thead>
              <tbody>${D.districts.map((d) => `<tr data-href="#/districts/${d.slug}">
                <td><i class="dot" style="background:${d.color}"></i> <b>${esc(d.name)}</b></td><td class="r">${fmt(d.sys.tp_count)}</td>
                <td class="r hide-narrow">${fmt(d.sys.consumers)}</td>
                <td class="r">${d.mahallas.length}</td><td class="r t-money">${fmt(d.budget, 1)}</td></tr>`).join("")}
                <tr class="tr-total"><td><b>Жами</b></td><td class="r"><b>${fmt(s.tp_count)}</b></td><td class="r hide-narrow"><b>${fmt(s.consumers)}</b></td>
                <td class="r"><b>${p.mahallas}</b></td><td class="r t-money"><b>${fmt(p.budget, 1)}</b></td></tr></tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Туманлар бюджети</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-city"></canvas></div>
        </div>
      </div>`;
    comboChart($("#ch-city", el), D.districts.map((d) => d.name), D.districts.map((d) => d.budget), "Бюджет, млн сўм", null, null,
      D.districts.map((d) => d.color));
    return [["Тошкент", "#/home"], ["Туманлар", "#/districts"], ["Тошкент шаҳри (жами)"]];
  }

  /* ---------- Барча маҳаллалар (жами) ---------- */
  function mahallaTotal(el) {
    const s = D.mtotal, p = D.program, has = s.tp_count > 0;
    const pr = { high: 0, medium: 0, low: 0 };
    D.goals.forEach((g) => { pr[g.priority]++; });
    const ms = D.mahallas.slice().sort((a, b) => b.budget - a.budget);
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("sigma")}Жами · «Обод маҳалла» 2027</span>
          <h1>Барча маҳаллалар</h1>
          <div class="head__sub">${p.mahallas} та маҳалла · ${fmt(s.tp_count || 0)} та ТП · ${p.works} та иш</div>
        </div>
        <div class="head__right">${has ? score(Math.round(s.health), s.status) : ""}</div>
      </div>
      <div class="kpis kpis--6">
        ${kpi("users", "Истеъмолчилар", has ? fmt(s.consumers) : "—", "", has ? `${fmt(s.household)} аҳоли · ${fmt(s.commercial)} улгуржи` : "", "", 2)}
        ${kpi("battery-charging", "Қувват", has ? fmt(s.capacity_mva, 1) : "—", "МВА", has ? `Юкланиш ${fmt(s.load_pct, 1)}%` : "", has ? bar(s.load_pct * 1.25, "cyan") : "", 3)}
        ${kpi("activity", "Кунлик истеъмол", has ? mwh(s.daily_kwh, 0) : "—", "МВт·соат", has ? `Ойлик: ${gwh(s.monthly_kwh, 2)} ГВт·соат` : "", "", 5)}
        ${kpi("triangle-alert", "Сариқ ва қизил ТП", fmt(s.problems || 0), `/ ${fmt(s.tp_count || 0)}`, `${fmt(s.warn || 0)} сариқ · ${fmt(s.crit || 0)} қизил`, "", 4)}
        ${kpi("target", "Дастур бюджети", fmt(p.budget / 1000, 2), "млрд сўм", `${p.works} та иш`, "", 7)}
        ${kpi("list-checks", "Юқори устуворлик", pr.high, "та", `${pr.medium} ўрта · ${pr.low} паст`, "", 1)}
      </div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Маҳаллалар (бюджет бўйича)</h3><span class="muted">Маҳаллани танланг</span></div>
          <div class="card__body">
            <table class="tbl"><thead><tr><th>Маҳалла</th><th class="hide-narrow">Туман</th><th class="r">ТП</th><th class="r">Ишлар</th><th class="r">Бюджет, млн</th></tr></thead>
              <tbody>${ms.map((m) => {
                const g = gById.get(m.goal);
                return `<tr data-href="#/mahallas/${m.id}"><td>${g ? `<i class="dot dot--${g.priority}" title="${PRIO[g.priority]} устуворлик"></i> ` : ""}<b>${esc(m.name)}</b></td><td class="hide-narrow">${esc(district(m.d).name)}</td>
                  <td class="r">${m.tps.length}</td><td class="r">${m.works}</td><td class="r t-money">${fmt(m.budget, 1)}</td></tr>`;
              }).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Туманлар бўйича маҳаллалар бюджети</h3><span class="muted hide-narrow">млн сўм</span></div>
          <div class="chart"><canvas id="ch-mt"></canvas></div>
        </div>
      </div>`;
    comboChart($("#ch-mt", el), D.districts.map((d) => d.name), D.districts.map((d) => d.budget), "Бюджет, млн сўм", null, null,
      D.districts.map((d) => d.color));
    return [["Тошкент", "#/home"], ["Маҳаллалар", "#/mahallas"], ["Жами"]];
  }

  /* ---------- Маҳалла ---------- */
  function mahallaDetail(m, el) {
    const s = m.stats, d = district(m.d), g = gById.get(m.goal);
    const tps = m.tps.map((id) => tById.get(id));
    const has = s.tp_count > 0;
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("house")}Маҳалла</span>
          <h1>${esc(m.name)} маҳалласи</h1>
          <div class="head__sub"><a href="#/districts/${d.slug}">${esc(d.name)} тумани</a> · ${tps.length} та ТП · ${m.works} та иш (2027)</div>
        </div>
        <div class="head__right">${has ? score(Math.round(s.health), s.status) : ""}</div>
      </div>
      <div class="kpis kpis--6">
        ${kpi("users", "Истеъмолчилар", has ? fmt(s.consumers) : "—", "", has ? `${fmt(s.household)} аҳоли · ${fmt(s.commercial)} улгуржи` : "ТП маълумоти йўқ", "", 2)}
        ${kpi("battery-charging", "Қувват", has ? fmt(s.capacity_kva) : "—", has ? "кВА" : "", has ? `Юкланиш ${fmt(s.load_pct, 1)}%` : "", has ? bar(s.load_pct * 1.25, "cyan") : "", 3)}
        ${kpi("activity", "Кунлик истеъмол", has ? fmt(s.daily_kwh) : "—", has ? "кВт·соат" : "", has ? `Ойлик: ${mwh(s.monthly_kwh)} МВт·соат` : "", "", 5)}
        ${kpi("waves", "Ўртача кучланиш", has && s.avg_voltage ? fmt(s.avg_voltage, 1) : "—", has ? "В" : "", has ? `${s.problems} та ТП сариқ/қизил` : "", "", 6)}
        ${kpi("target", "Дастур бюджети", money(m.budget).replace(" сўм", ""), "сўм", `${m.works} та иш`, "", 7)}
        ${kpi("list-checks", "Устуворлик", g ? PRIO[g.priority] : "—", "", g ? GSTATUS[g.status] + " · 2027" : "", "", 1)}
      </div>
      <div class="dgrid dgrid--2">
        <div class="card">
          <div class="card__head"><h3>Трансформатор пунктлари</h3><span class="muted">${has ? "ТП ни танланг" : ""}</span></div>
          <div class="card__body">
            ${has ? `<table class="tbl"><thead><tr><th>ТП</th><th class="r">Қувват</th><th class="r">Истеъмолчи</th><th>Юкланиш</th><th class="hide-narrow">А / Б / С, В</th><th class="r">Ҳолат</th></tr></thead>
              <tbody>${tps.map((t) => `<tr data-href="#/tps/${t.id}">
                <td><b>ТП-${esc(t.n)}</b></td><td class="r">${t.cap} кВА</td><td class="r">${t.ct}</td>
                <td>${loadBar(t.lf * 100)}${fmt(t.lf * 100, 1)}%</td>
                <td class="hide-narrow">${volt(t)}</td>
                <td class="r">${pill(t.status, STATUS[t.status])}</td></tr>`).join("")}</tbody></table>`
            : `<div class="empty">${icon("cable")}<span>Бу маҳалла бўйича дастурда ТП рақамлари кўрсатилмаган —<br>ишлар кабель тармоқларига тегишли.</span></div>`}
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Маҳалла мақсади · 2027</h3>${g ? pill(g.priority, PRIO[g.priority]) : ""}</div>
          ${g ? `
          <div class="card__body goal-brief">
            <h2>${esc(g.title)}</h2>
            <p class="quote">${esc(g.summary)}</p>
            <div class="facts facts--3">
              <div><span>Бюджет</span><b class="t-money">${money(g.budget)}</b></div>
              <div><span>Ишлар</span><b>${g.tasks.length} та</b></div>
              <div><span>Тегишли ТП</span><b>${g.tpn} та</b></div>
            </div>
            ${catBars(g)}
            <div><a class="btn btn--gold" href="#/goals/${g.id}">${icon("arrow-right")}Мақсад батафсил</a></div>
          </div>` : `<div class="empty">Мақсад белгиланмаган</div>`}
        </div>
      </div>`;
    return [["Тошкент", "#/home"], [d.name, "#/districts/" + d.slug], [m.name]];
  }

  const volt = (t) => ["va", "vb", "vc"].map((k, i) =>
    `<span class="t-${t.ph[["А", "Б", "С"][i]]}">${t[k] == null ? "—" : fmt(t[k], 1)}</span>`).join(" / ");

  function catBars(g) {
    const max = Math.max(...g.cats.map((c) => c.cost), 1);
    return `<div class="catbars">${g.cats.map((c) => `
      <div class="catbar"><span class="catbar__l"><i class="dot" style="background:${CAT_COLOR[c.kind]}"></i>${esc(catLabel(c.kind))}</span>
        <span class="catbar__t"><i style="width:${(c.cost / max * 100).toFixed(1)}%;background:${CAT_COLOR[c.kind]}"></i></span>
        <b>${fmt(c.cost, c.cost < 100 ? 1 : 0)}</b></div>`).join("")}</div>`;
  }

  /* ---------- ТП ---------- */
  let tpTab = "main";
  function tpDetail(t, el) {
    const m = mahalla(t.m), d = district(t.d);
    const sib = m ? m.tps : D.tps.filter((x) => x.d === t.d && x.m == null).map((x) => x.id);
    const idx = sib.indexOf(t.id);
    const prev = idx > 0 ? sib[idx - 1] : null, next = idx >= 0 && idx < sib.length - 1 ? sib[idx + 1] : null;
    const lp = t.lf * 100, ll = loadLevel(lp);
    const phases = [["А", t.va], ["Б", t.vb], ["С", t.vc]];
    const dev = t.avgv == null ? null : t.avgv - 230;
    const hhPct = t.ct ? t.ch / t.ct * 100 : 0;
    const mLink = m ? `<a href="#/mahallas/${m.id}">${esc(m.name)} маҳалласи</a>` : `<span class="t-warn">Маҳалла аниқланмаган</span>`;
    const kvRow = (k, v) => `<tr><th>${k}</th><td>${v == null || v === "" ? "—" : v}</td></tr>`;
    el.innerHTML = `
      <div class="head">
        <div>
          <span class="eyebrow">${icon("utility-pole")}Трансформатор пункти</span>
          <h1>ТП-${esc(t.n)}</h1>
          <div class="head__sub">${mLink} · <a href="#/districts/${d.slug}">${esc(d.name)} тумани</a> · ${t.cap} кВА
            ${pill(t.status, "Юкланиш: " + STATUS[t.status])}${t.prog ? pill("info", "Дастурда") : ""}${t.obod ? pill("plain", "Обод файлида") : ""}</div>
        </div>
        <div class="head__right">
          <div class="seg seg--tabs"><button type="button" data-tabbtn="main" class="${tpTab === "main" ? "is-active" : ""}">Таҳлил</button><button type="button" data-tabbtn="data" class="${tpTab === "data" ? "is-active" : ""}">Барча маълумотлар</button></div>
          <a class="btn" href="#/tps/${prev}" ${prev ? "" : 'aria-disabled="true"'} title="Олдинги ТП">${icon("chevron-left")}</a>
          <a class="btn" href="#/tps/${next}" ${next ? "" : 'aria-disabled="true"'} title="Кейинги ТП">${icon("chevron-right")}</a>
          ${score(t.score, t.hs)}
        </div>
      </div>
      <div class="dgrid dgrid--tp" data-tab="main" ${tpTab === "main" ? "" : "hidden"}>
        <div class="card">
          <div class="card__head"><h3>Юкланиш</h3><span class="muted">ўртача суткалик</span></div>
          <div class="gauge is-${ll}" style="--p:${lp.toFixed(1)}"><div class="gauge__arc"></div>
            <div class="gauge__v"><b>${fmt(lp, 1)}%</b><span>${fmt(t.actual, 1)} / ${t.cap} кВА</span></div></div>
          <div class="facts">
            <div><span>Қувват захираси</span><b>${fmt(t.reserve, 1)} кВА</b></div>
            <div><span>Чўққи (тахминий)</span><b>~${t.peak}%</b></div>
            <div><span>cos φ</span><b class="${t.pf != null && t.pf < 0.92 ? "t-warn" : ""}">${t.pf == null ? "—" : fmt(t.pf, 3)}</b></div>
            <div><span>Зичлик</span><b>${t.cap ? fmt(t.ct / t.cap, 2) : "—"} / кВА</b></div>
          </div>
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
            <div><span>Ток А / Б / С</span><b>${[t.ia, t.ib, t.ic].map((x) => x == null ? "—" : fmt(x, 0)).join(" / ")} А</b></div>
            <div><span>Фазалар фарқи</span><b>${fmt(t.imb, 1)}%</b></div>
            <div><span>Оғиш</span><b>${dev == null ? "—" : (dev > 0 ? "+" : "") + fmt(dev, 1) + " В"}</b></div>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Электр истеъмоли</h3></div>
          ${t.anomaly ? `<div class="alert">${icon("cpu")}<span>Қиймат манфий/нол — ҳисоблагич маълумоти нотўғри, йиғиндиларга қўшилмаган.</span></div>` : ""}
          <div class="facts facts--3">
            <div><span>Кунлик, кВт·с</span><b>${fmt(t.dk, 1)}</b></div>
            <div><span>Ойлик, МВт·с</span><b>${mwh(t.mk)}</b></div>
            <div><span>Йиллик, МВт·с</span><b>${mwh(t.yk)}</b></div>
          </div>
          <div class="facts facts--3" style="margin-top:8px">
            <div><span>Истеъмолчилар</span><b>${t.ct}</b></div>
            <div><span>Аҳоли</span><b>${t.ch} (${fmt(hhPct)}%)</b></div>
            <div><span>Улгуржи</span><b>${t.cc}</b></div>
          </div>
          ${t.kpc != null ? `<div class="muted small" style="margin-top:10px">1 истеъмолчига ойига <b class="t-money">${fmt(t.kpc)}</b> кВт·соат · шаҳар ўртачаси ${fmt(D.city.kwh_per_consumer)}</div>` : ""}
        </div>
        <div class="card">
          <div class="card__head"><h3>Таҳлил ва тавсиялар</h3><span class="muted">${t.issues.length} та</span></div>
          <div class="card__body">
            ${t.issues.length ? `<ul class="issues">${t.issues.map((i) => `
              <li class="issue is-${i.level}">${icon(i.icon)}<div>
                <div class="issue__t">${esc(i.title)} ${pill(i.level, LEVEL[i.level])}</div>
                <p>${esc(i.text)}</p><p class="issue__a">→ ${esc(i.advice)}</p></div></li>`).join("")}</ul>`
            : `<div class="ok-box">${icon("circle-check")}<div><b>Барча кўрсаткичлар меъёрда</b><span>Кучланиш, юкланиш, зичлик ва cos φ бўйича муаммо аниқланмади.</span></div></div>`}
          </div>
        </div>
      </div>
      <div class="dgrid dgrid--data" data-tab="data" ${tpTab === "data" ? "" : "hidden"}>
        <div class="card"><div class="card__head"><h3>Жойлашув ва ҳисоб</h3><span class="muted">тизим ҳисоботи</span></div>
          <table class="kv">${kvRow("Туман (РЭС)", esc(d.name) + " · " + esc(d.res))}${kvRow("Маҳалла", esc(mName(t)))}
            ${kvRow("ТП рақами", esc(t.n))}${kvRow("Подстанция", esc(t.ps))}${kvRow("Фидер", esc(t.fd))}
            ${kvRow("Эгаси", esc(t.own))}${kvRow("Баланс ҳисоблагичи", esc(t.mtr))}${kvRow("ТТ коэффициенти", t.kt == null ? null : fmt(t.kt))}
            ${kvRow("Ҳисоблагич ҳолати", esc(t.st))}</table></div>
        <div class="card"><div class="card__head"><h3>Техник кўрсаткичлар</h3></div>
          <table class="kv">${kvRow("Қувват", t.cap + " кВА")}${kvRow("Истеъмолчилар (жами / аҳоли / улгуржи)", `${t.ct} / ${t.ch} / ${t.cc}`)}
            ${kvRow("Кунлик истеъмол", fmt(t.dk, 3) + " кВт·с")}${kvRow("Ойлик / йиллик", `${fmt(t.mk, 0)} / ${fmt(t.yk, 0)} кВт·с`)}
            ${kvRow("Кучланиш А / Б / С", [t.va, t.vb, t.vc].map((x) => x == null ? "—" : fmt(x, 1)).join(" / ") + " В")}
            ${kvRow("Ток А / Б / С", [t.ia, t.ib, t.ic].map((x) => x == null ? "—" : fmt(x, 1)).join(" / ") + " А")}
            ${kvRow("Жами қувват / кеча", `${fmt(t.kva, 1)} / ${fmt(t.kvay, 1)} кВА`)}${kvRow("cos φ", t.pf == null ? null : fmt(t.pf, 3))}
            ${kvRow("Юкланганлик", `${fmt(t.lf, 3)} (${fmt(lp, 1)}%)`)}</table></div>
        <div class="card"><div class="card__head"><h3>Манба ва тузатиш</h3></div>
          <table class="kv">${kvRow("2027 дастурида", t.prog ? "Ҳа — маҳалла ишлари рўйхатида" : "Йўқ")}
            ${kvRow("«Обод маҳалла» файлида", t.obod ? "Ҳа" : "Йўқ")}
            ${t.obod ? kvRow("Эски ёзув (нотўғри)", `<s class="muted">${esc(t.od)} · ${esc(t.om)}</s>`) + kvRow("Тўғри", `${esc(d.name)} · ${esc(mName(t))}`) : ""}</table>
          ${t.obod && !t.m ? `<p class="muted small" style="margin-top:10px">Бу ТП дастурда тилга олинмагани учун маҳалласини манбалардан аниқлаб бўлмади.</p>` : ""}</div>
        <div class="card"><div class="card__head"><h3>Ҳисобланган кўрсаткичлар</h3></div>
          <table class="kv">${kvRow("Ҳақиқий юклама", fmt(t.actual, 1) + " кВА")}${kvRow("Қувват захираси", fmt(t.reserve, 1) + " кВА")}
            ${kvRow("Чўққи юкланиш (тахминий)", "~" + t.peak + "%")}${kvRow("Фазалар фарқи", fmt(t.imb, 1) + "%")}
            ${kvRow("Юкланиш тоифаси", STATUS[t.status] + " (0–50% яшил, 50–60% сариқ, 60%+ қизил)")}${kvRow("Саломатлик индекси", t.score + " / 100")}</table></div>
      </div>`;
    $$("[data-tabbtn]", el).forEach((btn) => btn.addEventListener("click", () => {
      tpTab = btn.dataset.tabbtn;
      $$("[data-tabbtn]", el).forEach((x) => x.classList.toggle("is-active", x === btn));
      $$("[data-tab]", el).forEach((x) => { x.hidden = x.dataset.tab !== tpTab; });
    }));
    const crumbs = [["Тошкент", "#/home"], [d.name, "#/districts/" + d.slug]];
    if (m) crumbs.push([m.name, "#/mahallas/" + m.id]);
    crumbs.push(["ТП-" + t.n]);
    return crumbs;
  }

  /* ---------- Мақсад ---------- */
  function goalDetail(g, el) {
    const m = mahalla(g.m), d = district(m.d);
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
        ${kpi("wallet", "Бюджет", money(g.budget).replace(" сўм", ""), "сўм", "2.1-илова бўйича", "", 7)}
        ${kpi("list-checks", "Ишлар", g.tasks.length, "та", `${g.cats.length} йўналиш`, "", 1)}
        ${kpi("zap", "Тегишли ТП", g.tpn, "та", "дастурда тилга олинган", "", 3)}
        ${kpi("users", "Фойда олувчилар", g.benef ? fmt(g.benef) : "—", g.benef ? "истеъмолчи" : "", g.benef ? "шу ТП лар орқали" : "ТП маълумоти йўқ", "", 2)}
      </div>
      <div class="dgrid dgrid--goal">
        <div class="card">
          <div class="card__head"><h3>Режадаги ишлар</h3><span class="muted">${g.tasks.length} та · ${money(g.budget)}</span></div>
          <div class="card__body">
            <ol class="tasks">${g.tasks.map((t) => `
              <li class="task"><span class="task__i" style="color:${CAT_COLOR[t.kind]};border-color:${CAT_COLOR[t.kind]}55;background:${CAT_COLOR[t.kind]}14">${icon(t.icon)}</span>
                <div class="task__b"><b>${esc(t.title)}</b><p><span style="color:${CAT_COLOR[t.kind]}">${esc(catLabel(t.kind))}</span>${t.tps ? ` · ТП: ${esc(t.tps)}` : ""}</p></div>
                <div class="task__m"><b>${t.qty != null ? qty(t.qty) + " " + esc(t.unit) : esc(t.unit)}</b><span>${money(t.cost)}</span></div></li>`).join("")}
            </ol>
          </div>
        </div>
        <div class="card">
          <div class="card__head"><h3>Йўналишлар ва натижалар</h3></div>
          <div class="card__body">
            <p class="quote">${esc(g.summary)}</p>
            ${catBars(g)}
            <ul class="effects" style="margin-top:14px">${g.effects.map((e) => `<li>${icon("circle-check")}<span>${esc(e)}</span></li>`).join("")}</ul>
            <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">
              <a class="btn btn--gold" href="#/mahallas/${m.id}">${icon("house")}Маҳаллага ўтиш</a>
              <a class="btn" href="#/districts/${d.slug}">${icon("map")}${esc(d.name)} тумани</a>
            </div>
          </div>
        </div>
      </div>`;
    return [["Тошкент", "#/home"], ["Мақсадлар", "#/goals"], [m.name]];
  }

  /* =========================================================
     Маршрутлаш
     ========================================================= */
  let current = null;

  function parse() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
    const view = LISTS[parts[0]] ? parts[0] : "home";
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

  function routeInner() {
    const { view, key } = parse();
    let crumbs;
    if (view === "home") {
      clearCharts();
      crumbs = renderHome();
      current = "home";
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
      if (q.length < 2) { close(); return; }
      const res = [];
      D.districts.forEach((d) => { if ((d.name + " " + d.lat).toLowerCase().includes(q)) res.push(["map", d.name + " тумани", `${d.mahallas.length} маҳалла`, "Туман", "#/districts/" + d.slug]); });
      D.mahallas.forEach((m) => { if ((m.name + " " + m.lat).toLowerCase().includes(q)) res.push(["house", m.name, district(m.d).name + " тумани", "Маҳалла", "#/mahallas/" + m.id]); });
      D.tps.forEach((t) => { if (("тп-" + t.n + " tp-" + t.n).toLowerCase().includes(q)) res.push(["zap", "ТП-" + t.n, mName(t) + ", " + district(t.d).name, "ТП", "#/tps/" + t.id]); });
      out.innerHTML = res.length ? res.slice(0, 14).map(([ic, t, s, type, href]) =>
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
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && current !== "home") {
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
      if (tr) location.hash = tr.dataset.href;
    });
  }

  /* ---------- Ишга тушириш ---------- */
  function initSidebar() {
    const counts = { districts: D.districts.length, mahallas: D.mahallas.length, tps: D.tps.length, goals: D.goals.length };
    $$("[data-count]").forEach((el) => { el.textContent = counts[el.dataset.count]; });
    const c = D.project;
    $("[data-side-health]").innerHTML = `${ring(Math.round(c.health), c.status, fmt(c.health))}
      <div><b>Лойиҳа ТП лари</b><span>${fmt(c.good)} яшил · ${fmt(c.warn)} сариқ · ${fmt(c.crit)} қизил</span></div>`;
  }

  if (window.Chart) {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.color = C.text;
  }
  window.addEventListener("error", (e) => { if ($(".boot", viewEl)) showError(e.error || e.message); });
  try { initSidebar(); } catch (err) { console.error(err); }
  initSearch();
  initKeys();
  window.addEventListener("hashchange", route);
  route();
})();
