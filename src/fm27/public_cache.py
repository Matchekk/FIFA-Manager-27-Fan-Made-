"""Bounded, serialized public DFB fetches with immutable snapshots and provenance."""
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .common import write_json


class DfbCache:
    def __init__(self, root: Path, host: str = "datencenter.dfb.de"):
        if host not in {"datencenter.dfb.de", "www.ea.com", "www.transfermarkt.de"}:
            raise ValueError("Unsupported public source host")
        self.host = host
        self.root = root
        self.last_request = 0.0
        self.robots = None
        request = urllib.request.Request(f"https://{self.host}/robots.txt", headers={"User-Agent": "FM27Research/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                self.robots = RobotFileParser()
                self.robots.parse(response.read(100000).decode("utf-8").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

    def fetch(self, url: str, reuse_today: bool = False) -> tuple[str, dict]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != self.host:
            raise ValueError("Cache only accepts its configured official host")
        if self.robots and not self.robots.can_fetch("FM27Research", url):
            raise ValueError("Source disallows this automated fetch")
        key = hashlib.sha256(url.encode()).hexdigest()
        if reuse_today:
            for item in sorted(self.root.glob(f"{key}-*.json"), reverse=True):
                metadata = json.loads(item.read_text(encoding="utf-8"))
                if metadata["url"] != url or metadata["retrieved_at"][:10] != dt.datetime.now(dt.timezone.utc).date().isoformat():
                    continue
                path = self.root / (metadata["sha256"] + ".html")
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
                    raise ValueError("Cached source hash mismatch")
                return content.decode("utf-8-sig"), metadata
        request = urllib.request.Request(url, headers={"User-Agent": "FM27Research/0.1"})
        for attempt in range(3):
            time.sleep(max(0, 1.0 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    if urlsplit(response.url).hostname != self.host:
                        raise ValueError("Unexpected source redirect")
                    content = response.read(4_000_001)
                    if len(content) > 4_000_000:
                        raise ValueError("Oversized source page")
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / f"{digest}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Cached source hash mismatch")
        metadata = {"url": url, "retrieved_at": stamp, "sha256": digest, "file": path.name}
        key = hashlib.sha256(url.encode()).hexdigest()
        write_json(self.root / f"{key}-{stamp.replace(':','-')}.json", metadata)
        return content.decode("utf-8-sig"), metadata
