"""Find every number in a generated summary and check it against the source facts.

A number is supported if some fact has that value, allowing for the rounding
the text itself shows ("$48.3k" stands for anything from $48,250 to $48,350).
Words count too: "doubled", "half of", "a third of", "twelve".

Known blind spot, measured in evals/checker_eval.py: a number that is real but
attached to the wrong thing ("revenue was 14" when 14 is the deal count)
passes, because the checker checks values, not which label they belong to.
"""
import re

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
MASKS = [
    r"\b\d{4}-\d{2}-\d{2}\b",                                  # ISO dates
    rf"\b{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*[-–]\s*(?:{MONTH}\s+)?\d{{1,2}}(?:st|nd|rd|th)?)?\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}",                  # 22 June
    r"\b(?:19|20)\d{2}\b",                                      # years
    r"\bQ[1-4]\b", r"\bweek\s+\d+\b", r"\bOPP-\d+\b",
    r"\b\d+(?:st|nd|rd|th)\b",                                  # ordinals
]
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
         "twenty": 20, "a dozen": 12, "dozen": 12}
RATIOS = {"doubled": 2, "double": 2, "tripled": 3, "triple": 3, "quadrupled": 4,
          "halved": 0.5, "half of": 0.5, "a third of": 1 / 3, "one third of": 1 / 3,
          "two thirds of": 2 / 3, "a quarter of": 0.25, "one quarter of": 0.25}

NUM = r"(\d[\d,]*(?:\.\d+)?)"
PATTERNS = [
    ("money", re.compile(rf"\$\s?{NUM}\s?(k|K|m|M|bn|thousand|million|billion)?\b")),
    ("percent", re.compile(rf"{NUM}\s?(%|percent\b|per cent\b|percentage points?\b|pts?\b)")),
    ("ratio", re.compile(r"(?i)\b(two thirds of|one third of|a third of|one quarter of|a quarter of|"
                         r"half of|halved|quadrupled|tripled|triple|doubled|double)\b(?!-)")),
    ("word", re.compile(r"(?i)\b(a dozen|dozen|two|three|four|five|six|seven|eight|nine|ten|eleven|"
                        r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b")),
    ("number", re.compile(rf"(?<![\w.$-]){NUM}(\s?(?:k|K|m|M)\b)?")),
]


def _blank(text, start, end):
    return text[:start] + " " * (end - start) + text[end:]


def extract(text: str):
    work = text
    for pat in MASKS:
        for m in re.finditer(pat, work, flags=re.I):
            work = _blank(work, m.start(), m.end())
    found = []
    for kind, pat in PATTERNS:
        for m in pat.finditer(work):
            raw = m.group(0)
            if kind in ("money", "percent", "number"):
                digits = m.group(1).replace(",", "")
                suffix = (m.group(2) or "").strip().lower() if kind != "percent" else ""
                scale = SCALE.get(suffix, 1)
                decimals = len(digits.split(".")[1]) if "." in digits else 0
                value = float(digits) * scale
                unit = 10 ** -decimals * scale
            elif kind == "word":
                value, unit = WORDS[m.group(1).lower()], 1
            else:
                value, unit = RATIOS[m.group(1).lower()], 0
            found.append({"text": raw.strip(), "start": m.start(), "end": m.start() + len(raw.rstrip()),
                          "kind": kind, "value": value, "unit": unit})
            work = _blank(work, m.start(), m.end())
    return sorted(found, key=lambda x: x["start"])


def _close(v, f, unit):
    tol = max(unit / 2 * 1.0001, abs(f) * 1e-9)
    return abs(abs(v) - abs(f)) <= tol + 1e-9


def verify(mention, facts):
    nums = [f for f in facts if isinstance(f["value"], (int, float))]
    v, unit, kind = mention["value"], mention["unit"], mention["kind"]
    if kind == "ratio":
        for f in nums:
            if f["unit"] == "ratio" and abs(f["value"] - v) <= 0.05 * v + 0.05:
                return f["id"]
            if f["unit"] == "pct" and (abs(f["value"] / 100 - v) <= 0.03
                                       or abs(1 + f["value"] / 100 - v) <= 0.05 * v):
                return f["id"]
        return None
    pool = {"money": ("usd",), "percent": ("pct",), "word": ("count",)}.get(kind)
    for f in nums:
        if (pool is None or f["unit"] in pool) and _close(v, f["value"], unit):
            return f["id"]
    # A number in a fact's own label is a definition the data gives
    # ("engaging for more than 60 days"), so repeating it is supported.
    if kind in ("number", "word"):
        for f in facts:
            if any(float(x) == v for x in re.findall(r"\d+(?:\.\d+)?", f["label"])):
                return f["id"]
    return None


def check(text, facts):
    mentions = extract(text)
    for m in mentions:
        m["fact"] = verify(m, facts)
        m["ok"] = m["fact"] is not None
    return {"mentions": mentions, "stated": len(mentions),
            "unsupported": sum(1 for m in mentions if not m["ok"])}
