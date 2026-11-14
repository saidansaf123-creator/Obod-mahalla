"""«Обод маҳалла 2027» манзилли дастури — ягона манба файлини ўқиш.

Файл тузилмаси (варақ «Манзилли дастур»):
  1–2-қатор  сарлавҳа, 3–4-қатор устун номлари, 5-қатор шаҳар жами;
  туман қатори: A — рим рақами (I, II …), B — «… тумани», F–M — туман жами (формула);
  иш қатори: A — тартиб рақами, B — иш мазмуни, C — ТП, D/E — маҳалла, F–M — режа ҳажми ва нархи,
             N–AO — шу ишга тегишли ТП секциясининг тизимдаги маълумотлари;
  охирида «Изоҳ» қаторлари.

Бир иш (туман ичида бир хил №) бир нечта қаторда келиши мумкин — ТП нинг ҳар бир секцияси алоҳида
қаторда, иш ҳажми ва нархи эса ҳар қаторда такрорланади. Шунинг учун иш бир марта ҳисобланади,
секциялар эса ишга бириктирилади.
"""
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from .analysis import TPMetrics

SOURCE_NAME = "Обод_махалла_2027.xlsx"

# Устунлар (1 дан бошлаб)
COL = dict(
    no=1, text=2, tp=3, mahalla=4, mahalla_group=5, km_total=6, lv_km=7, hv_km=8, tr_total=9,
    tr_upgrade=10, new_gktp=11, grsh=12, cost=13, res=14, substation=15, feeder=16, tp_number=17,
    owner=18, master=19, cons_total=20, cons_household=21, cons_industrial=22, capacity=23, meter=24,
    ct_ratio=25, daily_kwh=26, kva_yesterday=27, kva_total=28, pf=29, pf_l1=30, pf_l2=31, pf_l3=32,
    cur_l1=33, cur_l2=34, cur_l3=35,
    # Файл сарлавҳасида кучланиш устунлари L2, L1, L3 тартибида
    volt_l2=36, volt_l1=37, volt_l3=38,
    load=39, meter_state=40, note=41,
)

# Иш тоифалари: (номи, белги, ўлчов, режа устуни)
CATEGORIES = OrderedDict([
    ("new_gktp", ("Янги ГКТП ўрнатиш", "square-plus", "дона", "new_gktp")),
    ("tr_upgrade", ("Трансформаторни катта қувватлисига алмаштириш", "circle-arrow-up", "дона", "tr_upgrade")),
    ("hv_cable", ("Юқори кучланишли кабел (6–10 кВ)", "cable", "км", "hv_km")),
    ("lv_cable", ("Паст кучланишли кабел (0,4 кВ)", "plug-zap", "км", "lv_km")),
    ("grsh", ("ГРШ-0,4 кВ модернизацияси", "server", "дона", "grsh")),
    ("other", ("Ҳажми кўрсатилмаган", "wrench", "", None)),
])

# Режа/амал кўрсаткичлари
PLAN_FIELDS = OrderedDict([
    ("lv_km", ("Паст кучланишли кабел", "км")),
    ("hv_km", ("Юқори кучланишли кабел", "км")),
    ("tr_upgrade", ("Трансформатор алмаштириш", "дона")),
    ("new_gktp", ("Янги ГКТП", "дона")),
    ("grsh", ("ГРШ модернизацияси", "дона")),
    ("cost", ("Маблағ", "млн сўм")),
])

ROMAN = re.compile(r"^[IVXLC]+$")
CABLE = re.compile(r"(АВВГ|АПвПУ|АПВПу|АПвПу|ААШВ|АСБ)\s*[-–]?\s*([\d/]*\s*[хx×*]\s*\d+(?:\s*мм2?)?)", re.I)
TP_MENTION = re.compile(r"(?:ТП|TP)\s*[№#]?\s*[-–]?\s*(\d{2,5})|(\d{2,5})\s*[-–]?\s*сонли|ТП\s*(\d{2,5})")
KVA = re.compile(r"(\d{3,4})\s*(?:/\s*(?:10|6)\s*)?(?:кВА|кВа|кв\b|кВ\b|кВ\s*А)", re.I)


def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def text(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def clean_name(v):
    return re.sub(r"\s+", " ", re.sub(r"[“”\"«»]", "", str(v or ""))).strip()


def text_categories(t):
    """Иш матнидан тоифаларни аниқлаш (рақамлар билан солиштириш учун)."""
    s = t.lower()
    cats = set()
    if "грш" in s or "грщ" in s:
        cats.add("grsh")
    if "гктп" in s or "янги тп" in s or ("қўшимча" in s or "кушимча" in s) and "трансформатор" in s:
        cats.add("new_gktp")
    if ("трансформатор" in s and ("алмашт" in s or "қувват" in s or "кувват" in s or "ўрнатиш" in s)) \
            or "кувватни ошириш" in s or "қувватини ошириш" in s:
        cats.add("tr_upgrade")
    if "юқори кучланиш" in s or "юкори кучланиш" in s or "кл -10" in s or "кл-10" in s \
            or re.search(r"\b(10|6)\s*кв\b", s) and "0,4" not in s:
        cats.add("hv_cable")
    if "паст кучланиш" in s or "0,4 кв" in s or "0,4кв" in s or "хл - 0,4" in s:
        cats.add("lv_cable")
    return cats


def mentioned_tps(t):
    out = []
    for m in TP_MENTION.finditer(t):
        n = next(g for g in m.groups() if g)
        if n not in out and n not in ("240", "120", "150", "185", "630", "400", "250"):
            out.append(n)
    return out


@dataclass(eq=False)
class Section(TPMetrics):
    """Ишга бириктирилган ТП секцияси (тизимдаги ҳисоблагич маълумотлари)."""
    row: int
    res: str
    substation: str
    feeder: str
    number: str
    base_number: str
    owner: str
    master: str
    consumers_total: int
    consumers_household: int
    consumers_commercial: int
    capacity_kva: float
    meter_no: str
    ct_ratio: float
    daily_kwh: float
    kva_yesterday: float
    kva_total: float
    pf: float
    pf_l1: float
    pf_l2: float
    pf_l3: float
    current_a: float
    current_b: float
    current_c: float
    voltage_a: float  # L1
    voltage_b: float  # L2
    voltage_c: float  # L3
    load_factor: float
    meter_state: str
    note: str

    @property
    def monthly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 30

    @property
    def yearly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 365

    @property
    def has_data(self):
        return bool(self.capacity_kva) or self.daily_kwh is not None


@dataclass(eq=False)
class Work:
    district: int          # туман тартиби (1…12)
    number: int            # файлдаги №
    rows: list
    text: str
    tp_ref: str
    mahalla: str
    mahalla_group: str
    lv_km: float
    hv_km: float
    tr_upgrade: float
    new_gktp: float
    grsh: float
    cost: float
    km_total_file: float
    tr_total_file: float
    sections: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    text_file: str = ""      # файлдаги асл матн (тузатилган бўлса)

    @property
    def km_total(self):
        return (self.lv_km or 0) + (self.hv_km or 0)

    @property
    def tr_total(self):
        return (self.tr_upgrade or 0) + (self.new_gktp or 0)

    @property
    def categories(self):
        cats = [k for k, v in CATEGORIES.items() if v[3] and (getattr(self, v[3]) or 0) > 0]
        return cats or ["other"]

    @property
    def category(self):
        return self.categories[0]

    @property
    def title(self):
        """Маҳалла номи такрорланмасин: «“Лолазор” МФЙ …» → «…»."""
        t = re.sub(r'^\W*[“"«]?[^”"»]{1,40}[”"»]\s*МФЙ\s*', "", self.text).strip(" •-–,")
        # «Лолазор МФЙ да …», «Салар МФЙ. …» каби иккинчи такрорни ҳам олиб ташлаш
        first = re.escape(self.mahalla.split()[0]) if self.mahalla else ""
        if first:
            t = re.sub(rf"^\W*{first}\S*(\s+\S+)?\s+МФЙ\s*(да|даги|,|\.)?\s*", "", t, flags=re.I).strip(" •-–,.\"")
        t = t.strip(' "')
        return (t[:1].upper() + t[1:]) if t else self.text

    @property
    def cable_spec(self):
        m = CABLE.search(self.text)
        return re.sub(r"\s+", "", f"{m.group(1)} {m.group(2)}") if m else ""

    @property
    def target_kva(self):
        """Ўрнатиладиган трансформатор қуввати (матндан)."""
        if not (self.tr_upgrade or self.new_gktp):
            return None
        vals = [int(x) for x in KVA.findall(self.text) if int(x) in (160, 250, 320, 400, 630, 1000, 1250)]
        # Матнда кўпинча эски қувват ҳам ёзилади (400 → 630); янги қувват — каттаси, камида 630 кВА
        return max(vals + [630])

    @property
    def tp_mentions(self):
        return mentioned_tps(self.text)

    @property
    def text_categories(self):
        return sorted(text_categories(self.text))


@dataclass
class District:
    order: int
    roman: str
    name: str
    row: int
    file_totals: dict
    res: str = ""


@dataclass
class Source:
    path: Path
    sheet: str
    title: str
    subtitle: str
    notes: list
    city_file_totals: dict
    districts: list
    works: list
    issues: list
    row_count: int


TOTAL_KEYS = ["km_total", "lv_km", "hv_km", "tr_total", "tr_upgrade", "new_gktp", "grsh", "cost"]


def _totals(ws, r):
    return {k: num(ws.cell(r, COL[k]).value) or 0 for k in TOTAL_KEYS}


def find_source(data_dir):
    data_dir = Path(data_dir)
    exact = data_dir / SOURCE_NAME
    if exact.exists():
        return exact
    found = [p for p in data_dir.glob("*.xlsx") if not p.name.startswith("~$") and "обод" in p.name.lower()]
    if not found:
        raise FileNotFoundError(f"data/ папкасида «{SOURCE_NAME}» файли топилмади")
    return max(found, key=lambda p: p.stat().st_mtime)


def read(path) -> Source:
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]

    # E устуни бирлаштирилган катакларда — ҳар қаторга юқори катак қийматини ёйиш
    group = {}
    for rng in ws.merged_cells.ranges:
        if rng.min_col == COL["mahalla_group"] == rng.max_col:
            v = ws.cell(rng.min_row, rng.min_col).value
            for r in range(rng.min_row, rng.max_row + 1):
                group[r] = v

    def cell(r, k):
        return ws.cell(r, COL[k]).value

    districts, works, issues, notes = [], OrderedDict(), [], []
    city_totals, cur = None, None
    data_rows = 0
    for r in range(5, ws.max_row + 1):
        a, b = cell(r, "no"), cell(r, "text")
        if r == 5 or (a is None and b and "ЖАМИ" in str(b).upper()):
            city_totals = _totals(ws, r)
            continue
        if isinstance(a, str) and ROMAN.match(a.strip()):
            cur = District(len(districts) + 1, a.strip(), clean_name(b).replace(" тумани", "").strip(), r,
                           _totals(ws, r))
            districts.append(cur)
            continue
        if isinstance(a, str) and a.strip():
            notes.append(text(a))
            continue
        if a is None or cur is None:
            continue
        data_rows += 1
        key = (cur.order, int(a))
        w = works.get(key)
        vals = dict(
            text=text(b), tp_ref="" if cell(r, "tp") is None else str(cell(r, "tp")).strip(),
            mahalla=clean_name(cell(r, "mahalla")), mahalla_group=clean_name(group.get(r, cell(r, "mahalla_group"))),
            lv_km=num(cell(r, "lv_km")), hv_km=num(cell(r, "hv_km")), tr_upgrade=num(cell(r, "tr_upgrade")),
            new_gktp=num(cell(r, "new_gktp")), grsh=num(cell(r, "grsh")), cost=num(cell(r, "cost")),
            km_total_file=num(cell(r, "km_total")), tr_total_file=num(cell(r, "tr_total")),
        )
        if w is None:
            w = Work(district=cur.order, number=int(a), rows=[r], **vals)
            works[key] = w
        else:
            w.rows.append(r)
            same = all(getattr(w, k) == v for k, v in vals.items() if k not in ("mahalla_group",))
            if not same:
                issues.append(dict(kind="dup_diff", level="warn", district=cur.order, work=w.number, rows=w.rows[:],
                                   text="Бир хил рақамли иш қаторлари бир-биридан фарқ қилади — биринчи қатор олинди."))
        if cell(r, "tp_number"):
            sec = Section(
                row=r, res=text(cell(r, "res")), substation=text(cell(r, "substation")), feeder=text(cell(r, "feeder")),
                number=text(cell(r, "tp_number")), base_number=w.tp_ref, owner=text(cell(r, "owner")),
                master=text(cell(r, "master")),
                consumers_total=int(num(cell(r, "cons_total")) or 0),
                consumers_household=int(num(cell(r, "cons_household")) or 0),
                consumers_commercial=int(num(cell(r, "cons_industrial")) or 0),
                capacity_kva=num(cell(r, "capacity")) or 0, meter_no=text(cell(r, "meter")),
                ct_ratio=num(cell(r, "ct_ratio")), daily_kwh=num(cell(r, "daily_kwh")),
                kva_yesterday=num(cell(r, "kva_yesterday")), kva_total=num(cell(r, "kva_total")),
                pf=num(cell(r, "pf")), pf_l1=num(cell(r, "pf_l1")), pf_l2=num(cell(r, "pf_l2")), pf_l3=num(cell(r, "pf_l3")),
                current_a=num(cell(r, "cur_l1")), current_b=num(cell(r, "cur_l2")), current_c=num(cell(r, "cur_l3")),
                voltage_a=num(cell(r, "volt_l1")), voltage_b=num(cell(r, "volt_l2")), voltage_c=num(cell(r, "volt_l3")),
                load_factor=num(cell(r, "load")), meter_state=text(cell(r, "meter_state")), note=text(cell(r, "note")),
            )
            # Манфий/нол кунлик истеъмол — ҳисоблагич хатоси, тўғри қиймат эмас
            if sec.daily_kwh is not None and sec.daily_kwh <= 0:
                sec.daily_kwh = None
            # Маълумоти бутунлай бўш секциялар олинмайди
            if sec.has_data:
                w.sections.append(sec)
            if sec.res and not cur.res:
                cur.res = sec.res

    works = list(works.values())
    for w in works:
        _correct(w)
        _check_work(w, issues)
    _check_totals(districts, works, city_totals, issues)
    return Source(path=path, sheet=ws.title, title=text(ws.cell(1, 1).value), subtitle=text(ws.cell(2, 1).value),
                  notes=notes, city_file_totals=city_totals or {}, districts=districts, works=works,
                  issues=issues, row_count=data_rows)


def _q(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}".replace(".", ",")


def _generated_text(w):
    """Иш мазмуни рақамлар (G–L устунлари) асосида."""
    parts = []
    if w.new_gktp:
        parts.append(f"{_q(w.new_gktp)} та янги ГКТП ўрнатиш")
    if w.tr_upgrade:
        parts.append(f"{_q(w.tr_upgrade)} та трансформаторни катта қувватлисига алмаштириш")
    if w.hv_km:
        parts.append(f"{_q(w.hv_km)} км юқори кучланишли (6–10 кВ) кабел тармоғини янгилаш")
    if w.lv_km:
        parts.append(f"{_q(w.lv_km)} км паст кучланишли (0,4 кВ) кабел тармоғини янгилаш")
    if w.grsh:
        parts.append(f"{_q(w.grsh)} та ГРШ-0,4 кВ ни таъмирлаш")
    return f"“{w.mahalla}” МФЙ " + ("; ".join(parts) or "иш ҳажми кўрсатилмаган")


def _norm(cats):
    return {"cable" if c in ("lv_cable", "hv_cable") else c for c in cats}


def _correct(w):
    """Файлдаги аниқ хатоларни тузатиш — сайтга фақат тўғри маълумот чиқади.

    - ТП устунидаги «630» (янги ГКТП қуввати) ТП рақами эмас;
    - бир катак матни икки қаторга бўлиниб кетган жойлар (қатор кичик ҳарфдан бошланади ёки ёпилувчи
      қўштирноқ билан тугайди) ва матни рақамларга умуман тўғри келмайдиган қаторлар (масалан, матнда
      «ГРШ таъмирлаш», рақамларда кабел) — мазмун рақамлар бўйича ёзилади. Рақамлар тўғри деб олинади:
      улар нархлар билан мос (паст кучл. кабел ≈ 474 млн/км, юқори ≈ 273 млн/км, 3 та ГРШ = 16,2 млн).
    """
    if w.tp_ref in ("630", "400", "250") and not w.sections and "гктп" in w.text.lower():
        w.tp_ref = ""
    t = w.text
    fragment = bool(re.match(r"^[а-яёўқғҳ]", t)) or (t.endswith('"') and not t.startswith('"'))
    if t.startswith('"“'):                       # бўлинган катакнинг биринчи ярми
        t = t[1:].strip()
    tc = _norm(text_categories(t))
    nc = _norm(set(w.categories) - {"other"})
    if fragment or (tc and nc and not (tc & nc)) or ("grsh" in nc and nc == {"grsh"} and "grsh" not in tc):
        w.text_file, w.text = w.text, _generated_text(w)
    elif "grsh" in tc and "grsh" not in nc and nc:
        w.text_file, w.text = w.text, _generated_text(w)
    elif nc and not tc and not re.search(r"янгила|алмашт|ўрнат|урнат|ошир|ётқиз|ёткиз|таъмир|реконстр|тортиш|қуриш|модерн", t.lower()):
        # Матн чала (иш тури айтилмаган) — ҳажм рақамлардан қўшилади
        w.text_file, w.text = w.text, t.rstrip(" .;,") + " — " + _generated_text(w).split(" МФЙ ", 1)[1]
    else:
        # Матн тўғри, лекин рақамлардаги ГРШ ёки янги ГКТП тилга олинмаган — қўшиб ёзилади
        extra = []
        if "grsh" in nc and "grsh" not in tc:
            extra.append(f"{_q(w.grsh)} та ГРШ-0,4 кВ ни таъмирлаш")
        if "new_gktp" in nc and "new_gktp" not in tc:
            extra.append(f"{_q(w.new_gktp)} та янги ГКТП ўрнатиш")
        if extra:
            t = t.rstrip(" .;") + "; " + "; ".join(extra)
        if t != w.text:
            w.text_file, w.text = w.text, t


def _check_work(w, issues):
    def add(kind, level, msg):
        w.issues.append(dict(kind=kind, level=level, text=msg))
        issues.append(dict(kind=kind, level=level, district=w.district, work=w.number, rows=w.rows[:], text=msg))

    if len(w.rows) > 1:
        add("multi_row", "info", f"Иш {len(w.rows)} та қаторда ёзилган (ТП секциялари бўйича); ҳажм ва нарх "
                                 "ҳар қаторда такрорланган — бир марта ҳисобланди.")
    if w.cost is None:
        add("no_cost", "warn", "Зарур маблағ (M устуни) кўрсатилмаган.")
    if w.mahalla_group and w.mahalla and w.mahalla_group != w.mahalla:
        add("mahalla_mismatch", "warn", f"D устунида «{w.mahalla}», E устунида «{w.mahalla_group}» — D устуни олинди.")
    if w.tp_ref and not w.sections:
        if w.tp_ref in ("630", "400", "250") and ("гктп" in w.text.lower()):
            add("tp_is_capacity", "info", f"ТП устунида «{w.tp_ref}» — бу ТП рақами эмас, янги ГКТП қуввати.")
        else:
            add("tp_no_data", "info", f"ТП-{w.tp_ref} бўйича тизим маълумоти берилмаган.")
    for s in w.sections:
        if not s.has_data:
            add("section_empty", "warn", f"ТП-{s.number}: қувват ва истеъмол маълумотлари бўш.")
        elif s.daily_kwh is not None and s.daily_kwh <= 0:
            add("negative_kwh", "warn", f"ТП-{s.number}: кунлик истеъмол {s.daily_kwh:g} кВт·соат — ҳисоблагич хатоси.")
    if w.km_total_file is not None and abs((w.km_total_file or 0) - w.km_total) > 0.001:
        add("km_formula", "warn", "F устуни G+H йиғиндисига тенг эмас.")
    tc = set(w.text_categories)
    nc = set(w.categories) - {"other"}
    if "grsh" in nc and "grsh" not in tc:
        add("text_mismatch", "warn", "Рақамларда ГРШ бор, лекин иш матнида ГРШ ҳақида гап йўқ — матн ва рақамлар "
                                     "мос эмас (қатор силжиган бўлиши мумкин).")
    elif "grsh" in tc and "grsh" not in nc and nc:
        add("text_mismatch", "warn", "Матнда ГРШ таъмирлаш, рақамларда эса кабел/трансформатор — матн ва рақамлар мос эмас.")
    elif "grsh" in tc and not nc:
        add("text_mismatch", "warn", "Матнда ГРШ таъмирлаш, лекин ГРШ сони (L устуни) кўрсатилмаган.")
    if "lv_cable" in nc and "hv_cable" not in nc and "hv_cable" in tc and "lv_cable" not in tc:
        add("voltage_mismatch", "warn", "Матнда юқори кучланишли (6–10 кВ) кабел, ҳажм эса паст кучланиш (G) устунида.")
    if "hv_cable" in nc and "lv_cable" not in nc and "lv_cable" in tc and "hv_cable" not in tc:
        add("voltage_mismatch", "warn", "Матнда паст кучланишли (0,4 кВ) кабел, ҳажм эса юқори кучланиш (H) устунида.")


def _check_totals(districts, works, city, issues):
    for d in districts:
        ws = [w for w in works if w.district == d.order]
        calc = {k: sum((getattr(w, k) or 0) for w in ws) for k in TOTAL_KEYS}
        diff = {k: round(d.file_totals[k] - calc[k], 3) for k in TOTAL_KEYS if abs(d.file_totals[k] - calc[k]) > 0.001}
        d.calc_totals = calc
        if diff:
            issues.append(dict(kind="district_total", level="info", district=d.order, work=None, rows=[d.row],
                               text="Файлдаги туман жами такрорий қаторлар билан ҳисобланган: "
                                    + ", ".join(f"{k}: файлда {d.file_totals[k]:g}, такрорсиз {calc[k]:g}" for k in diff)))
