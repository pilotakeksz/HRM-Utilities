Here is a detailed documentation of all commands and functions for your HRM Discord bot, including the archive, blacklist, infractions, and other core systems. This is suitable for your README or for posting in your documentation channel.

---

# 🟩 High Rock Military Corps Bot — Full Command & Function Documentation 🟩

---

## 📦 Core Features

- **Persistent Interactive Embeds**: Divisions, About Us, Regulations, and Assistance embeds with dropdowns/buttons that remain functional after bot restarts.
- **Ticket System**: Open tickets for general support or management, with `/ticket-add` and `/ticket-remove` for ticket management.
- **Economy System**: Daily rewards, shop, inventory, and item selling with autocomplete.
- **Leveling System**: XP per message, level roles, and leaderboard.
- **Verification & Welcome**: Verification and welcome messages with role assignment.
- **Applications**: Application system for new members.
- **Suggestion Box**: Submit and manage suggestions.
- **Callsign Management**: Request, view, and manage callsigns with unique number enforcement and admin menu.
- **Infraction System**: Issue, void, view, and list infractions with DM notification, role updates, logging, and paginated user infraction history.
- **Blacklist System**: Issue, void, view, and list blacklists with DM notification, role updates, logging, and paginated user blacklist history.
- **Archive System**: Save, view, and list archive entries with interactive UI and role restrictions.
- **Miscellaneous**: Ping, uptime, and say commands.

---

## 📝 Command Reference

### General Commands

| Command | Description | Permissions |
|---------|-------------|-------------|
| `!divisions` | Sends the persistent divisions embed in the configured channel. | Admin only |
| `!aboutus` | Sends the About Us embed with interactive rank info. | Owner only |
| `!regulations` | Sends the persistent regulations embed in the configured channel. | Owner only |
| `!assistance` | Sends the persistent assistance/ticket embed in the configured channel. | Admin only |
| `!verification` | Sends the verification embed in the configured channel. | Admin only |
| `!inventory` or `/inventory` | Shows your inventory. | All users |
| `/sell` | Sell items from your inventory (autocomplete only shows items you own). | All users |
| `/ticket-add`, `/ticket-remove` | Add or remove users from your ticket (civilians only). | Civilians |
| `!rank`, `!leaderboard` | Leveling and leaderboard commands. | All users |
| `/callsign` or `!callsign` | View or request your callsign. Only one of each number is allowed globally. Admins can add/remove callsigns via the admin menu. | All users / Admins |

---

### 🟧 Archive System

#### Commands

| Command | Description | Who Can Use |
|---------|-------------|-------------|
| `!archive` or `/archive` | Open the archive interface (interactive UI). | All users |
| `!sendtoarchive <YEAR>-<MONTH>-<DAY> <NAME> <TEXT TO ARCHIVE>` | Save a new archive entry. | <@&911072161349918720>, <@&1329910241835352064> |
| `!viewallarchives` or `/archive-viewall` | View all archive entries (date and name). | All users |

#### Archive UI

- **Interactive Browsing**: Use the archive interface to select a date, then a name, to view the archived message.
- **Role Restriction**: Only users with <@&911072161349918720> or <@&1329910241835352064> can save to the archive.
- **Logging**: All actions are logged in `logs/archive_action_log.txt`.

#### Functions

- `has_allowed_role(ctx)`: Checks if the user has an allowed role for archive actions.
- `has_allowed_role_appcmd(interaction)`: Checks if the user has an allowed role for slash command archive actions.
- `log_action(user, action, details)`: Logs archive actions to `logs/archive_action_log.txt`.
- `NameSelect`: UI select for choosing an archive entry by name.
- `NameSelectView`: View for the name select dropdown.
- `DateModal`: Modal for entering a date to view archive entries.
- `ArchiveView`: Persistent view for archive browsing.

---

### 🟥 Blacklist System

#### Commands

| Command | Description | Who Can Use |
|---------|-------------|-------------|
| `/blacklist` | Blacklist a user from HRMC. | High Command |
| `/blacklist-by-id` | Blacklist a user by user ID (not in server). | High Command |
| `/blacklist-void` | Void (remove) a blacklist by its ID. | High Command |
| `/blacklist-view <blacklist_id>` | View all details of a specific blacklist by its ID. | All users (for their own) / High Command |
| `/blacklist-list <user> [page]` | List all blacklists for a user, paginated. | All users (for their own) / High Command |

#### Features

- **DM Notification**: Users are notified in DMs when blacklisted or when a blacklist is voided (if not banned).
- **Role Management**: Blacklisted role is added/removed as appropriate.
- **Logging**: All actions are logged locally and in <#1343686645815181382>.
- **Pagination**: Blacklist history is paginated for easy viewing.

#### Functions

- `add_blacklist(...)`: Adds a blacklist entry to the database.
- `get_blacklist_embed(...)`: Formats a blacklist entry as a Discord embed.
- `log_command_to_txt(...)`: Logs blacklist actions to a text file.

---

### 🟦 Infraction System

#### Commands

| Command | Description | Who Can Use |
|---------|-------------|-------------|
| `/infraction-issue` | Issue an infraction to a user, with DM, role updates, and logging. | High Command |
| `/infraction-void` | Void (remove) an infraction by its ID. | High Command |
| `/infraction-view <infraction_id>` | View all details of a specific infraction by its ID. | All users (for their own) / High Command |
| `/infraction-list <user> [page]` | List all infractions for a user, paginated. | All users (for their own) / High Command |
| `/infraction-log` | View the last 10 non-voided infractions in an embed. | High Command |

#### Features

- **DM Notification**: Users are notified in DMs when infractions are issued or voided.
- **Role Management**: Warning/strike roles are added/removed as appropriate.
- **Logging**: All actions are logged locally and in <#1343686645815181382>.
- **Pagination**: Infraction history is paginated for easy viewing.

#### Functions

- `add_infraction(...)`: Adds an infraction entry to the database.
- `get_infraction_embed(...)`: Formats an infraction entry as a Discord embed.
- `log_command_to_txt(...)`: Logs infraction actions to a text file.

---

### 🟨 Miscellaneous

| Command | Description | Who Can Use |
|---------|-------------|-------------|
| `!ping` | Check bot latency. | All users |
| `!uptime` | Show bot uptime. | All users |
| `!say <message>` | Make the bot say something. | Admin only |

---

## 🗂️ File Structure

- cogs — All bot features are modularized as cogs.
- data — Databases for economy, leveling, callsigns, infractions, and archives.
- logs — Logs for commands, infractions, blacklists, and archives.
- .env — Configuration for all IDs and settings.

---

## 🛠️ Setup

1. **Clone the repository and install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

2. **Configure your .env file:**
    - See the provided .env for all required IDs and settings.
    - Make sure to set your `DISCORD_BOT_TOKEN` and all relevant channel/role IDs.

3. **Run the bot:**
    ```sh
    python bot.py
    ```

---

## 📝 Logging

- All major actions (infractions, blacklists, archives, applications, etc.) are logged to the logs folder.
- Archive actions are logged in `logs/archive_action_log.txt`.
- Blacklist and infraction actions are logged in their respective `.txt` files.
- Logs include user, action, details, and timestamp for auditing.

---

## 🆘 Support

If you encounter issues, check:
- Bot permissions in all relevant channels.
- That all IDs in .env are correct.
- The bot console/logs for errors.

---

## 👥 Roles & Permissions

- **Archive Save**: <@&911072161349918720>, <@&1329910241835352064>
- **Blacklist/Infraction**: High Command and above
- **General Use**: Most commands are available to all users unless otherwise noted.

---

## 📢 Credits

Developed for the High Rock Military Corps Discord.

---

*For further details, see the code in the cogs folder or ask a developer for help.*