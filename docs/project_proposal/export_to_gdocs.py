"""
export_to_gdocs.py — Export Project_Proposal.md to a Google Doc
Uses ONLY the Google Docs API (scope: documents).

Markdown tables → real Google Docs tables.
Images: omitted (insert manually from diagrams/ folder).

Setup:
1. Google Cloud Console → Enable "Google Docs API"
2. Create OAuth 2.0 credentials (Desktop App) → download as credentials.json
3. Place credentials.json next to this script
4. pip install google-auth google-auth-oauthlib google-api-python-client
5. python export_to_gdocs.py
"""

import os
import re
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/documents"]
PROPOSAL_PATH = Path(__file__).parent / "Project_Proposal.md"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_PATH = Path(__file__).parent / "token.json"


# ─── Auth ─────────────────────────────────────────────────────────────────────

def authenticate():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}\n"
                    "Download from: Google Cloud Console → APIs → Credentials → OAuth 2.0 Client IDs"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


# ─── Markdown Parser ──────────────────────────────────────────────────────────

def clean_inline(text: str) -> str:
    """Strip inline markdown: bold, italic, code, links."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.strip()


def parse_blocks(md_text: str) -> list[dict]:
    """
    Parse markdown into ordered blocks:
    {"type": "h1"|"h2"|"h3"|"body"|"bullet"|"numbered"|"blank"|"table", ...}
    Tables have a "rows" key: list[list[str]]
    """
    lines = md_text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Headings
        if line.startswith("### "):
            blocks.append({"type": "h3", "text": clean_inline(line[4:])})
            i += 1
        elif line.startswith("## "):
            blocks.append({"type": "h2", "text": clean_inline(line[3:])})
            i += 1
        elif line.startswith("# "):
            blocks.append({"type": "h1", "text": clean_inline(line[2:])})
            i += 1

        # Code fences (skip entirely)
        elif line.strip().startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1  # closing fence

        # Image lines (skip)
        elif line.strip().startswith("!["):
            i += 1

        # Horizontal rules / blank
        elif line.strip() in ("", "---"):
            blocks.append({"type": "blank"})
            i += 1

        # Tables
        elif line.startswith("|"):
            raw_rows = []
            while i < len(lines) and lines[i].startswith("|"):
                raw_rows.append(lines[i])
                i += 1
            rows = []
            for row_line in raw_rows:
                # Skip separator lines like |---|---|
                if re.match(r"^\|[-| :]+\|$", row_line.strip()):
                    continue
                cells = [clean_inline(c) for c in row_line.strip("|").split("|")]
                rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})

        # Bullet lists
        elif re.match(r"^[-*] ", line):
            blocks.append({"type": "bullet", "text": clean_inline(line[2:])})
            i += 1

        # Numbered lists
        elif re.match(r"^\d+\. ", line):
            blocks.append({"type": "numbered", "text": clean_inline(re.sub(r"^\d+\. ", "", line))})
            i += 1

        # Body text
        else:
            text = clean_inline(line)
            if text:
                blocks.append({"type": "body", "text": text})
            i += 1

    return blocks


# ─── Phase 1: Insert text with table placeholders ─────────────────────────────

PLACEHOLDER_PREFIX = "__VACAY_TABLE_"

def build_text_requests(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Build batchUpdate requests to insert all non-table content.
    Returns (requests, tables_in_order).
    Tables are replaced by a unique placeholder line.
    """
    requests = []
    tables = []      # list of table block dicts, in order
    cursor = 1       # Google Docs content starts at index 1

    HEADING_STYLE = {"h1": "HEADING_1", "h2": "HEADING_2", "h3": "HEADING_3"}

    # Collapse consecutive blanks
    cleaned = []
    prev_blank = False
    for b in blocks:
        if b["type"] == "blank":
            if not prev_blank:
                cleaned.append(b)
            prev_blank = True
        else:
            cleaned.append(b)
            prev_blank = False

    for block in cleaned:
        btype = block["type"]

        if btype == "table":
            n = len(tables)
            tables.append(block)
            placeholder = f"{PLACEHOLDER_PREFIX}{n}__\n"
            requests.append({"insertText": {"location": {"index": cursor}, "text": placeholder}})
            cursor += len(placeholder)

        elif btype == "blank":
            requests.append({"insertText": {"location": {"index": cursor}, "text": "\n"}})
            cursor += 1

        elif btype in HEADING_STYLE:
            text = block["text"] + "\n"
            requests.append({"insertText": {"location": {"index": cursor}, "text": text}})
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": cursor, "endIndex": cursor + len(text)},
                    "paragraphStyle": {"namedStyleType": HEADING_STYLE[btype]},
                    "fields": "namedStyleType",
                }
            })
            cursor += len(text)

        elif btype == "bullet":
            text = block["text"] + "\n"
            requests.append({"insertText": {"location": {"index": cursor}, "text": text}})
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": cursor, "endIndex": cursor + len(text)},
                    "paragraphStyle": {
                        "namedStyleType": "NORMAL_TEXT",
                        "indentFirstLine": {"magnitude": 18, "unit": "PT"},
                        "indentStart": {"magnitude": 36, "unit": "PT"},
                        "spaceAbove": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "namedStyleType,indentFirstLine,indentStart,spaceAbove",
                }
            })
            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": cursor, "endIndex": cursor + len(text)},
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }
            })
            cursor += len(text)

        elif btype == "numbered":
            text = block["text"] + "\n"
            requests.append({"insertText": {"location": {"index": cursor}, "text": text}})
            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": cursor, "endIndex": cursor + len(text)},
                    "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN",
                }
            })
            cursor += len(text)

        else:  # body
            text = block.get("text", "") + "\n"
            requests.append({"insertText": {"location": {"index": cursor}, "text": text}})
            cursor += len(text)

    return requests, tables


# ─── Phase 2: Replace placeholders with real tables ───────────────────────────

def find_placeholder_index(service, doc_id: str, placeholder: str) -> int | None:
    """Read the document and find the start index of a placeholder text."""
    doc = service.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {}).get("content", [])

    def search_content(content):
        for element in content:
            para = element.get("paragraph")
            if para:
                for pr in para.get("elements", []):
                    tr = pr.get("textRun", {})
                    text = tr.get("content", "")
                    if placeholder in text:
                        return pr.get("startIndex", 0) + text.index(placeholder)
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        result = search_content(cell.get("content", []))
                        if result is not None:
                            return result
        return None

    return search_content(body)


def find_table_in_doc(service, doc_id: str, table_start_hint: int) -> dict | None:
    """Find the first table whose startIndex is >= table_start_hint."""
    doc = service.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {}).get("content", [])
    for element in body:
        if "table" in element:
            if element.get("startIndex", -1) >= table_start_hint - 2:
                return element
    return None


def get_cell_index(table_element: dict, row: int, col: int) -> int | None:
    """Return the start index of the first paragraph in a given cell."""
    rows = table_element.get("table", {}).get("tableRows", [])
    if row >= len(rows):
        return None
    cells = rows[row].get("tableCells", [])
    if col >= len(cells):
        return None
    content = cells[col].get("content", [])
    if content:
        return content[0].get("startIndex")
    return None


def style_table_header(service, doc_id: str, table_element: dict):
    """Make the first row bold."""
    rows = table_element.get("table", {}).get("tableRows", [])
    if not rows:
        return
    header_row = rows[0]
    requests = []
    for cell in header_row.get("tableCells", []):
        for para in cell.get("content", []):
            start = para.get("startIndex")
            end = para.get("endIndex")
            if start is not None and end is not None and end > start:
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })
    if requests:
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()


def insert_real_table(service, doc_id: str, table_idx: int, table_block: dict):
    """
    1. Find placeholder text
    2. Delete it
    3. Insert a real table
    4. Fill cells
    5. Bold the header row
    """
    placeholder = f"{PLACEHOLDER_PREFIX}{table_idx}__"
    rows_data = table_block["rows"]
    num_rows = len(rows_data)
    num_cols = max(len(r) for r in rows_data)

    # Pad rows to uniform column count
    rows_data = [r + [""] * (num_cols - len(r)) for r in rows_data]

    # Find placeholder
    idx = find_placeholder_index(service, doc_id, placeholder)
    if idx is None:
        print(f"  ⚠️  Placeholder {placeholder!r} not found — skipping")
        return

    placeholder_full = placeholder + "\n"

    # Delete placeholder + newline
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{
            "deleteContentRange": {
                "range": {
                    "startIndex": idx,
                    "endIndex": idx + len(placeholder_full),
                }
            }
        }]}
    ).execute()

    # Insert table at the same index
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{
            "insertTable": {
                "rows": num_rows,
                "columns": num_cols,
                "location": {"index": idx},
            }
        }]}
    ).execute()

    # Read back to find the table
    table_el = find_table_in_doc(service, doc_id, idx)
    if table_el is None:
        print(f"  ⚠️  Could not find table after insertion at {idx}")
        return

    # Fill cells — process in reverse order so earlier inserts don't shift later indices
    cell_inserts = []
    for r in range(num_rows):
        for c in range(num_cols):
            text = rows_data[r][c]
            if not text:
                continue
            cell_idx = get_cell_index(table_el, r, c)
            if cell_idx is not None:
                cell_inserts.append((cell_idx, text))

    # Sort by index descending so we insert from the end
    cell_inserts.sort(key=lambda x: x[0], reverse=True)

    if cell_inserts:
        fill_requests = [
            {"insertText": {"location": {"index": ci}, "text": ct}}
            for ci, ct in cell_inserts
        ]
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": fill_requests}
        ).execute()

    # Bold the header row
    # Re-read the table since indices changed after cell fill
    table_el = find_table_in_doc(service, doc_id, idx)
    if table_el:
        style_table_header(service, doc_id, table_el)

    print(f"  ✅ Table {table_idx} inserted ({num_rows}×{num_cols})")


# ─── Main ─────────────────────────────────────────────────────────────────────

def export(creds):
    service = build("docs", "v1", credentials=creds)

    print("Creating Google Doc...")
    doc = service.documents().create(body={"title": "VACAY — Project Proposal"}).execute()
    doc_id = doc["documentId"]
    print(f"  Doc ID: {doc_id}")

    print(f"Parsing {PROPOSAL_PATH.name}...")
    md_text = PROPOSAL_PATH.read_text(encoding="utf-8")
    blocks = parse_blocks(md_text)

    print("Phase 1: Inserting text content...")
    text_requests, tables = build_text_requests(blocks)

    # Chunk to stay under API limits
    CHUNK = 200
    for i in range(0, len(text_requests), CHUNK):
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": text_requests[i: i + CHUNK]}
        ).execute()
    print(f"  Text done ({len(tables)} tables to convert)")

    print("Phase 2: Converting table placeholders to real tables...")
    # Process tables in REVERSE order so earlier table deletions don't shift
    # the indices of later placeholders
    for table_idx in reversed(range(len(tables))):
        print(f"  Processing table {table_idx}...")
        insert_real_table(service, doc_id, table_idx, tables[table_idx])

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"\n✅ Done!")
    print(f"   {doc_url}")
    print("\n📌 Images: Insert PNGs manually from docs/project_proposal/diagrams/")
    return doc_url


if __name__ == "__main__":
    creds = authenticate()
    export(creds)
