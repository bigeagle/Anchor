"""Download and cache Zotero translators from the official repository."""

import json
import os
import re
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

from anchor_server.config import settings


# The Zotero version we claim to be when talking to the repository.
_ZOTERO_VERSION = "7.0"
# Number of concurrent translator downloads.
_DOWNLOAD_WORKERS = 20


def _http_proxy() -> str | None:
    """Return the proxy to use for repository requests.

    Prefers the explicit ``ANCHOR_HTTP_PROXY`` setting, then falls back to
    standard environment variables.
    """
    return (
        settings.http_proxy
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
    )


def _urlopen(url: str, timeout: int = 60) -> urllib.request.addinfourl:
    """Open a URL, routing through the configured proxy if any."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"Zotero/{_ZOTERO_VERSION}",
            "X-Zotero-Version": _ZOTERO_VERSION,
        },
    )
    proxy = _http_proxy()
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        opener = urllib.request.build_opener(proxy_handler)
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def fetch_metadata() -> list[dict]:
    """Fetch the full translator metadata list from the Zotero repository."""
    url = urljoin(
        settings.zotero_repo_url,
        f"metadata?version={_ZOTERO_VERSION}&last=0",
    )
    with _urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_code(translator_id: str) -> str:
    """Fetch the JavaScript source for a single translator."""
    url = urljoin(
        settings.zotero_repo_url,
        f"code/{translator_id}?version={_ZOTERO_VERSION}",
    )
    with _urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def _safe_filename(label: str) -> str:
    """Convert a translator label into a safe filesystem name."""
    base = re.sub(r"[^\w\s-]", "", label).strip()
    return re.sub(r"[-\s]+", "_", base) or "translator"


def _is_valid_uuid(value: str) -> bool:
    """Return True if ``value`` looks like a UUID string."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _sync_one(
    item: dict, old_by_id: dict, translators_dir: Path, force: bool
) -> tuple[str, str | None]:
    """Download a single translator if needed.

    Returns (status, error_message). Status is "downloaded", "skipped", or "failed".
    """
    translator_id = item.get("translatorID", "")
    label = item.get("label", translator_id)
    last_updated = item.get("lastUpdated", "")
    if not _is_valid_uuid(translator_id):
        return "failed", f"{label}: invalid translatorID {translator_id!r}"

    code_path = translators_dir / f"{_safe_filename(label)}.js"
    marker_path = code_path.with_suffix(".json")

    if (
        not force
        and code_path.exists()
        and marker_path.exists()
        and old_by_id.get(translator_id, {}).get("lastUpdated") == last_updated
    ):
        return "skipped", None

    try:
        code = fetch_code(translator_id)
    except Exception as exc:
        return "failed", f"{label}: {exc}"

    code_path.write_text(code, encoding="utf-8")
    marker_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return "downloaded", None


def sync_translators(force: bool = False) -> tuple[int, int, list[str]]:
    """Sync translators from the Zotero repository into ``translators_dir``.

    Returns (downloaded_count, skipped_count, errors). With ``force=True``,
    re-download every translator regardless of ``lastUpdated``.
    """
    translators_dir = settings.translators_dir
    translators_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = translators_dir / "metadata.json"
    old_metadata: list[dict] = []
    if metadata_path.exists():
        old_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    old_by_id = {item["translatorID"]: item for item in old_metadata}

    print("Fetching translator metadata...")
    metadata = fetch_metadata()
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    downloaded = 0
    skipped = 0
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as executor:
        futures = {
            executor.submit(_sync_one, item, old_by_id, translators_dir, force): item
            for item in metadata
        }
        for future in as_completed(futures):
            status, error = future.result()
            if status == "downloaded":
                downloaded += 1
            elif status == "skipped":
                skipped += 1
            else:
                errors.append(error or "unknown error")

    return downloaded, skipped, errors


if __name__ == "__main__":
    import sys

    force = "--force" in sys.argv
    down, skip, errs = sync_translators(force=force)
    print(f"Done. Downloaded: {down}, skipped: {skip}, errors: {len(errs)}")
    for err in errs[:10]:
        print(f"  - {err}")
