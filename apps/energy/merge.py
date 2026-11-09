"""Уч манбани бирлаштириш.

1. «Обод махалла.xlsx» — 205 ТП нинг техник маълумотлари тўғри, туман/маҳалла номлари нотўғри.
2. «TrLoadProfileReport(2).xlsx» — тизим ҳисоботи: Тошкентдаги барча ТП (РЭС, подстанция, фидер,
   истеъмолчилар, қувват, кучланиш, ток, cos φ, юкланиш).
3. «илова 2., 138 млрд (2) (2).xlsx» — 2027 йил «Обод маҳалла» дастури: туман → маҳалла → ишлар
   (ТП рақамлари ва нархлари билан).

Боғлаш қоидалари:
- Обод файлидаги ТП → тизим ҳисоботидаги қатор: ТП рақами + истеъмолчилар + қувват + кунлик истеъмол.
- Дастурдаги маҳалла → ТП: иш матнидаги ТП рақами (асосий рақам) + шу туман РЭСи.
- Тўғри туман — тизим ҳисоботидаги РЭС; тўғри маҳалла — дастурдаги маҳалла.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

from .analysis import TPMetrics

FILES = {
    "obod": "Обод махалла.xlsx",
    "trload": "TrLoadProfileReport(2).xlsx",
    "program": "илова 2., 138 млрд (2) (2).xlsx",
}
# Файл номи ўзгарса ҳам топилсин: аниқ ном бўлмаса, шу белги бўйича энг янги файл олинади
PATTERNS = {
    "obod": ("обод",),
    "trload": ("trload",),
    "program": ("илова",),
}


def find_file(data_dir, kind):
    data_dir = Path(data_dir)
    exact = data_dir / FILES[kind]
    if exact.exists():
        return exact
    found = [p for p in data_dir.glob("*.xls*")
             if not p.name.startswith("~$") and "бирлаштир" not in p.name.lower()
             and all(w in p.name.lower() for w in PATTERNS[kind])]
    if not found:
        raise FileNotFoundError(f"data/ папкасида «{FILES[kind]}» (ёки шунга ўхшаш номли) файл топилмади")
    return max(found, key=lambda p: p.stat().st_mtime)

# РЭС (тизимдаги ном) -> (кирилл, лотин)
RES = {
    "Bektemir TETK": ("Бектемир", "Bektemir"),
    "Chilonzor TETK": ("Чилонзор", "Chilonzor"),
    "Mirobod TETK": ("Миробод", "Mirobod"),
    "Mirzo Ulug‘bek TETK": ("Мирзо Улуғбек", "Mirzo Ulug'bek"),
    "Olmazor TETK": ("Олмазор", "Olmazor"),
    "Sergeli TETK": ("Сергели", "Sergeli"),
    "Shayxontohur TETK": ("Шайхонтоҳур", "Shayxontohur"),
    "Uchtepa TETK": ("Учтепа", "Uchtepa"),
    "Yakkasaroy TETK": ("Яккасарой", "Yakkasaroy"),
    "Yangihayot TETK": ("Янгиҳаёт", "Yangihayot"),
    "Yashnobod TETK": ("Яшнобод", "Yashnobod"),
    "Yunusobod TETK": ("Юнусобод", "Yunusobod"),
}
CYR_TO_RES = {v[0]: k for k, v in RES.items()}
# Дастур файлидаги туман сарлавҳалари (ёзилиши турлича)
PROGRAM_HEADERS = {
    "Миробод": "Миробод", "Мирзо Улуғбек": "Мирзо Улуғбек", "Олмазор": "Олмазор", "Учтепа": "Учтепа",
    "Чилонзор": "Чилонзор", "Шайхонтохур": "Шайхонтоҳур", "Шайхонтоҳур": "Шайхонтоҳур",
    "Юнусобод": "Юнусобод", "Яшнабод": "Яшнобод", "Яшнобод": "Яшнобод", "Янгиҳаёт": "Янгиҳаёт",
    "ергели": "Сергели", "Яккасарой": "Яккасарой", "Бектемир": "Бектемир",
}

MAHALLA_FIX = {
    "Тукимачи": "Тўқимачи", "Богсарой": "Боғсарой", "Дилбулок": "Дилбулоқ", "Мухандислар": "Муҳандислар",
    "Ю. Раджабий": "Ю. Ражабий", "А. Каххор": "А. Қаҳҳор", "Армугон": "Армуғон", "Мехригие": "Меҳригиё",
    "Сохибқирон": "Соҳибқирон", "Янги сергели": "Янги Сергели", "Хумоюн": "Ҳумоюн", "Шахрисабз": "Шаҳрисабз",
    "Олтинкул": "Олтинкўл", "Ат Термизий": "Ат-Термизий", "Мовароунахр": "Мовароуннаҳр",
    "Ш.Рашидов": "Ш. Рашидов", "Коратош": "Қоратош", "Катта Ёлонгоч ота": "Катта Ёлғоч ота",
    "Alimkent": "Алимкент", "Amir Temur": "Амир Темур", "Ахил обод": "Ахилобод", "Янги боғ": "Янгибоғ",
    "ВАТАНДОШ": "Ватандош", "Мохинур": "Моҳинур", "Х.Байқаро": "Ҳ. Бойқаро", "Юрт Обод": "Юртобод",
    "Хамдўст": "Ҳамдўст", "Ташисти": "Ташисти",
}

CATEGORIES = {
    "tp_capital": ("ТП мукаммал таъмирлаш", "wrench", "count"),
    "tp_current": ("ТП жорий таъмирлаш", "hammer", "count"),
    "upgrade": ("Трансформатор қувватини ошириш", "arrow-up-down", "count"),
    "new_gktp": ("Янги ГКТП ўрнатиш", "plus", "count"),
    "lv_cable": ("Паст кучланишли кабелни янгилаш", "cable", "km"),
    "hv_cable": ("Юқори кучланишли кабелни янгилаш", "zap", "km"),
    "air_capital": ("Ҳаво тармоғини мукаммал таъмирлаш", "utility-pole", "km"),
    "air_current": ("Ҳаво тармоғини жорий таъмирлаш", "utility-pole", "km"),
    "air_new": ("Ҳаво тармоғини янгилаш", "waypoints", "km"),
    "grsh": ("ГРШ-0,4 кВ модернизацияси", "cpu", "count"),
    "other": ("Бошқа ишлар", "circle-dot", "count"),
}

STATE_UZ = {
    "Введено в эксплуатацию": "Фойдаланишга топширилган",
    "Установлено": "Ўрнатилган",
    "Запускается в работу": "Ишга туширилмоқда",
}

AUX_RE = re.compile(r"ГРШ|ГРЩ|GRSH|dom|pod", re.I)
TP_RE1 = re.compile(r"(?:ТП|TP)\s*[-№]?\s*(\d{1,5})(?!\d)", re.I)
TP_RE2 = re.compile(r"(\d{1,5})\s*-?\s*с?с?онли")


def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def base_number(tp):
    m = re.match(r"^\s*0*(\d+)", str(tp))
    return (m.group(1) or "0") if m else ""


def full_key(tp):
    s = str(tp).strip().upper().replace(" ", "")
    m = re.match(r"^0*(\d+)(.*)$", s)
    return ((m.group(1) or "0") + m.group(2)) if m else s


def clean_text(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def clean_mahalla(s):
    s = re.sub(r"[“”\"«»]", "", str(s))
    s = re.sub(r"\s+", " ", s).strip().lstrip(".").strip()
    s = re.sub(r"\s+(МФЙ|маҳалласи|махалласи)$", "", s, flags=re.I).strip()
    return MAHALLA_FIX.get(s, s)


def categorize(text):
    t = text.lower().replace("ё", "е")
    if "грш" in t:
        return "grsh"
    if ("гктп" in t or "gktp" in t) and any(k in t for k in ("ўрнат", "урнат", "o'rnat")):
        return "new_gktp"
    if "кабел" not in t and "kabel" not in t and any(k in t for k in (
            "катта қувват", "катта кувват", "katta quvvat", "қувватлисига", "кувватлисига",
            "куввати ошир", "кувватни ошир", "қувватини ошир", "630 ква", "630/10", "630/6", "630 кв")):
        return "upgrade"
    hv = any(k in t for k in ("юқори кучланиш", "юкори кучланиш", "юкори  кучланиш", "6,10", "10 кв", "10кв",
                              "6 кв", "кл -10", "апвпу", "katta kuchlanish", "3/1х240", "3/1x240"))
    cable = "кабел" in t or "kabel" in t
    if hv and (cable or "тармо" in t or "реконструк" in t):
        return "hv_cable"
    if any(k in t for k in ("паст кучланиш", "аввг", "past kuchlanish", "кабел ётқиз")) or (cable and "0,4" in t):
        return "lv_cable"
    if "хаво" in t or "ҳаво" in t or "хл-0,4" in t:
        if "янгила" in t or "реконструк" in t:
            return "air_new"
        return "air_capital" if "мукаммал" in t else "air_current"
    if "кл янгилаш" in t:
        return "hv_cable"
    if "трансформатор пункт" in t or "трагсформатор" in t or re.search(r"\bтп\b|тп[-№ ]?\d", t):
        return "tp_capital" if ("мукаммал" in t or "капитал" in t) else "tp_current"
    return "other"


def tps_in(text):
    found = []
    for rx in (TP_RE1, TP_RE2):
        for m in rx.finditer(text.replace("№", " № ")):
            n = m.group(1).lstrip("0") or "0"
            if n not in found:
                found.append(n)
    return found


@dataclass(eq=False)
class TPRec(TPMetrics):
    res: str
    number: str
    substation: str = ""
    feeder: str = ""
    owner: str = ""
    meter_no: str = ""
    ct_ratio: float = None
    meter_state: str = ""
    consumers_total: int = 0
    consumers_household: int = 0
    consumers_commercial: int = 0
    capacity_kva: int = 0
    daily_kwh: float = None
    kva_total: float = None
    kva_yesterday: float = None
    pf: float = None
    voltage_a: float = None
    voltage_b: float = None
    voltage_c: float = None
    current_a: float = None
    current_b: float = None
    current_c: float = None
    load_factor: float = None
    row: int = 0
    aux: bool = False
    # бирлаштиришдан кейин тўлдирилади
    mahalla_key: tuple = None
    in_program: bool = False
    in_obod: bool = False
    obod_district: str = ""
    obod_mahalla: str = ""
    obod_voltages: tuple = None

    @property
    def base_number(self):
        return base_number(self.number)

    @property
    def monthly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 30

    @property
    def yearly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 360

    @property
    def active(self):
        return self.capacity_kva > 0 and self.owner != "Virtual" and not self.aux


@dataclass
class Work:
    res: str
    mahalla: str
    title: str
    unit: str
    quantity: float
    cost: float
    kind: str
    tps: list
    row: int


@dataclass
class Merged:
    trload: list
    works: list
    mahallas: list                    # [(res, name)] дастур тартибида
    tps: list                         # сайтга кирадиган ТП лар
    obod_rows: list                   # тузатишлар жадвали учун
    program_summary: dict             # res -> {"budget": .., "rows": [...]}
    report_date: str = ""
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- манбаларни ўқиш
def read_trload(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    ws.reset_dimensions()
    date = ""
    recs = []
    for i, r in enumerate(ws.iter_rows(values_only=True), start=1):
        r = list(r) + [None] * (30 - len(r))
        if i == 3 and r[10]:
            date = str(r[10])
        if i < 6 or r[0] is None or not r[1]:
            continue
        cap = num(r[10]) or 0
        recs.append(TPRec(
            res=str(r[1]).strip(), number=str(r[4]).strip(), substation=clean_text(r[2]),
            feeder=clean_text(r[3]), owner=clean_text(r[5]), meter_no=clean_text(r[11]),
            ct_ratio=num(r[12]), meter_state=STATE_UZ.get(clean_text(r[27]), clean_text(r[27])),
            consumers_total=int(num(r[7]) or 0), consumers_household=int(num(r[8]) or 0),
            consumers_commercial=int(num(r[9]) or 0), capacity_kva=int(cap),
            daily_kwh=num(r[13]), kva_yesterday=num(r[14]), kva_total=num(r[15]), pf=num(r[16]),
            current_a=num(r[20]), current_b=num(r[21]), current_c=num(r[22]),
            # Тизим сарлавҳалари: 23-устун «L2», 24-устун «L1», 25-устун «L3»
            voltage_a=num(r[24]), voltage_b=num(r[23]), voltage_c=num(r[25]),
            load_factor=num(r[26]), row=i, aux=bool(AUX_RE.search(str(r[4]))),
        ))
    wb.close()
    return recs, date


def read_program(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    # 2-илова: туманлар бўйича умумий маълумот
    ws = wb["2 илова"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[2]
    cols = {}
    for j, h in enumerate(header):
        h = clean_text(h)
        if h in CYR_TO_RES:
            cols[j] = CYR_TO_RES[h]
    summary = {res: {"budget": 0.0, "rows": []} for res in RES}
    for j, res in cols.items():
        summary[res]["budget"] = num(rows[4][j]) or 0.0
    for r in rows[5:]:
        if r[0] is None or not r[1]:
            continue
        for j, res in cols.items():
            q = num(r[j])
            if q:
                summary[res]["rows"].append({"direction": clean_text(r[1]), "unit": clean_text(r[2]), "qty": q})

    # 2.1-илова: манзилли рўйхат
    ws = wb["2.1. илова"]
    works, order = [], []
    res = mahalla = None
    for i, r in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
        a, b, c, unit, qty, cost = (list(r) + [None] * 6)[:6]
        if c and "ЖАМИ" in str(c) and b is None:
            res = next((CYR_TO_RES[v] for k, v in PROGRAM_HEADERS.items() if k in str(c)), None)
            if res is None:
                raise ValueError(f"Туман аниқланмади: {c}")
            mahalla = None
            continue
        if b and str(b).strip().startswith("Жами"):
            continue
        if b:
            mahalla = clean_mahalla(b)
            if (res, mahalla) not in order:
                order.append((res, mahalla))
        if c is None or mahalla is None:
            continue
        title = clean_text(c).lstrip("•").strip()
        works.append(Work(res=res, mahalla=mahalla, title=title, unit=clean_text(unit), quantity=num(qty),
                          cost=num(cost) or 0.0, kind=categorize(title), tps=tps_in(title), row=i))
    return works, order, summary


def read_obod(path):
    df = pd.read_excel(path)
    df.columns = ["district", "mahalla", "tp", "ct", "ch", "cc", "cap", "dk", "mk", "yk", "va", "vb", "vc", "lf"]
    return df


# ---------------------------------------------------------------- бирлаштириш
def merge(data_dir):
    data_dir = Path(data_dir)
    trload, date = read_trload(find_file(data_dir, "trload"))
    works, order, summary = read_program(find_file(data_dir, "program"))
    obod = read_obod(find_file(data_dir, "obod"))
    notes = []

    by_key = {}
    by_base = {}
    for t in trload:
        by_key.setdefault(full_key(t.number), []).append(t)
        if t.capacity_kva > 0 and not t.aux:
            by_base.setdefault((t.res, base_number(t.number)), []).append(t)

    # 1) дастур маҳаллаларини ТП ларга боғлаш (биринчи тилга олинган маҳалла)
    selected = []
    for w in works:
        for n in w.tps:
            for t in by_base.get((w.res, n), []):
                if t.mahalla_key is None:
                    t.mahalla_key = (w.res, w.mahalla)
                    t.in_program = True
                    selected.append(t)

    # 2) Обод файлидаги ТП ларни тизим ҳисоботи билан солиштириш
    obod_rows = []
    for _, o in obod.iterrows():
        cands = by_key.get(full_key(o.tp), [])
        exact = [t for t in cands if t.consumers_total == int(o.ct) and t.capacity_kva == int(o.cap)
                 and t.daily_kwh is not None and abs(t.daily_kwh - float(o.dk)) < 0.01]
        if len(exact) != 1:
            notes.append(f"Обод файлидаги ТП-{o.tp} тизим ҳисоботидан бир маъноли топилмади ({len(exact)}).")
            continue
        t = exact[0]
        t.in_obod = True
        t.obod_district = clean_text(o.district)
        t.obod_mahalla = clean_mahalla(o.mahalla)
        t.obod_voltages = (float(o.va), float(o.vb), float(o.vc))
        if t not in selected:
            selected.append(t)
        obod_rows.append(t)

    return Merged(trload=trload, works=works, mahallas=order, tps=selected, obod_rows=obod_rows,
                  program_summary=summary, report_date=date, notes=notes)
