"""ТП рўйхатидан умумий кўрсаткичларни ҳисоблаш.

Шаҳар кўрсаткичлари — туманлар йиғиндиси. Истеъмоли манфий/нол (ҳисоб хатоси) ёки
номаълум бўлган ТП лар истеъмол йиғиндисига қўшилмайди.
"""
from collections import defaultdict


def summarize(tps):
    tps = list(tps)
    n = len(tps)
    if not n:
        return {"tp_count": 0}
    valid = [t for t in tps if t.daily_kwh is not None and not t.has_anomaly]
    capacity = sum(t.capacity_kva for t in tps)
    actual = sum(t.actual_kva for t in tps)
    status = defaultdict(int)
    for t in tps:
        status[t.report.status] += 1
    consumers = sum(t.consumers_total for t in tps)
    household = sum(t.consumers_household for t in tps)
    daily = sum(t.daily_kwh for t in valid)
    valid_consumers = sum(t.consumers_total for t in valid)
    volts = [t.avg_voltage for t in tps if t.avg_voltage is not None]
    return {
        "tp_count": n,
        "consumers": consumers,
        "household": household,
        "commercial": sum(t.consumers_commercial for t in tps),
        "capacity_kva": capacity,
        "capacity_mva": capacity / 1000,
        "actual_kva": actual,
        "reserve_kva": capacity - actual,
        "load_pct": actual / capacity * 100 if capacity else 0,
        "daily_kwh": daily,
        "monthly_kwh": daily * 30,
        "yearly_kwh": daily * 360,
        "kwh_per_consumer": daily * 30 / valid_consumers if valid_consumers else 0,
        "valid_consumers": valid_consumers,
        "avg_voltage": sum(volts) / len(volts) if volts else None,
        "health": sum(t.report.score for t in tps) / n,
        "good": status["good"],
        "warn": status["warn"],
        "crit": status["crit"],
        "problems": status["warn"] + status["crit"],
        "anomalies": sum(1 for t in tps if t.has_anomaly),
        "household_pct": household / consumers * 100 if consumers else 0,
    }


def combine(parts):
    """Бир нечта summarize() натижасини жамлаш (масалан, туманлардан шаҳар)."""
    parts = [p for p in parts if p.get("tp_count")]
    if not parts:
        return {"tp_count": 0}
    keys = ["tp_count", "consumers", "household", "commercial", "capacity_kva", "actual_kva", "reserve_kva",
            "daily_kwh", "monthly_kwh", "yearly_kwh", "good", "warn", "crit", "problems", "anomalies",
            "valid_consumers"]
    out = {k: sum(p.get(k) or 0 for p in parts) for k in keys}
    n = out["tp_count"]
    out["capacity_mva"] = out["capacity_kva"] / 1000
    out["load_pct"] = out["actual_kva"] / out["capacity_kva"] * 100 if out["capacity_kva"] else 0
    out["kwh_per_consumer"] = out["monthly_kwh"] / out["valid_consumers"] if out["valid_consumers"] else 0
    out["health"] = sum(p["health"] * p["tp_count"] for p in parts) / n
    vs = [(p["avg_voltage"], p["tp_count"]) for p in parts if p.get("avg_voltage")]
    out["avg_voltage"] = sum(v * w for v, w in vs) / sum(w for _, w in vs) if vs else None
    out["household_pct"] = out["household"] / out["consumers"] * 100 if out["consumers"] else 0
    return out


def health_status(score):
    return "good" if score >= 80 else "warn" if score >= 65 else "crit"


def group_by(tps, key):
    groups = defaultdict(list)
    for t in tps:
        groups[key(t)].append(t)
    return groups
