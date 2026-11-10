import re
import sys
from urllib.parse import urlparse

import httpx

import job_tools

ALIASES = {
    "taiwan semiconductor manufacturing": ["tsmc"],
    "saudi aramco": ["aramco"],
    "meta platforms": ["meta", "metaplatforms"],
    "samsung electronics": ["samsung"],
    "berkshire hathaway": ["berkshire"],
    "tencent holdings": ["tencent"],
}


def slugs_for(name: str) -> list:
    low = name.lower().strip()
    flat = re.sub(r"[^a-z0-9]", "", low)
    dashed = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    cands = [flat, dashed] + ALIASES.get(low, [])
    return [s for s in dict.fromkeys(cands) if s and job_tools.TOKEN_RE.match(s)]


path = job_tools.ALLOWED_DIR / "wishlist.txt"
names = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

for name in names:
    hits = []
    for slug in slugs_for(name):
        for ats in ("greenhouse", "lever"):
            try:
                jobs = job_tools.fetch_board(ats, slug)
            except (httpx.HTTPError, ValueError):
                continue
            if jobs:
                hosts = sorted({urlparse(j["url"]).hostname or "?" for j in jobs[:20]})
                hits.append((f"{ats}:{slug}", len(jobs), ", ".join(hosts[:3])))
    if hits:
        for board, n, hosts in hits:
            print(f"FOUND  {name:35} {board:30} {n:5} jobs   link hosts: {hosts}", flush=True)
    else:
        print(f"none   {name}", flush=True)