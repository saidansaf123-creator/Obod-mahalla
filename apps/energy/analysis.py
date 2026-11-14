"""Трансформатор пунктлари (ТП) ҳолатини таҳлил қилиш.

Меъёрлар ГОСТ 32144-2013 (230 В тармоқ) асосида:
нормал оғиш ±5% (218,5–241,5 В), рухсат этилган чегара ±10% (207–253 В).
Қувват коэффициенти (cos φ) меъёри — 0,92 дан кам эмас.
"""
from dataclasses import dataclass, field
from functools import cached_property

NOMINAL_V = 230.0
NORM_LOW, NORM_HIGH = 218.5, 241.5
LIMIT_LOW, LIMIT_HIGH = 207.0, 253.0

IMB_WARN, IMB_CRIT = 3.0, 6.0          # фазалар орасидаги фарқ, номиналга нисбатан %
LOAD_WARN, LOAD_CRIT = 0.50, 0.60      # юкланиш: 0–50% яшил, 50–60% сариқ, 60% дан юқори қизил
LOAD_LOW = 0.22                        # кам юкланган трансформатор
DENSITY_WARN, DENSITY_CRIT = 0.75, 1.0  # 1 кВА қувватга тўғри келадиган истеъмолчи
PF_WARN, PF_CRIT = 0.92, 0.85          # қувват коэффициенти
PEAK_RATIO = 1.8                       # чўққи юклама / ўртача юклама

STATUS_LABELS = {"good": "Яшил", "warn": "Сариқ", "crit": "Қизил"}


def load_status(lf):
    """ТП тоифаси юкланиш бўйича."""
    lf = lf or 0
    return "crit" if lf >= LOAD_CRIT else "warn" if lf >= LOAD_WARN else "good"


def score_status(score):
    """Саломатлик индекси бўйича умумий техник ҳолат."""
    return "good" if score >= 80 else "warn" if score >= 60 else "crit"


@dataclass
class Issue:
    code: str
    level: str  # info | warn | crit
    title: str
    text: str
    advice: str
    icon: str = "circle-alert"


@dataclass
class Report:
    score: int
    status: str
    imbalance_pct: float
    phases: dict
    issues: list = field(default_factory=list)
    health: str = "good"  # индекс бўйича ҳолат (status — юкланиш бўйича тоифа)

    @property
    def status_label(self):
        return STATUS_LABELS[self.status]

    def has(self, code):
        return any(i.code == code for i in self.issues)


def fmt(v, d=1):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def phase_state(v):
    if v is None:
        return "none"
    if v < LIMIT_LOW or v > LIMIT_HIGH:
        return "crit"
    if v < NORM_LOW or v > NORM_HIGH:
        return "warn"
    return "ok"


class TPMetrics:
    """Модель ва импорт объектлари учун умумий ҳисобланадиган кўрсаткичлар."""

    @cached_property
    def report(self):
        return analyze(self)

    @property
    def load_pct(self):
        return (self.load_factor or 0) * 100

    @property
    def actual_kva(self):
        return (self.load_factor or 0) * self.capacity_kva

    @property
    def reserve_kva(self):
        return self.capacity_kva - self.actual_kva

    @property
    def peak_pct(self):
        return min((self.load_factor or 0) * PEAK_RATIO, 1.3) * 100

    @property
    def voltages(self):
        return [v for v in (self.voltage_a, self.voltage_b, self.voltage_c) if v is not None]

    @property
    def avg_voltage(self):
        vs = self.voltages
        return sum(vs) / len(vs) if vs else None

    @property
    def has_anomaly(self):
        return self.daily_kwh is not None and self.daily_kwh <= 0

    @property
    def kwh_per_consumer_month(self):
        if self.has_anomaly or not self.consumers_total or self.monthly_kwh is None:
            return None
        return self.monthly_kwh / self.consumers_total


def analyze(tp) -> Report:
    phases = {"L1": tp.voltage_a, "L2": tp.voltage_b, "L3": tp.voltage_c}
    known = {p: v for p, v in phases.items() if v is not None}
    states = {p: phase_state(v) for p, v in phases.items()}
    issues, score = [], 100

    low = {p: v for p, v in known.items() if v < NORM_LOW}
    if low:
        crit = any(v < LIMIT_LOW for v in low.values())
        score -= sum(15 if v < LIMIT_LOW else 7 for v in low.values())
        issues.append(Issue(
            "low_voltage", "crit" if crit else "warn", "Паст кучланиш",
            f"{', '.join(low)} фазада кучланиш {fmt(min(low.values()))} В гача тушган "
            f"(меъёр {fmt(NORM_LOW)}–{fmt(NORM_HIGH)} В).",
            "0,4 кВ тармоқни янгилаш (СИП ёки кабель), контакт уланишларини текшириш.",
            "trending-down",
        ))

    high = {p: v for p, v in known.items() if v > NORM_HIGH}
    if high:
        crit = any(v > LIMIT_HIGH for v in high.values())
        score -= sum(14 if v > LIMIT_HIGH else 6 for v in high.values())
        issues.append(Issue(
            "high_voltage", "crit" if crit else "warn", "Юқори кучланиш",
            f"{', '.join(high)} фазада кучланиш {fmt(max(high.values()))} В гача кўтарилган — "
            "маиший техника тез ишдан чиқиши мумкин.",
            "Трансформаторнинг ПБВ улагичини пастроқ поғонага ўтказиш.",
            "trending-up",
        ))

    imb = 0.0
    if len(known) >= 2:
        spread = max(known.values()) - min(known.values())
        imb = spread / NOMINAL_V * 100
        if imb >= IMB_WARN:
            crit = imb >= IMB_CRIT
            score -= 16 if crit else 8
            issues.append(Issue(
                "imbalance", "crit" if crit else "warn", "Фазалар носимметрияси",
                f"Фазалар орасидаги фарқ {fmt(spread)} В ({fmt(imb)}%). Меъёр — {fmt(IMB_WARN, 0)}% гача.",
                "Бир фазали истеъмолчиларни фазалар бўйича қайта тақсимлаш.",
                "scale",
            ))

    lf = tp.load_factor
    if lf is not None and lf >= LOAD_WARN:
        crit = lf >= LOAD_CRIT
        score -= 20 if crit else 10
        issues.append(Issue(
            "overload", "crit" if crit else "warn", "Юқори юкланиш",
            f"Ўртача юкланиш {fmt(lf * 100, 0)}% — чўққи соатларда "
            f"~{fmt(min(lf * PEAK_RATIO, 1.3) * 100, 0)}% гача етиши мумкин.",
            "Янги ТП қуриб, юкламанинг бир қисмини ўтказиш ёки қувватни ошириш.",
            "gauge",
        ))
    elif lf is not None and lf < LOAD_LOW and tp.capacity_kva >= 400:
        score -= 3
        issues.append(Issue(
            "underload", "info", "Кам юкланган",
            f"Юкланиш атиги {fmt(lf * 100, 0)}% — салт ишлаш йўқотишлари улуши юқори.",
            "Келажакдаги янги уланишларни шу ТП га йўналтириш.",
            "battery-low",
        ))

    density = tp.consumers_total / tp.capacity_kva if tp.capacity_kva else 0
    if density >= DENSITY_WARN:
        crit = density >= DENSITY_CRIT
        score -= 15 if crit else 8
        issues.append(Issue(
            "density", "crit" if crit else "warn", "Истеъмолчилар зичлиги юқори",
            f"Ҳар 1 кВА қувватга {fmt(density, 2)} истеъмолчи тўғри келади "
            f"({tp.consumers_total} та истеъмолчи / {tp.capacity_kva} кВА).",
            "Қувват захирасини яратиш: янги ТП ёки қувватни ошириш.",
            "users",
        ))

    pf = getattr(tp, "pf", None)
    if pf is not None and 0 < pf < PF_WARN:
        crit = pf < PF_CRIT
        score -= 10 if crit else 5
        issues.append(Issue(
            "low_pf", "crit" if crit else "warn", "Паст қувват коэффициенти",
            f"cos φ = {fmt(pf, 3)} (меъёр {fmt(PF_WARN, 2)} дан кам эмас) — реактив қувват ортиқча.",
            "Реактив қувватни компенсациялаш (конденсатор батареяси ўрнатиш).",
            "activity",
        ))

    if tp.has_anomaly:
        score -= 15
        issues.append(Issue(
            "anomaly", "crit", "Ҳисоб маълумотида хато",
            f"Кунлик истеъмол {fmt(tp.daily_kwh)} кВт·соат қайд этилган — "
            "ҳисоблагич носозлиги ёки ҳисобсиз уланиш эҳтимоли.",
            "Бош ҳисоблагични алмаштириш ва АСКУЭ тизимига улаш.",
            "cpu",
        ))

    score = max(0, min(100, score))
    order = {"crit": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda i: order[i.level])
    return Report(score, load_status(lf), round(imb, 2), states, issues, score_status(score))
