# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""CLI helper for accessing papers in Anchor from an AI agent."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


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
    """Convert 'First Last' into an Anchor creator dict.

    The last whitespace-separated token becomes the last name; everything
    before it becomes the first name.
    """
    parts = value.strip().split()
    if len(parts) == 1:
        return {"first_name": "", "last_name": parts[0]}
    return {"first_name": " ".join(parts[:-1]), "last_name": parts[-1]}


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchor papers access helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
