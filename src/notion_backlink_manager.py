"""
Live edit/delete for Notion backlinks, using the platform_post_id (Notion
page_id) that NotionAdapter._log_backlink already captures.

Notion API CAN edit/archive a page - this is different from Contra, which
has no such API (see the note in adapters.ContraAdapter's docstring).
Kept as a separate module on purpose: NotionAdapter itself (the working
auto-posting adapter) is untouched.
"""
import logging
import requests
import config

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"


def _headers():
    creds = config.get_credentials()["notion"]
    return {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def edit_live_notion_page(page_id: str, new_content: str) -> dict:
    """
    Replaces the page's block content with new_content (plain text,
    one paragraph block). Title/properties are left as-is - only the
    body changes, matching what the dashboard's inline edit box controls.
    """
    if not page_id:
        return {"status": "failed", "detail": "No page_id on this record - can't edit live (was it posted before this feature existed?)."}

    try:
        # 1. Get existing children blocks so we can delete them
        list_res = requests.get(f"{NOTION_API_BASE}/blocks/{page_id}/children", headers=_headers(), timeout=15)
        if list_res.status_code != 200:
            return {"status": "failed", "detail": f"Could not read existing page blocks: {list_res.text}"}

        for block in list_res.json().get("results", []):
            requests.delete(f"{NOTION_API_BASE}/blocks/{block['id']}", headers=_headers(), timeout=15)

        # 2. Append new content as a single paragraph block (kept simple/robust;
        # full markdown block conversion isn't needed for a quick edit)
        payload = {
            "children": [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": new_content[:2000]}}]}
            }]
        }
        append_res = requests.patch(f"{NOTION_API_BASE}/blocks/{page_id}/children", headers=_headers(), json=payload, timeout=15)
        if append_res.status_code == 200:
            return {"status": "success", "detail": "Live Notion page content updated."}
        return {"status": "failed", "detail": f"Could not write new content: {append_res.text}"}

    except Exception as e:
        logger.error(f"[NotionEdit] Failed: {e}")
        return {"status": "failed", "detail": str(e)}


def delete_live_notion_page(page_id: str) -> dict:
    """
    Archives (soft-deletes) the live Notion page. Notion has no hard-delete
    via API - archived pages move to Trash and can be restored manually
    if needed, which is safer than an irreversible delete anyway.
    """
    if not page_id:
        return {"status": "failed", "detail": "No page_id on this record - can't delete live."}

    try:
        res = requests.patch(f"{NOTION_API_BASE}/pages/{page_id}", headers=_headers(), json={"archived": True}, timeout=15)
        if res.status_code == 200:
            return {"status": "success", "detail": "Live Notion page archived (moved to Trash)."}
        return {"status": "failed", "detail": f"Could not archive page: {res.text}"}
    except Exception as e:
        logger.error(f"[NotionDelete] Failed: {e}")
        return {"status": "failed", "detail": str(e)}