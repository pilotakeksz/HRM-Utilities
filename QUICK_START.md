# Automod System - Quick Start

## What's Been Implemented

✅ **Automatic Infractions** - Lowest severity moderation
✅ **Automatic Mute** - Timeout enforcement (30 min default)
✅ **Automatic Quarantine** - Role removal + timeout (2 days default)
✅ **Automatic Ban** - Immediate guild ban
✅ **Moderation Tracking** - Complete history in `data/moderation_tracking.json`
✅ **Personnel-Only** - Only affects users with role 1329910329701830686
✅ **Message Context** - 3 preceding messages captured + highlighted
✅ **Admin Reply Trigger** - Reply to message + mention bot + action
✅ **Undo Buttons** - Reverse any action from log channel
✅ **Block Word Buttons** - Prevent future word detection
✅ **Regex Patterns** - Your patterns implemented with IGNORECASE

## Next: Add Your Regex Patterns

Edit `/beta_cogs/automod.py` lines 30-62 and add your patterns to each list:

```python
# INFRACTION patterns - lowest severity, just logs an infraction
INFRACTION_PATTERNS = [
    # Add patterns here that should only issue warnings
]

# MUTE patterns - timeout user for mute_duration
MUTE_PATTERNS = [
    # Add patterns here that should timeout users
]

# QUARANTINE patterns - removes roles, adds quarantine role
QUARANTINE_PATTERNS = [
    r"\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+[a-z0-9$#@!*+_-]*\b",
    r"\b[n]+[\W_]*[i1!l|]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[ea4r3]*[a-z0-9]*\b",
    r"\b[n][i|1|!][g|9]{2,}[e|3]r\b",
    r"\b[n][!|1][g|9]{2,}[a|@]\b",
]

# BAN patterns - highest severity, automatic ban
BAN_PATTERNS = [
    r"\b[fph@][\W_]*[u*o0v]+[\W_]*[c(kq)(ck)*x]+[\W_]*[kq]+(ing|er|ed|s|in'?|a)?\b",
    r"\b[fF]+[uU*0]+[cC*k]+[kK]+(ing|er|ed|s)?\b",
    r"\b[fFph@]+[\W_]*[uU*0]+[\W_]*[cCckkqx]+[\W_]*[kKqx]+(ing|er|ed|s)?\b",
    r"\b(f+|ph)(y|i|u)?(c+|k+|q+)(y|k|n)?\b",
    r"\b(f+|ph)([a*u*y*i]*)(c+|k+|q+|z+|w+|\*+)([u*c*k*q*z*w]*)(k+|c+|\*)(e+r+|i+n+g+|e+d+)?\b",
    r"\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+s*\b",
]
```

## Customizable Settings

All at the top of `beta_cogs/automod.py`:

```python
MUTE_DURATION_MINUTES = 30           # How long to timeout (~line 65)
QUARANTINE_DURATION_SECONDS = 172800 # 2 days (~line 66)

# Thresholds (how many matches to trigger action)
INFRACT_THRESHOLD = 1                # (~line 69)
MUTE_THRESHOLD = 1                   # (~line 70)
QUARANTINE_THRESHOLD = 1             # (~line 71)
BAN_THRESHOLD = 1                    # (~line 72)

# Important role/channel IDs (~lines 83-86)
LOG_CHANNEL_ID = 1329910577375482068
ADMIN_ROLE_ID = 1355842403134603275
PERSONNEL_ROLE_ID = 1329910329701830686
QUARANTINE_ROLE_ID = 1432834406791254058
```

## How It Works

### Automated Detection
1. User with PERSONNEL_ROLE posts message
2. System checks against all regex patterns (INFRACTION, MUTE, QUARANTINE, BAN)
3. Message is deleted
4. **Highest severity** action triggers (Ban > Quarantine > Mute > Infraction)
   - If word matches BAN patterns → Ban (and stop)
   - Else if word matches QUARANTINE → Quarantine (and stop)
   - Else if word matches MUTE → Mute (continue checking)
   - Else if word matches INFRACTION → Infraction (continue)

### Admin Manual Action
1. Admin replies to message
2. Admin mentions the bot
3. Admin includes action keyword:
   - `warn`, `infraction`, `strike` → Warning
   - `mute` → Timeout
   - `quarantine` → Remove roles + timeout
   - `ban` → Ban

## Log Channel Info

All moderation actions post to LOG_CHANNEL_ID with:
- **Title**: Infraction/Mute/Quarantine/Ban
- **User**: Who was actioned
- **Reason**: Why (matched words/admin command)
- **Matched Words**: Highlighted in bold
- **Message Context**: 3 previous messages shown
- **↩️ Undo Button**: Reverse the action
- **🚫 Block Word**: Never detect this word again

## Data Files Created

```
data/
├── blocked_words.json         ← Words to never flag again
└── moderation_tracking.json   ← All user action history
```

## Important Limitations

⚠️ **Only affects PERSONNEL members** (role 1329910329701830686)
- Non-personnel messages deleted but no moderation applied
- This is by design - only actual personnel cause infractions

⚠️ **No double-penalty**
- Higher severity action overrides lower severity
- Highest threshold met = action taken

## Testing

1. Create a test channel
2. Post with one of your ban patterns (if personnel role)
3. Check that:
   - Message deleted ✓
   - User banned ✓
   - Embed posted to log channel ✓
   - Undo/Block buttons appear ✓
   - Moderator can click undo ✓

## Files Modified/Created

- `beta_cogs/automod.py` - Main system (replaced/updated)
- `data/blocked_words.json` - Created
- `data/moderation_tracking.json` - Created
- `AUTOMOD_CONFIG.md` - Full documentation
- `QUICK_START.md` - This file

## Support Commands

After adding patterns, these slash commands are available:

```
/moderation-history @user
```

Shows last 10 moderation actions for that user (admin only).

---

**Ready to deploy!** Just add your patterns and reload the cog.

