"""Excel'dagi kirillcha nomlarni tozalash va o'zbek lotin yozuviga o'girish."""
import re

_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'",
    "ь": "", "ы": "i", "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q",
    "ғ": "g'", "ҳ": "h",
}
_VOWELS = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")

# Rasmiy yoki to'g'ri imlodagi nomlar (avtomatik o'girish yetarli bo'lmagan joylar)
OVERRIDES = {
    "Мирзоулуғбек": "Mirzo Ulug'bek",
    "Шайхонтохур": "Shayxontohur",
    "Янгихаёт": "Yangihayot",
    "А. Каххор": "A. Qahhor",
    "Ат Термизий": "At-Termiziy",
    "Конситутция": "Konstitutsiya",
    "Мехригие": "Mehrigiyo",
    "Мовароунахр": "Movarounnahr",
    "Мухандислар": "Muhandislar",
    "Олтинкул": "Oltinko'l",
    "Хумоюн": "Humoyun",
    "Ш.Рашидов": "Sh. Rashidov",
    "Шахрисабз": "Shahrisabz",
    "Ю. Раджабий": "Yu. Rajabiy",
    "Сохибқирон": "Sohibqiron",
    "Халқабод": "Xalqobod",
    "Янги сергели": "Yangi Sergeli",
    "Катта Ёлонгоч ота": "Katta Yolg'och ota",
    "Дилбулок": "Dilbuloq",
}


# Excel'dagi kirillcha nomlarning to'g'ri imlosi (sayt kirill yozuvida)
CYR_FIX = {
    "Мирзоулуғбек": "Мирзо Улуғбек",
    "Шайхонтохур": "Шайхонтоҳур",
    "Янгихаёт": "Янгиҳаёт",
    "А. Каххор": "А. Қаҳҳор",
    "Ат Термизий": "Ат-Термизий",
    "Конситутция": "Конституция",
    "Мехригие": "Меҳригиё",
    "Мовароунахр": "Мовароуннаҳр",
    "Мухандислар": "Муҳандислар",
    "Олтинкул": "Олтинкўл",
    "Хумоюн": "Ҳумоюн",
    "Ш.Рашидов": "Ш. Рашидов",
    "Шахрисабз": "Шаҳрисабз",
    "Ю. Раджабий": "Ю. Ражабий",
    "Сохибқирон": "Соҳибқирон",
    "Янги сергели": "Янги Сергели",
    "Катта Ёлонгоч ота": "Катта Ёлғоч ота",
    "Дилбулок": "Дилбулоқ",
}


def fix_cyr(name: str) -> str:
    name = clean(name)
    return CYR_FIX.get(name, name)


def clean(name: str) -> str:
    """Ortiqcha bo'shliq, qo'shtirnoq va nuqtalarni olib tashlaydi."""
    name = re.sub(r"[“”\"«»]", "", str(name))
    name = re.sub(r"\s+", " ", name).strip().lstrip(".").strip()
    return name


def to_latin(name: str) -> str:
    name = clean(name)
    if name in OVERRIDES:
        return OVERRIDES[name]
    out = []
    prev = ""
    for ch in name:
        low = ch.lower()
        if low == "е" and (not prev or not prev.isalpha() or prev in _VOWELS):
            lat = "ye"
        else:
            lat = _MAP.get(low, ch)
        if ch != low and lat:
            lat = lat[0].upper() + lat[1:]
        out.append(lat)
        prev = ch
    return "".join(out)
