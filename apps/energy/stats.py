"""Йиғма кўрсаткичлар: режа/амал (ишлар бўйича) ва ТП секциялари таҳлили."""
from collections import defaultdict

PLAN_KEYS = ["lv_km", "hv_km", "tr_upgrade", "new_gktp", "grsh", "cost"]

FACT_MAP = {"lv_km": "fact_lv_km", "hv_km": "fact_hv_km", "tr_upgrade": "fact_tr_upgrade",
            "new_gktp": "fact_new_gktp", "grsh": "fact_grsh", "cost": "fact_cost"}


def plan_totals(works):
    p = {k: round(sum((getattr(w, k) or 0) for w in works), 3) for k in PLAN_KEYS}
    p["km"] = round(p["lv_km"] + p["hv_km"], 3)
    p["tr"] = p["tr_upgrade"] + p["new_gktp"]
    p["works"] = len(works)
    p["no_cost"] = sum(1 for w in works if w.cost is None)
    return p


def fact_totals(works):
    f = {k: round(sum((getattr(w, FACT_MAP[k]) or 0) for w in works), 3) for k in PLAN_KEYS}
    f["km"] = round(f["lv_km"] + f["hv_km"], 3)
    f["tr"] = f["tr_upgrade"] + f["new_gktp"]
    f["done"] = sum(1 for w in works if _done(w))
    return f


def _done(w):
    """Иш бажарилган: режадаги ҳар бир ҳажм амалда тўлиқ қопланган."""
    pairs = [(getattr(w, k) or 0, getattr(w, FACT_MAP[k]) or 0) for k in PLAN_KEYS if k != "cost"]
    planned = [(p, f) for p, f in pairs if p > 0]
    return bool(planned) and all(f >= p for p, f in planned)


def summarize(sections):
    """ТП секциялари бўйича (маълумоти бор секциялар)."""
    secs = [s for s in sections if s.has_data]
    n = len(secs)
    out = {"count": len(list(sections)), "with_data": n}
    if not n:
        return out
    valid = [s for s in secs if s.daily_kwh is not None and not s.has_anomaly]
    capacity = sum(s.capacity_kva for s in secs)
    actual = sum((s.kva_total or 0) for s in secs)
    status = defaultdict(int)
    for s in secs:
        status[s.report.status] += 1
    consumers = sum(s.consumers_total for s in secs)
    household = sum(s.consumers_household for s in secs)
    daily = sum(s.daily_kwh for s in valid)
    valid_consumers = sum(s.consumers_total for s in valid)
    volts = [s.avg_voltage for s in secs if s.avg_voltage is not None]
    pfs = [s.pf for s in secs if s.pf]
    out.update({
        "consumers": consumers,
        "household": household,
        "commercial": sum(s.consumers_commercial for s in secs),
        "household_pct": household / consumers * 100 if consumers else 0,
        "capacity_kva": capacity,
        "actual_kva": actual,
        "reserve_kva": capacity - actual,
        "load_pct": actual / capacity * 100 if capacity else 0,
        "daily_kwh": daily,
        "monthly_kwh": daily * 30,
        "yearly_kwh": daily * 365,
        "kwh_per_consumer": daily * 30 / valid_consumers if valid_consumers else 0,
        "avg_voltage": sum(volts) / len(volts) if volts else None,
        "avg_pf": sum(pfs) / len(pfs) if pfs else None,
        "health": sum(s.report.score for s in secs) / n,
        "good": status["good"], "warn": status["warn"], "crit": status["crit"],
        "problems": status["warn"] + status["crit"],
        "anomalies": sum(1 for s in secs if s.has_anomaly),
        "low_pf": sum(1 for s in secs if s.pf is not None and 0 < s.pf < 0.92),
        "voltage_issues": sum(1 for s in secs if s.report.has("low_voltage") or s.report.has("high_voltage")),
        "imbalance": sum(1 for s in secs if s.report.has("imbalance")),
    })
    return out


def health_status(score):
    return "good" if score >= 80 else "warn" if score >= 65 else "crit"


def group_by(items, key):
    groups = defaultdict(list)
    for t in items:
        groups[key(t)].append(t)
    return groups
