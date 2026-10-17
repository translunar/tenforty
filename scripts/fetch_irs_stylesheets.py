# scripts/fetch_irs_stylesheets.py
"""Download the IRS MeF stylesheet packages (one zip per tax year) into
``~/.cache/tenforty/irs-stylesheets/<year>/`` and verify each against its
sha256 pin in ``tenforty/declarations/stylesheets/manifest.py``.

Never writes into the repo. irs.gov refuses the default urllib User-Agent
(HTTP 403), so a browser User-Agent is sent. A package whose sha256 differs
from its pin is a hard stop (exit 2): never substitute a different file.
A year with no pin yet (first fetch) prints the hash and the zip's top
folder so they can be recorded in the manifest.

Usage:
    python scripts/fetch_irs_stylesheets.py                # every year with a URL
    python scripts/fetch_irs_stylesheets.py --year 2025
    python scripts/fetch_irs_stylesheets.py --url 2024=https://.../py2025r1.zip
    python scripts/fetch_irs_stylesheets.py --extract-only   # rewrite the JSON
    python scripts/fetch_irs_stylesheets.py --check          # is the commit current?
"""
import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

CACHE = Path.home() / ".cache" / "tenforty" / "irs-stylesheets"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_ALLOWED_PREFIX = "https://www.irs.gov/pub/irs-schema/"


def cached_zip(year: int) -> Path:
    return CACHE / str(year) / "stylesheets.zip"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def top_folder(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    if len(tops) != 1:
        raise SystemExit(f"{path}: expected one top folder, found {sorted(tops)}")
    return tops.pop()


def fetch(year: int, url: str, pinned: str | None) -> tuple[str, str]:
    if not url.startswith(_ALLOWED_PREFIX):
        raise SystemExit(f"refusing non-irs.gov URL {url}")
    dest = cached_zip(year)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    digest = sha256_of(tmp)
    if pinned and digest != pinned:
        tmp.unlink()
        print(f"STOP: TY{year} {url} sha256 {digest} != pinned {pinned}",
              file=sys.stderr)
        raise SystemExit(2)
    if not zipfile.is_zipfile(tmp):
        tmp.unlink()
        raise SystemExit(f"TY{year}: {url} is not a zip")
    tmp.replace(dest)
    return digest, top_folder(dest)


def main(argv=None) -> int:
    from tenforty.declarations.stylesheets.manifest import PACKAGES
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, action="append")
    ap.add_argument("--url", action="append", default=[],
                    help="YEAR=URL for a year not yet in the manifest")
    ap.add_argument("--extract-only", action="store_true",
                    help="skip downloading; re-extract the committed JSON "
                         "from the cached, pin-verified packages")
    ap.add_argument("--check", action="store_true",
                    help="re-extract from the cached, pin-verified packages "
                         "and report committed JSON that differs (exit 1)")
    args = ap.parse_args(argv)
    if args.extract_only:
        from tenforty.declarations.stylesheet import write_extractions
        print(f"wrote {len(write_extractions(CACHE))} extraction files")
        return 0
    if args.check:
        from tenforty.declarations.stylesheet import write_extractions
        stale = write_extractions(CACHE, check=True)
        for path in stale:
            print(f"STALE {path}")
        print("committed extractions are current" if not stale
              else f"{len(stale)} committed extraction file(s) are stale")
        return 1 if stale else 0
    urls = {y: p.url for y, p in PACKAGES.items()}
    urls.update({int(k): v for k, v in (u.split("=", 1) for u in args.url)})
    for year in sorted(args.year or urls):
        pinned = PACKAGES[year].sha256 if year in PACKAGES else None
        digest, folder = fetch(year, urls[year], pinned)
        state = "MATCHES PIN" if pinned else "UNPINNED (record it)"
        print(f"TY{year} {urls[year]}\n  sha256 {digest} {state}\n  top folder {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
