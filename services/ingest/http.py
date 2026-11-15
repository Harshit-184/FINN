"""Shared fetch helper: on-disk cache, 3 retries with backoff, a per-host rate limit, and the URL kept
with every response. No endpoint is assumed to stay available."""
import hashlib, json, time
from pathlib import Path
from urllib.parse import urlparse
import httpx

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_last: dict[str, float] = {}


class SourceError(RuntimeError):
    pass


def get(client: httpx.Client, url: str, *, params=None, headers=None, ttl: int = 1500, min_gap: float = 1.0,
        as_json: bool = True):
    """ttl in seconds; 0 disables the cache read (the response is still written)."""
    key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    path = CACHE / urlparse(url).netloc / f"{key}.{'json' if as_json else 'bin'}"
    if ttl and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text()) if as_json else path.read_bytes()
    host, err = urlparse(url).netloc, None
    for attempt in range(3):                         # 3 tries, backing off 1s then 2s
        wait = min_gap - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            _last[host] = time.time()
            r = client.get(url, params=params, headers=headers, timeout=12)
            r.raise_for_status()
            data = r.json() if as_json else r.content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data)) if as_json else path.write_bytes(data)
            return data
        except (httpx.HTTPError, ValueError) as e:
            err = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise SourceError(f"{host}: {err}")
