"""Маҳалла мақсади — 2027 йил «Обод маҳалла» дастуридаги (2.1-илова) ҳақиқий ишлар асосида.

Сарлавҳа, хулоса ва кутилаётган натижалар ишлар таркибидан тузилади; ТП таҳлили устуворликка таъсир қилади.
"""
from collections import OrderedDict

from .analysis import fmt
from .merge import CATEGORIES

COUNT_UNITS = ("дона", "та", "dona")


def _amount(work):
    """Ишнинг табиий миқдори: дона ёки км."""
    kind = CATEGORIES[work["kind"]][2]
    q = work.get("quantity")
    unit = (work.get("unit") or "").lower()
    if kind == "count":
        return q if (q and any(u in unit for u in COUNT_UNITS)) else 1
    return q if (q and "км" in unit) else 0


def _n(amount):
    """3 -> "3", 2.5 -> "2,5", 1.25 -> "1,25"."""
    if not amount:
        return ""
    if float(amount).is_integer():
        return fmt(amount, 0)
    return fmt(amount, 2).rstrip("0").rstrip(",")


def _phrase(kind, amount):
    n = _n(amount)
    return {
        "tp_capital": f"{n} та ТП ни мукаммал таъмирлаш",
        "tp_current": f"{n} та ТП ни жорий таъмирлаш",
        "upgrade": f"{n} та трансформатор қувватини ошириш",
        "new_gktp": f"{n} та янги ГКТП ўрнатиш",
        "lv_cable": f"{n} км паст кучланишли кабелни янгилаш" if amount else "паст кучланишли кабелни янгилаш",
        "hv_cable": f"{n} км юқори кучланишли кабелни янгилаш" if amount else "юқори кучланишли кабелни янгилаш",
        "air_capital": f"{n} км ҳаво тармоғини мукаммал таъмирлаш",
        "air_current": f"{n} км ҳаво тармоғини жорий таъмирлаш",
        "air_new": f"{n} км ҳаво тармоғини янгилаш",
        "grsh": f"{n} та ГРШ-0,4 кВ ни модернизация қилиш",
        "other": "бошқа ишлар",
    }[kind]


def _effect(kind, amount):
    n = _n(amount)
    return {
        "tp_capital": f"{n} та трансформатор пункти мукаммал таъмирланади",
        "tp_current": f"{n} та трансформатор пункти жорий таъмирдан чиқарилади",
        "upgrade": f"{n} та трансформатор қуввати оширилади — қувват захираси ортади",
        "new_gktp": f"{n} та янги ГКТП ўрнатилади — янги уланишлар учун имконият яратилади",
        "lv_cable": f"{n} км паст кучланишли кабель янгиланади — хонадонларда кучланиш барқарорлашади",
        "hv_cable": f"{n} км юқори кучланишли кабель янгиланади — авария узилишлари камаяди",
        "air_capital": f"{n} км ҳаво тармоғи мукаммал таъмирланади",
        "air_current": f"{n} км ҳаво тармоғи жорий таъмирланади",
        "air_new": f"{n} км ҳаво тармоғи янгиланади",
        "grsh": f"{n} та ГРШ модернизация қилинади",
        "other": "Бошқа ишлар бажарилади",
    }[kind]


def generate(mahalla_name, works, tps):
    """works: [{"kind", "title", "quantity", "unit", "cost_mln", "tps"}], tps: боғланган ТП лар."""
    by_kind = OrderedDict()
    for w in works:
        k = by_kind.setdefault(w["kind"], {"cost": 0.0, "amount": 0.0, "count": 0})
        k["cost"] += w["cost_mln"]
        k["amount"] += _amount(w)
        k["count"] += 1
    ranked = sorted(by_kind.items(), key=lambda kv: -kv[1]["cost"])
    budget = round(sum(w["cost_mln"] for w in works), 2)

    parts = [_phrase(k, v["amount"]) for k, v in ranked[:2]]
    title = " ва ".join(parts)
    title = title[:1].upper() + title[1:]

    reports = [t.report for t in tps]
    consumers = sum(t.consumers_total for t in tps)
    crit = sum(1 for r in reports if r.health == "crit")
    warn = sum(1 for r in reports if r.health == "warn")
    if crit or budget >= 1000:
        priority = "high"
    elif warn or budget >= 300:
        priority = "medium"
    else:
        priority = "low"

    summary = (f"{mahalla_name} маҳалласида 2027 йил «Обод маҳалла» дастури доирасида {len(works)} та иш "
               f"режалаштирилган, умумий қиймати {fmt(budget, 1)} млн сўм. ")
    if tps:
        summary += f"Дастурда {len(tps)} та трансформатор тилга олинган, улар орқали {consumers} та истеъмолчи таъминланади"
        summary += (f"; таҳлилда {crit} та жиддий ва {warn} та ўртача муаммоли ТП аниқланди." if (crit or warn)
                    else "; уларнинг техник ҳолати меъёрда.")
    else:
        summary += "Ишлар асосан кабель тармоқларига тегишли, ТП рақамлари кўрсатилмаган."

    effects = [_effect(k, v["amount"]) for k, v in ranked]
    if consumers:
        effects.append(f"{consumers} та истеъмолчининг электр таъминоти сифати яхшиланади")

    return {
        "title": title, "summary": summary, "priority": priority, "status": "planned", "year": 2027,
        "budget_mln": budget, "beneficiaries": consumers, "effects": effects,
    }
