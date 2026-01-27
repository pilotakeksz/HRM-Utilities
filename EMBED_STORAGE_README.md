# Embed Storage System

This system provides persistent storage for Discord embeds across bot restarts, allowing recovery of embed JSON from message IDs.

## Features

- **Automatic Storage**: Bot restart embeds are automatically stored when sent to the version channel
- **Recovery**: Retrieve embed JSON from any stored message ID
- **Listing**: View recent stored embeds with metadata
- **Cleanup**: Automatic removal of old embeds

## Storage Location

All embed data is stored in: `data/embeds_db.json`

Each entry contains:
- `message_id`: Discord message ID
- `channel_id`: Discord channel ID where sent
- `timestamp`: ISO format timestamp when stored
- `description`: Human-readable description (e.g., "Bot Restart v1.2.3")
- `embed_data`: Full embed dict
- `embed_json`: Pretty-printed JSON string for recovery

## Commands (Owner Only)

### Get Embed JSON from Message ID
```
!embed_from_message <message_id>
```
Retrieves and displays the embed JSON for a given message ID. Automatically formats large responses into chunks.

### List Recent Embeds
```
!list_embeds [limit]
```
Shows recent stored embeds with their message IDs, channels, timestamps, and descriptions.
- Default limit: 10
- Maximum limit: 50

### Clear Old Embeds
```
!clear_old_embeds [days]
```
Removes embeds older than the specified number of days.
- Default: 30 days
- Minimum: 1 day

## Python API

```python
from embed_storage import (
    store_embed,
    get_embed_by_message_id,
    get_embed_json_by_message_id,
    list_recent_embeds,
    clear_old_embeds
)

# Store an embed
store_embed(
    message_id=123456789,
    channel_id=987654321,
    embed_data=embed_dict,
    embed_json=json.dumps(embed_dict, indent=2),
    description="My Embed"
)

# Retrieve embed JSON string
json_str = get_embed_json_by_message_id(123456789)

# Get full entry with metadata
entry = get_embed_by_message_id(123456789)

# List recent embeds
recent = list_recent_embeds(limit=10)

# Clear old embeds
removed = clear_old_embeds(days=30)
```

## Integration

The bot automatically:
1. Stores embeds when they're sent to the version channel on restart
2. Stores both main and fallback embeds if needed
3. Persists all data to `data/embeds_db.json`

You can extend this system to store any embeds by calling `store_embed()` with appropriate parameters.
