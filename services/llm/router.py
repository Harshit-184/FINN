"""Model calls. One provider (Gemini) behind one function, with a disk cache keyed by
document hash + prompt version + model, and a token log for the cost note."""
import hashlib, json, os, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "llm"
COST_LOG = ROOT / "data" / "snapshot" / "llm_usage.json"
BASE = "https://generativelanguage.googleapis.com/v1beta"
GOOD = ROOT / "data" / "cache" / "llm_model.txt"


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
    found = (pro + flash if tier == "strong" else flash)[:6]
    good = GOOD.read_text().strip() if GOOD.exists() else "gemini-3.6-flash"     # last model that answered
    _candidates[tier] = ([good] if good in found or not found else []) + [n for n in found if n != good]
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
    try:
        models = candidates(client, tier)
    except httpx.HTTPError as e:
        last_error = f"could not list models: {type(e).__name__}: {str(e)[:200]}"
        return None
    print(f"  llm: candidates {models}", flush=True)
    for model in list(models):
        tries = 5 if model == models[0] else 1          # be patient with the model that works; one shot at the others
        for attempt in range(tries):
            try:
                print(f"  llm: asking {model} (try {attempt + 1}, {len(prompt) // 1000}k chars)...", flush=True)
                r = client.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": api_key()}, timeout=90)
                print(f"  llm: {model} -> HTTP {r.status_code}", flush=True)
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code} from {model}: {r.text[:240]}"
                    daily = "PerDay" in r.text or "limit: 0" in r.text
                    if r.status_code in (429, 500, 503) and not daily and attempt + 1 < tries:
                        print("  llm: per-minute limit or overload, waiting 45s...", flush=True)
                        time.sleep(45)                   # free-tier tokens-per-minute limit clears within a minute
                        continue
                    break                                # daily quota gone or no quota: try the next model
                data = r.json()
                out = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
                _log(model, tier, prompt_version, data.get("usageMetadata", {}))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(out))
                models.remove(model); models.insert(0, model)
                GOOD.parent.mkdir(parents=True, exist_ok=True); GOOD.write_text(model)
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
