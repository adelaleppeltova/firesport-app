import re


_DIACRITIC_GROUPS = {
    "a": "aáäàâãåą",
    "c": "cčćç",
    "d": "dďđ",
    "e": "eéěëèêę",
    "i": "iíïìî",
    "l": "lĺľł",
    "n": "nňńñ",
    "o": "oóöòôõø",
    "r": "rřŕ",
    "s": "sšśșş",
    "t": "tťțţ",
    "u": "uúůüùû",
    "y": "yýÿ",
    "z": "zžźż",
}


def build_diacritic_fuzzy_regex(value: str) -> str:
    """Vytvoří regex, který bere českou/slovenskou diakritiku jako ekvivalent."""
    parts: list[str] = []

    for char in value:
        group = _DIACRITIC_GROUPS.get(char.lower())
        if group:
            parts.append(f"[{group}]")
        else:
            parts.append(re.escape(char))

    return "".join(parts)
