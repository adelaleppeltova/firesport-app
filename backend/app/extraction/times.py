"""Source time interpretation; never calculate an official final result."""

import re

INVALID = {
    "999",
    "999.990",
    "998",
    "NP",
    "DNS",
    "DNF",
    "DSQ",
    "-1",
    "999990",
    "0:00-",
    "-",
    "",
}


def parse_time(raw, warnings, context="", *, absent=False):
    if absent:
        return {"time": None, "status": "missing"}
    value = re.sub(r"\s+", " ", str(raw or "").strip()).upper().replace(",", ".")
    if re.search(r"(?:\s|^)N$", value) or value in INVALID:
        return {"time": None, "status": "invalid"}
    value = re.sub(r"\s+P$", "", value)
    trailing = value.endswith("-")
    if trailing:
        value = value[:-1]
        # The documented SS:hh- notation is only unambiguous with two digits.
        if re.fullmatch(r"\d{2}:\d{2}", value):
            value = value.replace(":", ".")
        elif ":" in value:
            warnings.append(f"{context}: ambiguous trailing-dash time: {raw!r}")
            return {"time": None, "status": "invalid"}
    if re.fullmatch(r"\d+:\d{2}\.\d{1,3}", value):
        minutes, seconds = value.split(":")
        if float(seconds) >= 60:
            warnings.append(f"{context}: invalid seconds: {raw!r}")
            return {"time": None, "status": "invalid"}
        number = int(minutes) * 60 + float(seconds)
    elif re.fullmatch(r"\d+(?:\.\d{1,3})?", value):
        number = float(value)
    else:
        warnings.append(f"{context}: unrecognized time: {raw!r}")
        return {"time": None, "status": "invalid"}
    if number in (998, 999, 999.99, 999990):
        return {"time": None, "status": "invalid"}
    return {"time": round(number, 3), "status": "invalid" if trailing else "valid"}


def final_time(raw, attempts, warnings, context="", *, placeholder=False, absent=False):
    result = parse_time(raw, warnings, context, absent=absent)
    if (
        placeholder
        and str(raw).strip() == "30:00.00"
        and all(t["status"] == "invalid" for t in attempts)
    ):
        return {"time": None, "status": "invalid"}
    if result["status"] == "invalid":
        result["time"] = None
    if result["status"] == "valid" and result["time"] not in [
        t["time"] for t in attempts if t["status"] == "valid"
    ]:
        warnings.append(
            f"{context}: official final time disagrees with published attempts; preserved"
        )
    return result
