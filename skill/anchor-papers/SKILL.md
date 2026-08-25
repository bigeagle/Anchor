---
name: anchor-papers
description: Access, import, and fetch papers for the local Anchor reference manager. Use when the user asks AI to list, read, search, summarize, cite, download, save, or import papers stored in Anchor, or to fetch arXiv papers (metadata, PDF, Markdown, source) and save them into Anchor. Connects through Anchor's local HTTP API and the arXiv API.
---

# anchor-papers

Access the Anchor reference manager from an AI agent to read papers and their metadata.

## When to use

Use this skill for requests like:

- "List my papers about ..."
- "Summarize the paper titled ..."
- "What attachments does item <id> have?"
- "Download the PDF for ..."
- "Extract text from the PDF of ..."

## Configuration

Set environment variables before running the helper script:

- `ANCHOR_API_URL` — base URL of the Anchor public API. Default: `http://127.0.0.1:23119/api/v1`
- `ANCHOR_API_TOKEN` — Bearer token for Phase 4 authentication. Current phases do not require it.

## Anchor API cheat sheet

Items:

- `GET /api/v1/items/?skip=&limit=&q=` — list items, optional title substring filter `q`. Prefer the trailing slash; current backends accept both forms, but older ones return the SPA HTML page (not JSON) for `/api/v1/items` without it — same for `/api/v1/search/`.
- `GET /api/v1/items/{item_id}` — full item with embedded attachments
- `POST /api/v1/items/with-attachment` — atomically create an item plus its first file: multipart form with a `metadata` field (JSON item payload) and a `file` field. Returns `201` with the item, or `409` with `detail.existing_item_id` / `existing_item_title` / `existing_attachment_id` if the same file already exists — in that case nothing is written, so report the existing item instead of retrying.

**Prefer `with-attachment` whenever you create an item together with a file** (importing a PDF, saving an arXiv paper). The two-step alternative (`POST /items` then `POST /items/{id}/attachments`) can leave an orphan item behind when the upload turns out to be a duplicate.

Attachments:

- `GET /api/v1/items/{item_id}/attachments` — list attachments
- `POST /api/v1/items/{item_id}/attachments` — add a file to an existing item; idempotent: re-uploading identical content returns `200` with the existing attachment
- `GET /api/v1/attachments/{attachment_id}` — download file bytes (also returns metadata headers)
- `GET /api/v1/attachments/{attachment_id}/markdown` — Markdown/text extraction

`ItemOut` fields: `id`, `title`, `item_type`, `authors`, `abstract`, `publication`, `volume`, `issue`, `pages`, `year`, `doi`, `arxiv_id`, `isbn`, `url`, `language`, `extra`, `date_added`, `date_modified`, `attachments`.

`AttachmentOut` fields: `id`, `item_id`, `filename`, `content_type`, `size`, `storage_path`, `date_added`, `href`.

## Helper script

Use `scripts/anchor_papers.py` to call the API and extract PDF text.
The script path is relative to the directory of current skill file.

```bash
uv run scripts/anchor_papers.py list --limit 20 --query "machine learning"
uv run scripts/anchor_papers.py search "attention transformer"
uv run scripts/anchor_papers.py get <item-id>
uv run scripts/anchor_papers.py attachments <item-id>
uv run scripts/anchor_papers.py download <attachment-id> ./paper.pdf
uv run scripts/anchor_papers.py text <attachment-id>
uv run scripts/anchor_papers.py import-pdf ./paper.pdf --title "Paper Title"
```

`search` uses `GET /api/v1/search/?q=...` and matches titles, abstracts, authors, identifiers, publication, and other item fields.

The `text` command returns the attachment as Markdown via Anchor's `/attachments/{id}/markdown` endpoint. It works for PDFs and other supported formats.

## arXiv commands

```bash
uv run scripts/anchor_papers.py arxiv fetch 1706.03762
uv run scripts/anchor_papers.py arxiv pdf 1706.03762
uv run scripts/anchor_papers.py arxiv markdown 1706.03762
uv run scripts/anchor_papers.py arxiv source 1706.03762
uv run scripts/anchor_papers.py arxiv check 1706.03762
uv run scripts/anchor_papers.py arxiv save 1706.03762
```

- `fetch` — fetch and print arXiv metadata (title, authors, abstract, year, categories, PDF URL).
- `pdf` — download the PDF to a local cache and print the path. Use `--open` to open it on macOS.
- `markdown` — convert the arXiv PDF to Markdown and print it.
- `source` — download and extract the TeX source package, print the directory and file list.
- `check` — search Anchor for this arXiv ID and report whether it is already saved.
- `save` — create an Anchor item from the arXiv metadata and upload the PDF (unless `--no-pdf`) via the atomic `with-attachment` endpoint. `save` also uses `check` to avoid duplicates; if the server still reports a duplicate (409), it prints `status: exists` with the existing item's info.

Cache is stored under `~/.cache/anchor-papers/arxiv/`.

## Import local PDF

The `import-pdf` command creates a new item and uploads the PDF as its attachment in one atomic `with-attachment` call. If the same file already exists under an identical item, nothing is written and the command prints `status: exists` with the existing item's info.

```bash
uv run scripts/anchor_papers.py import-pdf ./paper.pdf \
  --title "Attention Is All You Need" \
  --author "Ashish Vaswani" \
  --author "Noam Shazeer" \
  --item-type journalArticle \
  --year 2017 \
  --url "https://arxiv.org/abs/1706.03762" \
  --doi "10.48550/arXiv.1706.03762" \
  --abstract "We propose the Transformer..."
```

Required flags: `--title`, `-a/--author` (repeatable), `--item-type`.

Optional metadata flags: `--year`, `--url`, `--doi`, `--arxiv-id`, `--abstract`, `--publication`, `--volume`, `--issue`, `--pages`, `--language`, `--isbn`.

## Workflow

1. If the user mentions a title or topic, call `list` with `--query`.
2. Identify the target item and call `get` or `attachments` for details.
3. To read the paper, call `download` or `text`.
4. Return concise answers with citations; include Anchor item/attachment IDs so the user can verify.
