"""Organizer evidence scoped to exact race identifiers and dates."""
import re
from datetime import date
from urllib.parse import urlsplit

KSH = "https://kshusti.hasicovo.cz/file/edee/ms-ksh/ksh-usteckeho-kraje/"
STIMAX_2024 = KSH + "2024/03/stimax-cup-2024-propozice.pdf"
STIMAX_2025 = KSH + "2025/02/stimax-cup-2025-propozice.pdf"
STIMAX_2023_DECIN = KSH + "2024/03/clanek-stimax-cup-2023-3.-kolo-decin-2.-9.pdf"
STIMAX_2023_CHOMUTOV = (
    "https://mladez.dh.cz/images/Dokumenty/mladez/souteze/2023/"
    "2023_-_clanek_STIMAX_CUP_2023_-_4_kolo_Chomutov_-_30_9__celkove_vysledky.pdf"
)
YOUNGER_STIMAX = {
    ("226", "2023-09-02"): STIMAX_2023_DECIN,
    ("367", "2024-05-05"): STIMAX_2024,
    ("368", "2024-05-11"): STIMAX_2024,
    ("369", "2024-08-31"): STIMAX_2024,
    ("370", "2024-09-28"): STIMAX_2024,
    ("656", "2025-08-30"): STIMAX_2025,
    ("658", "2025-09-27"): STIMAX_2025,
}
OLDER_GENERAL = {
    ("224", "2023-04-22"): KSH + "2024/03/2023-1.-kolo-clanek-stimax-cup-2023-usti-nad-labem-sobota-22.-4.-2023.pdf",
    ("225", "2023-05-13"): KSH + "2024/03/2023-2.-kolo-clanek-stimax-cup-2023-mezibori-13.-5.-2023.pdf",
    ("248", "2023-05-27"): "https://pozarnisport.hasicovo.cz/races/248",
}
RACE_HOSTS = {"pozarnisporty.cz", "www.pozarnisporty.cz", "pozarnisport.hasicovo.cz"}
PRAGUE_MEMORIAL = "https://www.hasicovo.cz/cs/zpravy/nejvetsi-sportovni-udalost-memorial-marty-habadove-zna-sve-viteze"
BOROVANY_STANDINGS = "https://www.sdhborovany.cz/wp-content/uploads/2024/05/2024_Boro60_vysledky.pdf"
PASEKY_STANDINGS = (
    "https://oshpisek.hasicovo.cz/file/edee/ms-osh/osh-pisek/2025/08/celkove-vysledky-ps-2025-20250813-082557.pdf"
)
POLABI_RULES = "https://sdhpiskovalhota.cz/2026/Polabske-sedesatkovani-propozice.pdf"

YOUTH_STANDINGS = {
    ("161", "2022-11-06"): (PRAGUE_MEMORIAL, {"6 11": "Mladší"}),
    ("162", "2022-11-05"): (PRAGUE_MEMORIAL, {"11 15": "Starší"}),
    ("335", "2024-05-08"): (BOROVANY_STANDINGS, {"7 11": "Mladší", "12 15": "Starší"}),
    ("771", "2025-08-09"): (PASEKY_STANDINGS, {"3 5": "Přípravka", "6 11": "Mladší", "12 15": "Starší"}),
}
POLABI_AGE_GROUPS = {
    ("mladsi", "i"): ("Mladší", "7–8"),
    ("mladsi", "ii"): ("Mladší", "9–11"),
    ("starsi", "i"): ("Starší", "12–13"),
    ("starsi", "ii"): ("Starší", "14–15"),
}
YOUTH_GENDER_LABEL = {"divky": "dívky", "chlapci": "chlapci"}


def event_identity(competition: dict) -> tuple:
    when = competition.get("date")
    when = when.strftime("%Y-%m-%d") if isinstance(when, date) else when
    return when, competition.get("name"), competition.get("place")


MCR_TEAM_MEMBER_LISTS = {
    ("2019-07-05", "MČR dorostu v PS – Svitavy", "Svitavy"): "665-vysledky-mcr-druzstev-dorostu-sh-cms-v-ps-svitavy-2019",
    ("2021-07-03", "MČR dorostu v PS", "Zábřeh"): "897-vysledky-mcr-druzstev-dorostu-sh-cms-v-ps-2021",
    ("2022-07-01", "MČR dorostu v PS", "Ústí nad Labem"): "1052-vysledky-druzstva-usti-2022",
    ("2023-07-01", "MČR dorostu SH ČMS v PS", "Domažlice"): "1183-vysledky-druzstva-domazlice-2023",
    ("2024-07-01", "MČR dorostu SH ČMS v PS", "Písek"): "1323-vysledky-druzstva-pisek-2024",
    ("2025-06-28", "MČR dorostu SH ČMS v PS", "Kolín"): "1482-vysledky-druzstva-kolin-2025",
}
MCR_SOURCE_ROOT = "https://mladez.dh.cz/index.php/sportovni-cinnost/mcr-plamen-a-dorostu/"


def team_member_source(key: str, discipline: str, competition: dict) -> str | None:
    if discipline == "100m" and key in {"dorostenci", "dorostenky"}:
        if source := MCR_TEAM_MEMBER_LISTS.get(event_identity(competition)):
            return MCR_SOURCE_ROOT + source
    return None


def published_adult_group(key: str, event: tuple) -> tuple[str, str] | None:
    if key not in {"muzi", "zeny"}:
        return None
    when, name, place = event
    female = key == "zeny"
    label = "Ženy" if female else "Muži"
    if name == "Bludovská stovka" and place == "Bludov" and when in {"2018-07-28", "2019-07-27", "2022-07-30"}:
        stem = ("zeny" if female else "muzi") if when == "2018-07-28" else (
            "zeny_starsi_dorostenky" if female else "muzi_starsi_dorostenci"
        )
        return f"{label} 17–100", f"https://stovky.cz/bludov/{when[:4]}/{stem}.pdf"
    if event == ("2020-06-27", "O pohár HVP, a.s.", "Třebíč"):
        stem = "zeny_starsi_dorost" if female else "muzi_starsi_dorost"
        return f"{label} 17–100", f"https://stovky.cz/trebic/2020/{stem}.pdf"
    if event == ("2023-08-12", "Otevřené MČR v běhu na 100m s překážkami", "Praha - Hostivař"):
        return f"{label} 15–100", "https://pozarnisporty.cz/races/271"
    return None


def organizer_label(key: str, discipline: str, competition: dict) -> tuple[str, str] | None:
    """Return a verified interpretation plus a source URL. Source captions remain intact."""
    event = event_identity(competition)
    if discipline == "100m" and not competition.get("source_url"):
        return published_adult_group(key, event)
    url = urlsplit(competition.get("source_url") or "")
    if url.scheme != "https" or url.netloc not in RACE_HOSTS:
        return None
    parts = url.path.strip("/").split("/")
    if len(parts) != 2 or parts[0] != "races":
        return None
    race = parts[1], event[0]
    younger = {
        "mladsi divky a": "Mladší dívky 6–8 let",
        "mladsi zaci a divky": "Mladší dívky 6–8 let",
        "mladsi chlapci a": "Mladší chlapci 6–8 let",
        "mladsi zaci a chlapci": "Mladší chlapci 6–8 let",
        "mladsi divky b": "Mladší dívky 9–11 let",
        "mladsi zaci b divky": "Mladší dívky 9–11 let",
        "mladsi chlapci b": "Mladší chlapci 9–11 let",
        "mladsi zaci b chlapci": "Mladší chlapci 9–11 let",
    }
    older = {"divky vek 11 15": "Starší dívky", "chlapci vek 11 15": "Starší chlapci"}
    if discipline == "60m":
        general_group = re.fullmatch(r"(divky|chlapci) vek (\d+ \d+)", key)
        if race in YOUTH_STANDINGS and general_group:
            source, groups = YOUTH_STANDINGS[race]
            gender, ages = general_group.groups()
            if division := groups.get(ages):
                return f"{division} {YOUTH_GENDER_LABEL[gender]}", source
        if race == ("1180", "2026-09-20"):
            group = re.fullmatch(r"(mladsi|starsi) (divky|chlapci) (i|ii)", key)
            if group:
                division, gender, number = group.groups()
                label, ages = POLABI_AGE_GROUPS[division, number]
                return f"{label} {YOUTH_GENDER_LABEL[gender]} {ages} let", POLABI_RULES
        if race in YOUNGER_STIMAX and key in younger:
            return younger[key], YOUNGER_STIMAX[race]
        if race in OLDER_GENERAL and key in older:
            return older[key], OLDER_GENERAL[race]
    if discipline == "100m":
        if race == ("196", "2023-07-30"):
            labels = {"mladsi dorost": "Mladší dorostenci", "stredni dorost": "Střední dorostenci"}
            if key in labels:
                return labels[key], "https://pozarnisport.hasicovo.cz/races/196"
        if race == ("227", "2023-09-30"):
            labels = {"dorost divky zeny nad 17 let": "Dorost dívky + ženy 17–100",
                      "dorost chlapci muzi nad 17 let": "Dorost chlapci + muži 17–100"}
            if key in labels:
                return labels[key], STIMAX_2023_CHOMUTOV
    return None
