"""Archive every response before interpretation, including HTTP failures."""
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import requests


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def safe_url(url):
    p = urlsplit(url)
    hidden = {"api_key", "apikey", "token", "access_token"}
    query = urlencode([(k, "REDACTED" if k.lower() in hidden else v)
                       for k, v in parse_qsl(p.query, keep_blank_values=True)])
    return urlunsplit((p.scheme, p.netloc, p.path, query, ""))


def emit(event, **fields):
    print(json.dumps({"timestamp": utcnow(), "event": event, **fields}), flush=True)


def retry_delay(header, attempt):
    try:
        value = float(header)
    except (TypeError, ValueError):
        try:
            value = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            value = 2 ** (attempt - 1) + random.random()
    return max(0, value)


class Fetcher:
    def __init__(self, root="data", session=None, sleep=time.sleep):
        self.root = Path(root)
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "MFAPIs-Research-PoC/1.0"})
        self.sleep = sleep

    def get(self, source, url, params=None):
        requested = requests.Request("GET", url, params=params).prepare().url
        for attempt in range(1, 4):
            meta = {"request_id": uuid4().hex, "source": source,
                    "requested_at": utcnow(), "url": safe_url(requested), "attempt": attempt}
            started = time.monotonic()
            try:
                r = self.session.get(url, params=params, timeout=(10, 40))
            except (requests.Timeout, requests.ConnectionError) as exc:
                meta.update(error=type(exc).__name__, elapsed_ms=round((time.monotonic()-started)*1000))
                self._log(meta)
                if attempt == 3:
                    raise
                self.sleep(retry_delay(None, attempt))
                continue
            body = r.content  # decoded entity bytes; transport gzip is handled by requests
            digest = hashlib.sha256(body).hexdigest()
            path = self.root / "raw" / (digest + ".bin")
            if not path.exists():
                path.write_bytes(body)
            meta.update(status=r.status_code, final_url=safe_url(r.url), bytes=len(body),
                        sha256=digest, raw_path=str(path.relative_to(self.root)),
                        fetched_at=utcnow(), elapsed_ms=round((time.monotonic()-started)*1000),
                        headers={k: r.headers[k] for k in ["Content-Type", "Date", "ETag", "Last-Modified", "Retry-After"] if k in r.headers})
            self._log(meta)
            if r.status_code == 429 or r.status_code in {500, 502, 503, 504}:
                r.raise_for_status() if attempt == 3 else None
                delay = retry_delay(r.headers.get("Retry-After"), attempt)
                if delay > 60:
                    raise RuntimeError("Provider requested a long retry delay; rerun later")
                self.sleep(delay)
                continue
            r.raise_for_status()  # 401/403/404 are not bypassed or repeatedly retried
            if not body:
                raise ValueError("Empty HTTP response")
            return body, meta
        raise RuntimeError("Retry loop exhausted")

    def _log(self, meta):
        with (self.root / "http_evidence.jsonl").open("a") as f:
            f.write(json.dumps(meta) + "\n")
        emit("http_request", **meta)
