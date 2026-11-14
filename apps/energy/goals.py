"""Маҳалла мақсади — манзилли дастурдаги ишлар ва ТП маълумотлари асосида тузилади."""
from .analysis import fmt


def _n(amount):
    """3 -> "3", 2.5 -> "2,5", 1.25 -> "1,25"."""
    if float(amount).is_integer():
        return fmt(amount, 0)
    return fmt(amount, 2).rstrip("0").rstrip(",")


PHRASE = {
    "new_gktp": "{n} та янги ГКТП ўрнатиш",
    "tr_upgrade": "{n} та трансформатор қувватини ошириш",
    "hv_cable": "{n} км юқори кучланишли кабелни янгилаш",
    "lv_cable": "{n} км паст кучланишли кабелни янгилаш",
    "grsh": "{n} та ГРШ-0,4 кВ ни модернизация қилиш",
}
EFFECT = {
    "new_gktp": "{n} та янги ГКТП ўрнатилади — янги уланишлар учун қувват захираси пайдо бўлади",
    "tr_upgrade": "{n} та трансформатор катта қувватлисига алмаштирилади — ортиқча юкланиш камаяди",
    "hv_cable": "{n} км юқори кучланишли кабель янгиланади — авария узилишлари камаяди",
    "lv_cable": "{n} км паст кучланишли кабель янгиланади — хонадонларда кучланиш барқарорлашади",
    "grsh": "{n} та ГРШ модернизация қилинади — кўп қаватли уйлар таъминоти ишончли бўлади",
}
FIELD = {"new_gktp": "new_gktp", "tr_upgrade": "tr_upgrade", "hv_cable": "hv_km", "lv_cable": "lv_km", "grsh": "grsh"}


def generate(mahalla_name, works, sections):
    amounts = {k: sum(getattr(w, f) or 0 for w in works) for k, f in FIELD.items()}
    costs = {k: sum((w.cost or 0) for w in works if w.category == k) for k in FIELD}
    ranked = [k for k in sorted(FIELD, key=lambda k: -costs[k]) if amounts[k] > 0]
    budget = round(sum((w.cost or 0) for w in works), 2)

    title = " ва ".join(PHRASE[k].format(n=_n(amounts[k])) for k in ranked[:2]) or "Электр тармоқларини янгилаш"
    title = title[:1].upper() + title[1:]

    consumers = sum(s.consumers_total for s in sections)
    reports = [s.report for s in sections if s.has_data]
    crit = sum(1 for r in reports if r.health == "crit")
    loaded = sum(1 for r in reports if r.status != "good")
    if budget >= 3000 or crit:
        priority = "high"
    elif budget >= 1000 or loaded:
        priority = "medium"
    else:
        priority = "low"

    summary = (f"{mahalla_name} маҳалласида 2027 йил «Обод маҳалла» дастури доирасида {len(works)} та иш "
               f"режалаштирилган, зарур маблағ {fmt(budget, 1)} млн сўм.")
    if sections:
        summary += (f" Ишларга {len(sections)} та ТП секцияси бириктирилган, улардан {fmt(consumers, 0)} та "
                    f"истеъмолчи таъминланади")
        summary += f"; таҳлилда {crit} та жиддий муаммоли секция аниқланди." if crit else "."
    no_cost = sum(1 for w in works if w.cost is None)
    if no_cost:
        summary += f" {no_cost} та иш нархи файлда кўрсатилмаган."

    effects = [EFFECT[k].format(n=_n(amounts[k])) for k in ranked]
    if consumers:
        effects.append(f"{fmt(consumers, 0)} та истеъмолчининг электр таъминоти сифати яхшиланади")
    return {"title": title, "summary": summary, "priority": priority, "budget_mln": budget,
            "beneficiaries": consumers, "effects": effects}
