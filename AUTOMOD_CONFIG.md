# Automod System Configuration Guide

This document explains how to configure and use the advanced moderation system in `beta_cogs/automod.py`.

## Overview

The automod system provides four levels of automated moderation actions:

1. **Infraction** - Lowest severity. Records an infraction in the database. For personnel members only.
2. **Mute** - Timeouts user for a configurable duration (default 30 minutes). For personnel members only.
3. **Quarantine** - Removes all roles except those specified, adds quarantine role, and times out member. For personnel members only.
4. **Ban** - Highest severity. Automatically bans the member from the guild. For personnel members only.

## Key IDs Used

```python
LOG_CHANNEL_ID = 1329910577375482068          # Where moderation embeds are posted
ADMIN_ROLE_ID = 1355842403134603275           # Can issue commands via reply
PERSONNEL_ROLE_ID = 1329910329701830686       # Only these members trigger actions
QUARANTINE_ROLE_ID = 1432834406791254058      # Applied when quarantining
```

## Configurable Regex Patterns

Edit the PATTERN lists at the top of `beta_cogs/automod.py`:

```python
# INFRACTION patterns - lowest severity
INFRACTION_PATTERNS = []

# MUTE patterns - timeout for MUTE_DURATION_MINUTES
MUTE_PATTERNS = []

# QUARANTINE patterns - remove roles + timeout
QUARANTINE_PATTERNS = [
    r"\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+[a-z0-9$#@!*+_-]*\b",
    r"\b[n]+[\W_]*[i1!l|]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[ea4r3]*[a-z0-9]*\b",
    r"\b[n][i|1|!][g|9]{2,}[e|3]r\b",
    r"\b[n][!|1][g|9]{2,}[a|@]\b",
]

# BAN patterns - highest severity, auto-ban
BAN_PATTERNS = [
    r"\b[fph@][\W_]*[u*o0v]+[\W_]*[c(kq)(ck)*x]+[\W_]*[kq]+(ing|er|ed|s|in'?|a)?\b",
    r"\b[fF]+[uU*0]+[cC*k]+[kK]+(ing|er|ed|s)?\b",
    # ... more patterns
]
```

## Action Durations

```python
MUTE_DURATION_MINUTES = 30           # How long to timeout on mute
QUARANTINE_DURATION_SECONDS = 172800 # 2 days in seconds
```

## Detection Thresholds

```python
INFRACT_THRESHOLD = 1    # How many matches to trigger infraction
MUTE_THRESHOLD = 1       # How many matches to trigger mute
QUARANTINE_THRESHOLD = 1 # How many matches to trigger quarantine
BAN_THRESHOLD = 1        # How many matches to trigger ban
```

## Important: Personnel-Only Restriction

**All moderation actions (infraction, mute, quarantine, ban) are ONLY applied to members who have the PERSONNEL_ROLE_ID (1329910329701830686).**

Non-personnel members will:
- Have their message deleted if it matches
- NOT receive any moderation action
- Be logged as skipped in the logs

## Features

### 1. Message Context Capture
When a violation is detected, the system captures:
- Up to 3 messages before the offending message
- The offending message itself
- Context is highlighted with `**word**` formatting
- Context is stored as base64-encoded JSON for audit trail

### 2. Admin Reply-to-Message Trigger
Admins (with ADMIN_ROLE_ID) can:
1. Reply to any message
2. Mention the bot
3. Include an action word:
   - `warn` / `infraction` / `strike` → Issues warning
   - `mute` → Mutes user
   - `quarantine` → Quarantines user
   - `ban` → Bans user

Example:
```
[Reply to offending message]
@bot warn This is unacceptable
```

### 3. Moderation Logging
All actions are logged to:
- **Log Channel** (via embeds with buttons)
- **logs/automod_protection.log** (text file)
- **logs/automod_actions.log** (base64-encoded JSON)
- **data/moderation_tracking.json** (user action history)

### 4. Undo & Block Word Buttons
Each moderation log embed includes two buttons:

- **↩️ Undo Action**: Reverses the action
  - Ban → Unban
  - Quarantine → Restore roles
  - Mute → Remove timeout
  - Infraction → Mark voided in DB

- **🚫 Block This Word**: Prevents future detection of that word
  - Stored in `data/blocked_words.json`
  - Word will be skipped in future detection

### 5. Moderation History Command
```
/moderation-history @user
```
Shows last 10 moderation actions for a user (admin only).

## Data Files

The system creates/uses these files:

```
data/
├── infractions.db                 # Infraction database (from infract.py)
├── quarantine_data.json           # Current quarantined users
├── moderation_tracking.json       # All moderation actions by user
├── blocked_words.json             # Words to skip detection for
└── automod_tracking.json          # Legacy tracking (may be deprecated)

logs/
├── automod_protection.log         # Main automod log file
└── automod_actions.log            # Base64-encoded action log
```

## Bypass Lists

Users/roles that bypass automod:

```python
automodbypass = [
    911072161349918720,  # User ID
    840949634071658507,  # User ID
    735167992966676530,  # User ID
]

bypassrole = 1329910230066401361  # Role ID that bypasses
```

## Workflow Examples

### Example 1: User Violates with Ban-Level Word
1. Personnel member sends message with banned word
2. Message is deleted
3. User is automatically banned
4. Ban embed posted to log channel with:
   - Undo button
   - Block Word button
   - Message context shown

### Example 2: Admin Issues Manual Action
1. Admin sees problematic message
2. Replies to message: `@bot ban`
3. User is banned
4. Same embed posted as above

### Example 3: Admin Undoes Action
1. Clicks "↩️ Undo Action" button
2. User is unbanned
3. Undo action is logged to tracking

### Example 4: Admin Blocks Word
1. Clicks "🚫 Block This Word" button
2. Word is added to blocked_words.json
3. That word will never trigger automod again

## Integration with Existing Cogs

- **infract.py**: Infractions stored in same database
- **quarantine.py**: Uses same quarantine role and restoration logic
- Share same moderation log channel

## Troubleshooting

**Issue**: Actions not triggering for someone
- Check if they have PERSONNEL_ROLE_ID
- Check if they're in bypass list
- Check if word is in blocked_words.json

**Issue**: Undo not working
- Ensure admin/original moderator clicking button
- Check logs for error messages

**Issue**: Patterns not matching**
- Test regex against expected text
- Remember patterns are case-INSENSITIVE
- Check exact regex syntax

## Next Steps

1. Review and customize regex patterns for each action level
2. Test in a sandbox channel first
3. Set appropriate thresholds
4. Train moderation team on admin trigger syntax
5. Monitor moderation_tracking.json for action history

