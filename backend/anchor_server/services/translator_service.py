"""Serve cached Zotero translator metadata and code."""

import json
import re
from pathlib import Path

from anchor_server.config import settings


# Properties the connector uses to match translators and check for updates.
_TRANSLATOR_CACHING_PROPERTIES = {
    "translatorID",
    "label",
    "creator",
    "target",
    "minVersion",
    "maxVersion",
    "priority",
    "translatorType",
    "browserSupport",
    "inRepository",
    "lastUpdated",
}


def translators_dir() -> Path:
    """Return the directory where translators are cached."""
    return settings.translators_dir


def _metadata_path() -> Path:
    return translators_dir() / "metadata.json"


def list_translators() -> list[dict]:
    """Return translator metadata for all cached translators.

    If no cached metadata exists, returns an empty list; the connector will
    fall back to generic snapshot saving.
    """
    path = _metadata_path()
    if not path.exists():
        return []
    metadata = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            key: value
            for key, value in item.items()
            if key in _TRANSLATOR_CACHING_PROPERTIES
        }
        for item in metadata
    ]


def get_translator_code(translator_id: str) -> str:
    """Return the JavaScript source for a translator by ID.

    Looks up the cached marker file (``<safe_label>.json``) to find the
    on-disk filename. Falls back to scanning all marker files if needed.
    """
    for marker_path in translators_dir().glob("*.json"):
        if marker_path.name == "metadata.json":
            continue
        try:
            item = json.loads(marker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if item.get("translatorID") == translator_id:
            code_path = marker_path.with_suffix(".js")
            if code_path.exists():
                return code_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Translator {translator_id} not found")


def get_translators_hash(sorted_ids: bool = False) -> str:
    """Return an MD5 hash of cached translator IDs and lastUpdated times.

    This matches the hash computed by the Zotero connector so it can decide
    when to refresh its translator cache.
    """
    import hashlib

    items = list_translators()
    if sorted_ids:
        items = sorted(items, key=lambda x: x.get("translatorID", ""))

    hash_string = ""
    for item in items:
        translator_id = item.get("translatorID", "")
        last_updated = item.get("lastUpdated", "")
        hash_string += f"{translator_id}:{last_updated},"

    return hashlib.md5(hash_string.encode("utf-8")).hexdigest()


def get_proxy_list() -> list[dict]:
    """Return proxy configuration hints for the connector.

    Anchor itself does not manage proxies, but if an HTTP proxy is configured
    we expose it so the connector can route page requests accordingly.
    """
    proxy = settings.http_proxy
    if not proxy:
        return []
    # Very rough parse; enough for a host/port hint.
    match = re.match(r"https?://([^:/]+)(?::(\d+))?", proxy)
    if not match:
        return []
    host, port_str = match.groups()
    return [
        {
            "scheme": "http",
            "host": host,
            "port": int(port_str) if port_str else 80,
        }
    ]


def get_client_hostnames() -> list[str]:
    """Return local hostnames the connector may see."""
    return ["localhost", "127.0.0.1"]
