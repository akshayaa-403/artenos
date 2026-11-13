"""Gemini over plain HTTPS, standard library only.

The key goes in the `x-goog-api-key` header, never in the URL, so it cannot
leak through a logged URL or an error message.

Evals pass cache=True: identical prompts are answered from .cache/llm/, so
re-running a report costs nothing and the numbers stay fixed.

    python -m core.llm --models    # list the models this key can use
"""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

from core import config

BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMError(Exception):
    pass


@dataclass
class Reply:
    text: str
    in_tokens: int
    out_tokens: int
    latency_ms: float
    cost_usd: float
    cached: bool = False


def _request(url, body=None, timeout=60):
    if not config.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set (see .env.example)")
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY},
        method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def generate(prompt: str, *, json_mode=False, temperature=0.0, max_tokens=1024,
             model=None, cache=False, retries=4) -> Reply:
    model = model or config.GEMINI_MODEL
    gen = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    if config.THINKING_LEVEL:
        gen["thinkingConfig"] = {"thinkingLevel": config.THINKING_LEVEL}
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}

    key = hashlib.sha256(json.dumps([model, body], sort_keys=True).encode()).hexdigest()
    cache_file = config.CACHE_DIR / f"{key}.json"
    if cache and cache_file.exists():
        return Reply(**{**json.loads(cache_file.read_text(encoding="utf-8")), "cached": True})

    url = f"{BASE}/models/{model}:generateContent"
    t0 = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            data = _request(url, body)
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(60, 2 ** attempt * 2))
                continue
            raise LLMError(f"Gemini HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(f"Gemini unreachable: {e}") from None
    latency = (time.perf_counter() - t0) * 1000

    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (KeyError, IndexError):
        reason = (data.get("candidates") or [{}])[0].get("finishReason") or data.get("promptFeedback")
        raise LLMError(f"Gemini returned no text ({reason})") from None
    usage = data.get("usageMetadata", {})
    tin = usage.get("promptTokenCount", 0)
    tout = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    cost = tin / 1e6 * config.PRICE_IN_PER_M + tout / 1e6 * config.PRICE_OUT_PER_M
    reply = Reply(text, tin, tout, latency, cost)
    if cache:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(asdict(reply)), encoding="utf-8")
    return reply


def list_models():
    data = _request(f"{BASE}/models?pageSize=200")
    return [m["name"].removeprefix("models/") for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


if __name__ == "__main__":
    if "--models" in sys.argv:
        print("\n".join(list_models()))
    else:
        r = generate("Reply with the single word: ready")
        print(f"{config.GEMINI_MODEL}: {r.text.strip()!r}  {r.latency_ms:.0f} ms  ${r.cost_usd:.6f}")
