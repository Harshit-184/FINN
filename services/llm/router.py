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


_candidates: dict[str, list[str]] = {}
last_error = ""


def candidates(client: httpx.Client, tier: str) -> list[str]:
    """Models to try, best first: 'cheap' -> Flash, 'strong' -> Pro then Flash. Read from what the key can call,
    so names are not hard-wired. A model with no free quota (e.g. Omni Flash) answers 429 and the next one is tried;
    the first that works is moved to the front. FINN_MODEL_CHEAP / FINN_MODEL_STRONG force one."""
    if tier in _candidates:
        return _candidates[tier]
    if (forced := os.getenv(f"FINN_MODEL_{tier.upper()}")):
        _candidates[tier] = [forced]
        return _candidates[tier]
    r = client.get(f"{BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": api_key()}, timeout=20)
    r.raise_for_status()
    skip = ("preview", "exp", "tts", "image", "live", "audio", "embedding", "omni", "computer", "robotics")
    names = sorted((m["name"].split("/")[-1] for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                    and m["name"].split("/")[-1].startswith("gemini") and not any(x in m["name"] for x in skip)), reverse=True)
    flash = [n for n in names if "flash" in n and "lite" not in n] + [n for n in names if "flash-lite" in n]
    pro = [n for n in names if "pro" in n]
    _candidates[tier] = (pro + flash if tier == "strong" else flash)[:6]
    return _candidates[tier]


def ask_json(client: httpx.Client, prompt: str, *, doc_hash: str, prompt_version: str, tier: str = "cheap") -> dict | list | None:
    """Returns parsed JSON, or None (bad output is dropped, never shown). Cached by document + prompt version."""
    global last_error
    if not api_key():
        last_error = "no GEMINI_API_KEY"
        return None
    path = CACHE / f"{hashlib.sha1(f'{doc_hash}|{prompt_version}|{tier}'.encode()).hexdigest()}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    models = candidates(client, tier)
    for model in list(models):
        for attempt in range(2):
            try:
                r = client.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": api_key()}, timeout=180)
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code} from {model}: {r.text[:240]}"
                    if r.status_code in (500, 503) or (r.status_code == 429 and "limit: 0" not in r.text and attempt == 0):
                        time.sleep(25)                   # a per-minute limit clears; a zero quota does not
                        continue
                    break                                # try the next model
                data = r.json()
                out = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
                _log(model, tier, prompt_version, data.get("usageMetadata", {}))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(out))
                models.remove(model); models.insert(0, model)
                return out
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                last_error = f"{model}: {type(e).__name__}: {str(e)[:240]}"
                break
    return None


def _log(model: str, tier: str, prompt_version: str, usage: dict) -> None:
    rows = json.loads(COST_LOG.read_text()) if COST_LOG.exists() else []
    rows.append({"model": model, "tier": tier, "prompt": prompt_version,
                 "in": usage.get("promptTokenCount", 0), "out": usage.get("candidatesTokenCount", 0)})
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG.write_text(json.dumps(rows))
