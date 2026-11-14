"""Кирилча номларни ўзбек лотин ёзувига ўгириш (қидирув ва slug учун)."""
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


def clean(name: str) -> str:
    """Ортиқча бўшлиқ ва қўштирноқларни олиб ташлайди."""
    name = re.sub(r"[“”\"«»]", "", str(name))
    return re.sub(r"\s+", " ", name).strip().lstrip(".").strip()


def to_latin(name: str) -> str:
    name = clean(name)
    out, prev = [], ""
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
