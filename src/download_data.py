"""Download the 2023 national YRBS files from CDC into data/raw/.

Usage (from the project root):
    python -m src.download_data            # download whatever is missing
    python -m src.download_data --force    # re-download and replace existing files
    python -m src.download_data --verify   # check a manually downloaded file and log its hash

CDC's website sits behind a CDN that sometimes refuses scripted requests with
HTTP 403 "Access Denied". When that happens this script stops and prints the manual
browser steps. It does not try to get around the block.

Downloaded raw files are made read-only so they are not changed by accident.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

try:
    from src.data_processing import (DAT_URL, DATA_PAGE_URL, RAW_DAT_FILE, RAW_DIR,
                                     DataFileError, check_raw_file)
except ModuleNotFoundError:  # run as "python src/download_data.py"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.data_processing import (DAT_URL, DATA_PAGE_URL, RAW_DAT_FILE, RAW_DIR,
                                     DataFileError, check_raw_file)

DOC_DIR = RAW_DIR / "documentation"
LOG_FILE = RAW_DIR / "download_log.json"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "social-media-wellbeing student project (python urllib)")


@dataclass(frozen=True)
class RemoteFile:
    url: str
    dest: Path
    required: bool
    min_bytes: int


FILES: List[RemoteFile] = [
    RemoteFile(DAT_URL, RAW_DAT_FILE, required=True, min_bytes=1_000_000),
    RemoteFile("https://www.cdc.gov/yrbs/media/pdf/2023/2023_National_YRBS_Data_Users_Guide508.pdf",
               DOC_DIR / "2023_National_YRBS_Data_Users_Guide508.pdf", required=False,
               min_bytes=10_000),
    RemoteFile("https://www.cdc.gov/yrbs/files/2023/2023XXH-SAS-Input-Program.sas",
               DOC_DIR / "2023XXH-SAS-Input-Program.sas", required=False, min_bytes=1_000),
    RemoteFile("https://www.cdc.gov/yrbs/files/2023/2023XXH-Formats-Program.sas",
               DOC_DIR / "2023XXH-Formats-Program.sas", required=False, min_bytes=1_000),
]


class DownloadBlocked(Exception):
    pass


def manual_instructions() -> str:
    return (
        "\nManual download steps\n"
        "---------------------\n"
        f"1. Open {DATA_PAGE_URL} in a web browser.\n"
        "2. Under the 2023 national YRBS data, click 'ASCII'.\n"
        "   (Direct link: " + DAT_URL + ")\n"
        "3. Save the file, keeping its name, as:\n"
        f"     {RAW_DAT_FILE}\n"
        "4. Check it and record its hash:\n"
        "     python -m src.download_data --verify\n"
        "5. Then build the cleaned dataset:\n"
        "     python -m src.data_processing\n"
    )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_read_only(path: Path) -> None:
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def _make_writable(path: Path) -> None:
    if path.exists():
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def _append_log(entry: dict) -> None:
    entries = []
    if LOG_FILE.exists():
        try:
            entries = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append(entry)
    LOG_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _log_file(path: Path, url: str, method: str) -> None:
    _append_log({
        "file": str(path.relative_to(RAW_DIR.parent.parent)),
        "source_url": url,
        "method": method,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": sha256_of(path),
    })


def download(remote: RemoteFile, force: bool = False) -> bool:
    """Download one file. Returns True if the file is present afterwards."""
    dest = remote.dest
    if dest.exists() and not force:
        print(f"  exists, skipped: {dest.name}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(remote.url, headers={"User-Agent": USER_AGENT,
                                                          "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as out:
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        if exc.code in (401, 403):
            raise DownloadBlocked(f"CDC refused the request (HTTP {exc.code}) for {remote.url}")
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        part.unlink(missing_ok=True)
        raise

    with part.open("rb") as fh:
        head = fh.read(512).lstrip().lower()
    if head.startswith((b"<html", b"<!doctype")) and not dest.suffix.lower() in (".html", ".htm"):
        part.unlink(missing_ok=True)
        raise DownloadBlocked(f"CDC returned a web page instead of {dest.name} "
                              f"(likely an 'Access Denied' page).")
    size = part.stat().st_size
    if size < remote.min_bytes:
        part.unlink(missing_ok=True)
        raise DataFileError(f"{dest.name} is only {size:,} bytes; expected at least "
                            f"{remote.min_bytes:,}. The download was probably incomplete.")

    _make_writable(dest)
    os.replace(part, dest)
    _make_read_only(dest)
    _log_file(dest, remote.url, "python -m src.download_data")
    print(f"  downloaded: {dest.name} ({size:,} bytes)")
    return True


def verify() -> int:
    """Check a manually downloaded .dat file and record its hash."""
    try:
        check_raw_file(RAW_DAT_FILE)
    except (DataFileError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _make_read_only(RAW_DAT_FILE)
    _log_file(RAW_DAT_FILE, DAT_URL, "manual browser download, verified")
    print(f"OK: {RAW_DAT_FILE} ({RAW_DAT_FILE.stat().st_size:,} bytes). "
          f"Hash recorded in {LOG_FILE}. File set to read-only.")
    return 0


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Download the 2023 national YRBS files from CDC.")
    parser.add_argument("--force", action="store_true", help="Replace files that already exist.")
    parser.add_argument("--verify", action="store_true",
                        help="Only check a manually downloaded .dat file and log its hash.")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    print(f"Downloading 2023 national YRBS files into {RAW_DIR}")
    required_ok = True
    for remote in FILES:
        try:
            download(remote, force=args.force)
        except DownloadBlocked as exc:
            print(f"  BLOCKED: {exc}")
            required_ok = required_ok and not remote.required
        except (urllib.error.URLError, TimeoutError, OSError, DataFileError) as exc:
            print(f"  FAILED: {remote.dest.name}: {exc}")
            required_ok = required_ok and not remote.required

    if not required_ok:
        print(manual_instructions())
        return 1
    print("\nDone. Next step:  python -m src.data_processing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
