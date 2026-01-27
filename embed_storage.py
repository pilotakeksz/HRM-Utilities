"""
Persistent storage for embed data across restarts.
Allows recovery of embed JSON from message IDs.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any


EMBEDS_DB_FILE = os.path.join("data", "embeds_db.json")


def ensure_db_dir():
    """Ensure data directory exists."""
    os.makedirs(os.path.dirname(EMBEDS_DB_FILE), exist_ok=True)


def load_embeds_db() -> Dict[str, Any]:
    """Load the embeds database."""
    ensure_db_dir()
    if os.path.exists(EMBEDS_DB_FILE):
        try:
            with open(EMBEDS_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load embeds database: {e}")
            return {"embeds": {}}
    return {"embeds": {}}


def save_embeds_db(db: Dict[str, Any]):
    """Save the embeds database."""
    ensure_db_dir()
    try:
        with open(EMBEDS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save embeds database: {e}")


def store_embed(message_id: int, channel_id: int, embed_data: Dict[str, Any], embed_json: str, description: str = ""):
    """
    Store an embed with its message ID for later recovery.
    
    Args:
        message_id: Discord message ID
        channel_id: Discord channel ID where message was sent
        embed_data: The embed data dict (for quick reference)
        embed_json: The full embed JSON as string (for recovery)
        description: Optional description of the embed (e.g., "Bot Restart v1.2.3")
    """
    db = load_embeds_db()
    
    entry = {
        "message_id": message_id,
        "channel_id": channel_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "embed_json": embed_json,
        "embed_data": embed_data,
    }
    
    db["embeds"][str(message_id)] = entry
    save_embeds_db(db)
    print(f"Stored embed for message {message_id}")


def get_embed_by_message_id(message_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve stored embed data by message ID.
    
    Returns the full entry with embed_json and metadata.
    """
    db = load_embeds_db()
    return db["embeds"].get(str(message_id))


def get_embed_json_by_message_id(message_id: int) -> Optional[str]:
    """
    Retrieve just the embed JSON string by message ID.
    """
    entry = get_embed_by_message_id(message_id)
    if entry:
        return entry.get("embed_json")
    return None


def list_recent_embeds(limit: int = 10) -> list:
    """List recent embeds stored."""
    db = load_embeds_db()
    embeds = list(db["embeds"].values())
    # Sort by timestamp descending (newest first)
    embeds.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return embeds[:limit]


def clear_old_embeds(days: int = 30):
    """Clear embeds older than specified days."""
    from datetime import timedelta
    
    db = load_embeds_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    
    original_count = len(db["embeds"])
    db["embeds"] = {
        mid: entry
        for mid, entry in db["embeds"].items()
        if entry.get("timestamp", "") > cutoff_str
    }
    removed = original_count - len(db["embeds"])
    
    if removed > 0:
        save_embeds_db(db)
        print(f"Cleared {removed} embeds older than {days} days")
    
    return removed
