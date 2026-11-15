"""Model calls. One provider (Gemini) behind one function, with a disk cache keyed by
document hash + prompt version + model, and a token log for the cost note."""
import hashlib, json, os, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "llm"
COST_LOG = ROOT / "data" / "snapshot" / "llm_usage.json"
BASE = "https://generativelanguage.googleapis.com/v1beta"


def api_key() -> str | None:
    if os.getenv("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


_model: dict[str, str] = {}


def pick_model(client: httpx.Client, tier: str) -> str:
    """tier 'cheap' -> a Flash model, 'strong' -> a Pro model. Chosen from what the key can actually call,
    so the code does not break when model names change. FINN_MODEL_CHEAP / FINN_MODEL_STRONG override."""
    if tier in _model:
        return _model[tier]
    if (forced := os.getenv(f"FINN_MODEL_{tier.upper()}")):
        _model[tier] = forced
        return forced
    r = client.get(f"{BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": api_key()}, timeout=20)
    r.raise_for_status()
    names = sorted((m["name"].split("/")[-1] for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                    and not any(x in m["name"] for x in ("preview", "exp", "tts", "image", "lite", "live", "audio", "embedding"))),
                   reverse=True)
    want = "flash" if tier == "cheap" else "pro"
    chosen = next((n for n in names if n.startswith("gemini") and want in n), None) or next(n for n in names if "flash" in n)
    _model[tier] = chosen
    return chosen


def ask_json(client: httpx.Client, prompt: str, *, doc_hash: str, prompt_version: str, tier: str = "cheap") -> dict | list | None:
    """Returns parsed JSON, or None after one retry (bad output is dropped, never shown)."""
    if not api_key():
        return None
    model = pick_model(client, tier)
    key = hashlib.sha1(f"{doc_hash}|{prompt_version}|{model}".encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    last = "no attempt made"
    for attempt in range(2):
        try:
            r = client.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": api_key()}, timeout=180)
            if r.status_code != 200:
                last = f"HTTP {r.status_code} from {model}: {r.text[:300]}"
                if r.status_code in (429, 500, 503):
                    time.sleep(20)
                    continue
                break                                    # 400/401/403/404 will not get better on retry
            data = r.json()
            out = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            _log(model, tier, prompt_version, data.get("usageMetadata", {}))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out))
            return out
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            last = f"{type(e).__name__}: {str(e)[:300]}"
    global last_error
    last_error = last
    return None


last_error = ""


def _log(model: str, tier: str, prompt_version: str, usage: dict) -> None:
    rows = json.loads(COST_LOG.read_text()) if COST_LOG.exists() else []
    rows.append({"model": model, "tier": tier, "prompt": prompt_version,
                 "in": usage.get("promptTokenCount", 0), "out": usage.get("candidatesTokenCount", 0)})
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG.write_text(json.dumps(rows))
