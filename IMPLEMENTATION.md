# 🚀 Automod System - Implementation Complete

## ✅ What's Been Implemented

### 1. **Automatic Infractions** ✓
- Issues warning-level infractions for personnel members
- Stores in `data/infractions.db` (uses same DB as infract.py)
- Creates entry with UUID tracking
- Logs to infraction channel if configured
- Can be voided via undo button

### 2. **Automatic Mute** ✓  
- Times out user for configurable duration (default 30 minutes)
- Uses Discord's built-in timeout/mute feature
- Only affects personnel members
- Can be reversed via undo button
- Full audit trail maintained

### 3. **Automatic Quarantine** ✓
- Removes all roles and stores them for later restoration
- Adds quarantine role (1432834406791254058)
- Times out user for 2 days (configurable)
- Integrated with existing quarantine.py role restoration
- Can be undone with role restoration

### 4. **Automatic Ban** ✓
- Automatically bans personnel member from guild
- Highest severity action
- Can be reversed via undo button
- Complete audit trail

### 5. **Severity Hierarchy** ✓
When word is detected:
```
Ban pattern detected? → Auto-ban and stop
Else Quarantine pattern? → Auto-quarantine and stop  
Else Mute pattern? → Auto-mute (continue checking)
Else Infraction pattern? → Issue infraction (continue)
```

### 6. **Regex Patterns** ✓
Provided patterns implemented:
- **Quarantine level**: 4 patterns (shi, n-word variations)
- **Ban level**: 6 patterns (f-word variations)
- Configurable lists for Infraction and Mute patterns (empty by default)
- All compiled with IGNORECASE flag
- Case-insensitive matching for variants

### 7. **Personnel-Only Enforcement** ✓
- Only members with role `1329910329701830686` trigger actions
- Non-personnel: message deleted, no infraction
- Prevents false positives on non-staff
- Logged in system for audit

### 8. **Message Context** ✓
For each violation, captures:
- 3 messages **before** the offending message
- The offending message itself
- Author, content, timestamp for each
- Highlighted in markdown with offending word in **bold**
- Base64-encoded JSON for database storage
- Full transparency in logs

### 9. **Admin Reply-to-Message Trigger** ✓
Admin (role 1355842403134603275) can:
1. Reply to ANY message
2. Mention the bot
3. Include action keyword:
   ```
   @bot warn          → Issues warning
   @bot mute          → Mutes user
   @bot quarantine    → Quarantines user
   @bot ban           → Bans user
   ```
Treated as legitimate moderation action with full context capture

### 10. **Moderation Tracking Database** ✓
File: `data/moderation_tracking.json`
Tracks:
- Timestamp
- Action type (infraction/mute/quarantine/ban)
- Target user
- Issued by (moderator)
- Reason
- Matched words
- Can void/undo actions
- Full history per user

### 11. **Undo Button** ✓
Available on all moderation log embeds:
- **Ban** → Unbans user
- **Quarantine** → Restores roles, removes quarantine role
- **Mute** → Removes timeout
- **Infraction** → Marks as voided in database
- Only admin or original moderator can undo
- Action is logged as undo event
- Button disables after use

### 12. **Block Word Button** ✓
Available on all moderation log embeds:
- Extracts flagged word(s) from embed
- Adds to `data/blocked_words.json`
- Word never triggers detection again
- Useful for legitimate words caught by regex
- Only admin can block words
- Button disables after use

### 13. **Logging & Audit Trail** ✓
Multiple logging levels:
- `logs/automod_protection.log` - Text log file
- `logs/automod_actions.log` - Base64-encoded JSON actions
- `data/moderation_tracking.json` - User-centric history
- Log channel embeds with context
- All actions timestamped and traceable

### 14. **Slash Commands** ✓
```
/moderation-history @user
```
- Shows last 10 moderation actions for user
- Admin only
- Sortable by action type

---

## 📋 Configuration Checklist

### Before Deploying (DO THIS)

- [ ] Review regex patterns in `beta_cogs/automod.py` (lines 30-62)
- [ ] Add INFRACTION patterns if desired (currently empty)
- [ ] Add MUTE patterns if desired (currently empty)
- [ ] Verify QUARANTINE patterns match your needs
- [ ] Verify BAN patterns match your needs
- [ ] Adjust durations if needed:
  - [ ] `MUTE_DURATION_MINUTES` (line 65)
  - [ ] `QUARANTINE_DURATION_SECONDS` (line 66)
- [ ] Confirm role IDs are correct:
  - [ ] `LOG_CHANNEL_ID = 1329910577375482068` (line 83)
  - [ ] `ADMIN_ROLE_ID = 1355842403134603275` (line 84)
  - [ ] `PERSONNEL_ROLE_ID = 1329910329701830686` (line 85)
  - [ ] `QUARANTINE_ROLE_ID = 1432834406791254058` (line 86)
- [ ] Test patterns in sandbox channel first
- [ ] Verify infraction DB exists at `data/infractions.db`

### After Deploying

- [ ] Reload the bot cog: `?cog reload beta_cogs.automod`
- [ ] Test with a personnel member in test channel
- [ ] Verify message is deleted
- [ ] Verify embed posted to log channel
- [ ] Verify undo button works
- [ ] Verify block word button works
- [ ] Test admin reply-to-message trigger
- [ ] Monitor `data/moderation_tracking.json` for entries

---

## 🔄 Integration with Existing Systems

### infract.py
- Uses same database: `data/infractions.db`
- Same infraction types and roles
- Infractions issued via automod appear in infract.py queries
- Undo button voids infraction correctly

### quarantine.py
- Uses same quarantine role: `1432834406791254058`
- Uses same quarantine data file: `data/quarantine_data.json`
- Role restoration works seamlessly
- Quarantine timeout integrates with existing system

### bot.py
- Make sure automod cog is loaded: `await bot.load_extension("beta_cogs.automod")`
- Required: `discord.py` with timeout support (v2.0+)

---

## 📊 Data Structure

### Table: infractions (in infractions.db)
```
infraction_id (TEXT) - UUID
user_id (INTEGER) - Target member ID
user_name (TEXT) - Target member name
moderator_id (INTEGER) - Who issued it
moderator_name (TEXT) - Moderator name
action (TEXT) - "Warning", "Strike", "Suspension", etc.
reason (TEXT) - Why it was issued
proof (TEXT) - Base64-encoded context JSON
date (TEXT) - ISO timestamp
message_id (INTEGER) - NULL for automod
voided (INTEGER) - 1 if undo button used
void_reason (TEXT) - Why it was voided
```

### File: data/moderation_tracking.json
```json
{
  "user_id_string": [
    {
      "timestamp": "2026-02-22T...",
      "action": "ban|quarantine|mute|infraction|undo_*",
      "action_id": "uuid",
      "target_id": 123456,
      "target": "Username#1234",
      "moderator_id": 987654,
      "moderator": "ModeratorName#5678",
      "reason": "...",
      "matched_words": ["word1", "word2"],
      "proof_b64": "base64string..."
    }
  ]
}
```

### File: data/blocked_words.json
```json
{
  "blocked_words": [
    "legitimate_false_positive_word",
    "another_blocked_word"
  ]
}
```

---

## 🎯 How It Works - Detailed Flow

### Automated Detection Flow
1. Member posts message
2. Check: Is poster bypassed? (ID or role) → If YES: skip
3. Check: Is poster personnel? → If NO: delete & skip
4. Check: Does message match patterns?
   - INFRACTION patterns?
   - MUTE patterns?
   - QUARANTINE patterns?
   - BAN patterns?
5. For each match: Check if word is blocked → If YES: skip
6. Delete message
7. Apply action based on severity:
   - If BAN match: Ban and stop
   - If QUARANTINE match: Quarantine and stop
   - If MUTE match: Mute (continue checking)
   - If INFRACTION match: Infraction (continue)
8. Post embed to log channel with:
   - Message context (3 prev + culprit)
   - Matched words highlighted
   - Undo button
   - Block Word button
9. Log all to database

### Admin Manual Action Flow
1. Admin replies to message
2. Check: Does message mention bot?
3. Check: Is replier admin?
4. Extract keyword from reply content
5. Fetch original message author
6. Apply action (warn/mute/quarantine/ban)
7. Post same embed as automated
8. Send confirmation reply

---

## ⚠️ Important Notes

1. **Severity Precedence**: Ban > Quarantine > Mute > Infraction
   - If a word matches both BAN and MUTE patterns, BAN wins
   
2. **Personnel Only**: This is intentional
   - Only actual staff members get moderated
   - Non-staff messages deleted silently
   
3. **Threshold System**: Currently set to 1
   - Change `*_THRESHOLD` to require multiple matches
   
4. **Bypass System**: Two levels
   - User ID bypass list
   - Role bypass (anyone with bypassrole)
   
5. **Regex Case-Insensitive**: All patterns use IGNORECASE
   - `ShIt` matches same as `shit`
   - Variants with numbers/symbols covered

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Actions not triggering | Check if user has PERSONNEL_ROLE_ID |
| Message not deleted | Maybe not personnel? Or bypass active? |
| Embed not posting | Check LOG_CHANNEL_ID is correct |
| Undo button error | Check DB permissions, user role |
| Block word not working | Check admin role ID |
| Regex not matching | Test regex on regex101.com |
| Patterns case-sensitive | All use IGNORECASE flag, should match |

---

## 📁 Files Changed

| File | Status | Details |
|------|--------|---------|
| `beta_cogs/automod.py` | ✅ Modified | Complete rewrite with all features |
| `data/blocked_words.json` | ✅ Created | Persistent blocked words list |
| `data/moderation_tracking.json` | ✅ Created | Action history |
| `AUTOMOD_CONFIG.md` | ✅ Created | Full documentation |
| `QUICK_START.md` | ✅ Created | Quick reference |
| `IMPLEMENTATION.md` | ✅ Created | This file |

---

## ✨ Ready to Deploy!

All code is syntax-valid and ready for production. Just:

1. Review the patterns
2. Adjust IDs/durations if needed  
3. Reload the cog
4. Test in a sandbox
5. Deploy!

Questions? Check `AUTOMOD_CONFIG.md` for detailed explanation of each feature.

