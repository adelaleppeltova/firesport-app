import re


def assign_reasons(raw, attempts, warnings, context):
    text = (raw or "").strip()
    if not text:
        return 0
    matches = list(
        re.finditer(r"(?:^|[,;]\s*)([1-4](?:\s*,\s*[1-4])*)\s*[-–—.]\s*", text)
    )
    if not matches or text[: matches[0].start()].strip(" ,;"):
        warnings.append(f"{context}: unassigned penalty: {text!r}")
        return 0
    count = 0
    for i, match in enumerate(matches):
        reason = text[
            match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)
        ].strip()
        for number in map(int, match[1].split(",")):
            if number > 2:
                warnings.append(
                    f"{context}: ignored penalty for try {number}: {reason} (source: {text!r})"
                )
                continue
            attempt = attempts[number - 1]
            if not reason or "invalid_reason" in attempt:
                raise ValueError(
                    f"{context}: empty or duplicate numbered penalty: {text!r}"
                )
            attempt["invalid_reason"] = reason
            count += 1
            if attempt["status"] != "invalid":
                warnings.append(
                    f"{context}: penalty on {attempt['status']} try {number}: {reason}"
                )
    return count
