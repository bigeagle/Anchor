# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "markitdown[pdf]"]
# ///
"""CLI helper for accessing papers in Anchor from an AI agent."""

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

import requests
from markitdown import MarkItDown


DEFAULT_BASE_URL = "http://127.0.0.1:23119/api/v1"


def base_url() -> str:
    return os.environ.get("ANCHOR_API_URL", DEFAULT_BASE_URL).rstrip("/")


def auth_token() -> str | None:
    return os.environ.get("ANCHOR_API_TOKEN") or None


def request_headers(accept: str = "application/json") -> dict[str, str]:
    headers = {"Accept": accept}
    token = auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _url(path: str) -> str:
    return urljoin(base_url() + "/", path.lstrip("/"))


def get_json(path: str, params: dict | None = None) -> dict | list:
    response = requests.get(
        _url(path), params=params, headers=request_headers(), timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_bytes(path: str) -> bytes:
    response = requests.get(_url(path), headers=request_headers(), timeout=120)
    response.raise_for_status()
    return response.content


def get_text(path: str) -> str:
    response = requests.get(
        _url(path), headers=request_headers("text/plain"), timeout=120
    )
    response.raise_for_status()
    return response.text


def post_json(path: str, payload: dict) -> dict:
    response = requests.post(
        _url(path),
        json=payload,
        headers=request_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def post_file(path: str, field_name: str, filename: str, data: bytes) -> dict:
    files = {field_name: (filename, data, "application/pdf")}
    response = requests.post(
        _url(path),
        files=files,
        headers=request_headers(),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def print_json(data: dict | list) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def parse_author(value: str) -> dict[str, str]:
    """Convert 'First Last' into an Anchor creator dict."""
    parts = value.strip().split()
    if len(parts) == 1:
        return {"first_name": "", "last_name": parts[0]}
    return {"first_name": " ".join(parts[:-1]), "last_name": parts[-1]}


# ---------------------------------------------------------------------------
# Anchor library commands
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    params = {"limit": args.limit, "skip": args.offset}
    if args.query:
        params["q"] = args.query
    print_json(get_json("items", params))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    print_json(get_json(f"items/{args.item_id}"))
    return 0


def cmd_attachments(args: argparse.Namespace) -> int:
    print_json(get_json(f"items/{args.item_id}/attachments"))
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    data = get_bytes(f"attachments/{args.attachment_id}")
    output = Path(args.output)
    output.write_bytes(data)
    print(f"Downloaded {len(data)} bytes to {output}", file=sys.stderr)
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    text = get_text(f"attachments/{args.attachment_id}/markdown")
    try:
        sys.stdout.write(text)
    except BrokenPipeError:
        pass
    return 0


def cmd_import_pdf(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_file():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return 1

    payload: dict = {"title": args.title, "item_type": args.item_type}

    if args.author:
        payload["authors"] = [parse_author(a) for a in args.author]

    for field in (
        "abstract",
        "publication",
        "volume",
        "issue",
        "pages",
        "doi",
        "arxiv_id",
        "isbn",
        "url",
        "language",
    ):
        value = getattr(args, field)
        if value is not None:
            payload[field] = value

    if args.year is not None:
        payload["year"] = args.year

    item = post_json("items", payload)
    item_id = item["id"]

    data = pdf_path.read_bytes()
    attachment = post_file(
        f"items/{item_id}/attachments",
        "file",
        pdf_path.name,
        data,
    )

    print_json({"item": item, "attachment": attachment})
    return 0


# ---------------------------------------------------------------------------
# arXiv client
# ---------------------------------------------------------------------------


class ArxivClient:
    """Fetch arXiv metadata, PDFs, source packages, and Markdown text."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        base = cache_dir or Path.home() / ".cache" / "anchor-papers"
        self.cache_dir = base
        self.pdf_dir = base / "arxiv" / "pdf"
        self.meta_dir = base / "arxiv" / "metadata"
        self.source_dir = base / "arxiv" / "source"
        self.markdown_dir = base / "arxiv" / "markdown"
        for d in (
            self.cache_dir,
            self.pdf_dir,
            self.meta_dir,
            self.source_dir,
            self.markdown_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        self.md = MarkItDown()

    def _meta_cache(self, arxiv_id: str) -> Path:
        return self.meta_dir / f"{arxiv_id}.json"

    def _pdf_cache(self, arxiv_id: str, pdf_url: str) -> Path:
        filename = pdf_url.split("/")[-1]
        if not filename.endswith(".pdf"):
            filename = f"{filename or arxiv_id}.pdf"
        return self.pdf_dir / filename

    def fetch_metadata(self, arxiv_id: str) -> dict:
        """Fetch arXiv metadata, with a simple file cache."""
        cache = self._meta_cache(arxiv_id)
        if cache.exists():
            return json.loads(cache.read_text("utf-8"))

        url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        metadata = self._parse_metadata(response.text, arxiv_id)
        cache.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), "utf-8")
        return metadata

    def _parse_metadata(self, xml_text: str, arxiv_id: str) -> dict:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            raise ValueError(f"Paper not found on arXiv: {arxiv_id}")

        title_el = entry.find("atom:title", ns)
        authors = entry.findall("atom:author/atom:name", ns)
        summary = entry.find("atom:summary", ns)
        published = entry.find("atom:published", ns)
        categories = [
            c.attrib["term"]
            for c in entry.findall("atom:category", ns)
            if "term" in c.attrib
        ]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        for link in entry.findall("atom:link", ns):
            if (
                link.get("title") == "pdf"
                and link.get("type") == "application/pdf"
                and link.get("href")
            ):
                pdf_url = link.get("href")
                break

        published_text = published.text if published is not None else ""
        year = None
        if published_text and len(published_text) >= 4:
            try:
                year = int(published_text[:4])
            except ValueError:
                pass

        return {
            "arxiv_id": arxiv_id,
            "title": (
                title_el.text.strip() if title_el is not None and title_el.text else ""
            ),
            "authors": [a.text or "" for a in authors],
            "abstract": (
                summary.text.strip() if summary is not None and summary.text else ""
            ),
            "published": published_text,
            "year": year,
            "categories": categories,
            "pdf_url": pdf_url,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        }

    def download_pdf(self, arxiv_id: str) -> Path:
        """Download the arXiv PDF, with caching."""
        metadata = self.fetch_metadata(arxiv_id)
        pdf_url = metadata["pdf_url"]
        cache = self._pdf_cache(arxiv_id, pdf_url)
        if cache.exists() and cache.stat().st_size > 0:
            return cache

        response = requests.get(pdf_url, timeout=120)
        response.raise_for_status()
        cache.write_bytes(response.content)
        return cache

    def get_markdown(self, arxiv_id: str) -> str:
        """Return the arXiv PDF as Markdown."""
        pdf_path = self.download_pdf(arxiv_id)
        cache = self.markdown_dir / f"{arxiv_id}.md"
        if cache.exists():
            return cache.read_text("utf-8")

        result = self.md.convert(str(pdf_path))
        text = result.text_content
        cache.write_text(text, "utf-8")
        return text

    def download_source(self, arxiv_id: str) -> Path:
        """Download and extract the arXiv source package."""
        source_dir = self.source_dir / arxiv_id
        if source_dir.exists() and any(source_dir.iterdir()):
            return source_dir

        source_dir.mkdir(parents=True, exist_ok=True)
        url = f"https://arxiv.org/src/{arxiv_id}"
        response = requests.get(url, timeout=120)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        try:
            with gzip.open(tmp_path, "rb") as gz:
                gz.read(1)
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path=source_dir, filter="data")
        except (tarfile.TarError, gzip.BadGzipFile):
            shutil.copy2(tmp_path, source_dir / "main.tex")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return source_dir


# ---------------------------------------------------------------------------
# arXiv commands
# ---------------------------------------------------------------------------


def cmd_arxiv_fetch(args: argparse.Namespace) -> int:
    client = ArxivClient()
    metadata = client.fetch_metadata(args.arxiv_id)
    print_json(metadata)
    return 0


def cmd_arxiv_pdf(args: argparse.Namespace) -> int:
    client = ArxivClient()
    pdf_path = client.download_pdf(args.arxiv_id)
    if args.open:
        if sys.platform == "darwin":
            subprocess.run(["open", str(pdf_path)], check=False)
        else:
            print(f"--open is not supported on {sys.platform}", file=sys.stderr)
            return 1
    else:
        print(pdf_path)
    return 0


def cmd_arxiv_markdown(args: argparse.Namespace) -> int:
    client = ArxivClient()
    text = client.get_markdown(args.arxiv_id)
    try:
        sys.stdout.write(text)
    except BrokenPipeError:
        pass
    return 0


def cmd_arxiv_source(args: argparse.Namespace) -> int:
    client = ArxivClient()
    source_dir = client.download_source(args.arxiv_id)
    files = sorted(p.name for p in source_dir.iterdir() if p.is_file())
    print_json(
        {"arxiv_id": args.arxiv_id, "source_dir": str(source_dir), "files": files}
    )
    return 0


def cmd_arxiv_save(args: argparse.Namespace) -> int:
    client = ArxivClient()
    metadata = client.fetch_metadata(args.arxiv_id)

    item_payload = {
        "title": metadata["title"],
        "item_type": "preprint",
        "authors": [parse_author(a) for a in metadata["authors"]],
        "abstract": metadata["abstract"],
        "year": metadata["year"],
        "arxiv_id": metadata["arxiv_id"],
        "url": metadata["url"],
    }

    item = post_json("items", item_payload)
    item_id = item["id"]

    attachment = None
    if not args.no_pdf:
        pdf_path = client.download_pdf(args.arxiv_id)
        attachment = post_file(
            f"items/{item_id}/attachments",
            "file",
            pdf_path.name,
            pdf_path.read_bytes(),
        )

    print_json({"item": item, "attachment": attachment})
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchor papers access helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Anchor library
    list_parser = subparsers.add_parser("list", help="List items")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--offset", type=int, default=0)
    list_parser.add_argument("--query", "-q", type=str, default=None)
    list_parser.set_defaults(func=cmd_list)

    get_parser = subparsers.add_parser("get", help="Get an item by ID")
    get_parser.add_argument("item_id")
    get_parser.set_defaults(func=cmd_get)

    attachments_parser = subparsers.add_parser(
        "attachments", help="List attachments for an item"
    )
    attachments_parser.add_argument("item_id")
    attachments_parser.set_defaults(func=cmd_attachments)

    download_parser = subparsers.add_parser(
        "download", help="Download an attachment file"
    )
    download_parser.add_argument("attachment_id")
    download_parser.add_argument("output")
    download_parser.set_defaults(func=cmd_download)

    text_parser = subparsers.add_parser(
        "text", help="Extract Markdown text from an attachment"
    )
    text_parser.add_argument("attachment_id")
    text_parser.set_defaults(func=cmd_text)

    import_parser = subparsers.add_parser(
        "import-pdf", help="Create an item and upload a PDF attachment"
    )
    import_parser.add_argument("pdf_path")
    import_parser.add_argument("--title", type=str, required=True)
    import_parser.add_argument(
        "-a",
        "--author",
        action="append",
        required=True,
        help="Author as 'First Last'; repeatable",
    )
    import_parser.add_argument("--item-type", type=str, required=True)
    import_parser.add_argument("--year", type=int, default=None)
    import_parser.add_argument("--url", type=str, default=None)
    import_parser.add_argument("--doi", type=str, default=None)
    import_parser.add_argument("--arxiv-id", type=str, default=None)
    import_parser.add_argument("--abstract", type=str, default=None)
    import_parser.add_argument("--publication", type=str, default=None)
    import_parser.add_argument("--volume", type=str, default=None)
    import_parser.add_argument("--issue", type=str, default=None)
    import_parser.add_argument("--pages", type=str, default=None)
    import_parser.add_argument("--language", type=str, default=None)
    import_parser.add_argument("--isbn", type=str, default=None)
    import_parser.set_defaults(func=cmd_import_pdf)

    # arXiv
    arxiv_parser = subparsers.add_parser("arxiv", help="Interact with arXiv papers")
    arxiv_subparsers = arxiv_parser.add_subparsers(dest="arxiv_command", required=True)

    arxiv_fetch = arxiv_subparsers.add_parser("fetch", help="Fetch arXiv metadata")
    arxiv_fetch.add_argument("arxiv_id")
    arxiv_fetch.set_defaults(func=cmd_arxiv_fetch)

    arxiv_pdf = arxiv_subparsers.add_parser("pdf", help="Download the arXiv PDF")
    arxiv_pdf.add_argument("arxiv_id")
    arxiv_pdf.add_argument("--open", action="store_true", help="Open the PDF file")
    arxiv_pdf.set_defaults(func=cmd_arxiv_pdf)

    arxiv_markdown = arxiv_subparsers.add_parser(
        "markdown", help="Convert the arXiv PDF to Markdown"
    )
    arxiv_markdown.add_argument("arxiv_id")
    arxiv_markdown.set_defaults(func=cmd_arxiv_markdown)

    arxiv_source = arxiv_subparsers.add_parser(
        "source", help="Download and extract the arXiv source package"
    )
    arxiv_source.add_argument("arxiv_id")
    arxiv_source.set_defaults(func=cmd_arxiv_source)

    arxiv_save = arxiv_subparsers.add_parser(
        "save", help="Save the arXiv paper to Anchor"
    )
    arxiv_save.add_argument("arxiv_id")
    arxiv_save.add_argument(
        "--no-pdf", action="store_true", help="Save metadata only, without PDF"
    )
    arxiv_save.set_defaults(func=cmd_arxiv_save)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
