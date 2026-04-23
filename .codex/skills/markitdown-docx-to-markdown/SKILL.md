---
name: markitdown-docx-to-markdown
description: Use when converting Word documents (.docx/.doc) to Markdown while preserving hyperlinks and citation URLs.
---

# MarkItDown DOCX to Markdown

## Overview
Convert Office documents to Markdown with link targets preserved.
Prefer an existing MarkItDown MCP integration when available; otherwise use local CLI fallback.

## Quick Steps
1. Check whether MarkItDown MCP resources are available.
2. If MCP is unavailable, create a local virtual environment and install dependencies:
   `python3 -m venv .venv && . .venv/bin/activate && pip install "markitdown[docx]"`
3. Convert the file:
   `markitdown "input.docx" -o "output.md"`
4. Verify links in output:
   `rg -n "https?://|\[[^]]+\]\([^\)]+\)" "output.md"`

## Notes
- If conversion fails with `MissingDependencyException` for `.docx`, install extra dependencies using `markitdown[docx]`.
- If `code --install-extension ...` is unavailable, use the Python package fallback.
- Keep quoted paths for filenames with spaces or Unicode characters.
