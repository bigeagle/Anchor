---
name: anchor-papers
description: Access and import papers stored in the local Anchor reference manager. Use when the user asks AI to list, read, search, summarize, cite, download, or save papers stored in Anchor. Connects through Anchor's local HTTP API, supports listing items, reading bibliographic metadata, listing attachments, downloading PDFs, extracting text for analysis, and importing PDFs as new items.
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

- `GET /api/v1/items?skip=&limit=&q=` — list items, optional title substring filter `q`
- `GET /api/v1/items/{item_id}` — full item with embedded attachments

Attachments:

- `GET /api/v1/items/{item_id}/attachments` — list attachments
- `GET /api/v1/attachments/{attachment_id}` — download file bytes (also returns metadata headers)
- `GET /api/v1/attachments/{attachment_id}/markdown` — Markdown/text extraction

`ItemOut` fields: `id`, `title`, `item_type`, `authors`, `abstract`, `publication`, `volume`, `issue`, `pages`, `year`, `doi`, `arxiv_id`, `isbn`, `url`, `language`, `extra`, `date_added`, `date_modified`, `attachments`.

`AttachmentOut` fields: `id`, `item_id`, `filename`, `content_type`, `size`, `storage_path`, `date_added`, `href`.

## Helper script

Use `scripts/anchor_papers.py` to call the API and extract PDF text.

```bash
uv run scripts/anchor_papers.py list --limit 20 --query "machine learning"
uv run scripts/anchor_papers.py get <item-id>
uv run scripts/anchor_papers.py attachments <item-id>
uv run scripts/anchor_papers.py download <attachment-id> ./paper.pdf
uv run scripts/anchor_papers.py text <attachment-id>
uv run scripts/anchor_papers.py import-pdf ./paper.pdf --title "Paper Title"
```

The `text` command returns the attachment as Markdown via Anchor's `/attachments/{id}/markdown` endpoint. It works for PDFs and other supported formats.

The `import-pdf` command creates a new item and uploads the PDF as its attachment.

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
