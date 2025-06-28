# High Rock Military Corps Discord Bot

A custom Discord bot for the High Rock Military Corps community, featuring persistent interactive embeds, ticketing, economy, verification, leveling, callsign management, infractions, and more.

---

## Features

- **Persistent Interactive Embeds**  
  - Divisions, About Us, Regulations, and Assistance embeds with dropdowns/buttons that remain functional after bot restarts.
- **Ticket System**  
  - Open tickets for general support or management, with `/ticket-add` and `/ticket-remove` for ticket management.
- **Economy System**  
  - Daily rewards, shop, inventory, and item selling with autocomplete.
- **Leveling System**  
  - XP per message, level roles, and leaderboard.
- **Verification & Welcome**  
  - Verification and welcome messages with role assignment.
- **Applications**  
  - Application system for new members.
- **Suggestion Box**  
  - Submit and manage suggestions.
- **Callsign Management**  
  - Request, view, and manage callsigns with unique number enforcement and admin menu.
- **Infraction System**  
  - Issue, void, view, and list infractions with DM notification, role updates, logging, and paginated user infraction history.
- **Miscellaneous**  
  - Ping, uptime, and say commands.

---

## Setup

1. **Clone the repository and install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

2. **Configure your `.env` file:**
    - See the provided `.env` for all required IDs and settings.
    - Make sure to set your `DISCORD_BOT_TOKEN` and all relevant channel/role IDs.

3. **Run the bot:**
    ```sh
    python bot.py
    ```

---

## Usage

### Core Commands

- `!divisions`  
  Sends the persistent divisions embed in the configured channel (admin only).

- `!aboutus`  
  Sends the About Us embed with interactive rank info (owner only).

- `!regulations`  
  Sends the persistent regulations embed in the configured channel (owner only).

- `!assistance`  
  Sends the persistent assistance/ticket embed in the configured channel (admin only).

- `!verification`  
  Sends the verification embed in the configured channel (admin only).

- `!inventory` or `/inventory`  
  Shows your inventory.

- `/sell`  
  Sell items from your inventory (autocomplete only shows items you own).

- `/ticket-add`, `/ticket-remove`  
  Add or remove users from your ticket (civilians only).

- `!rank`, `!leaderboard`  
  Leveling and leaderboard commands.

- `/callsign` or `!callsign`  
  View or request your callsign. Only one of each number is allowed globally. Admins can add/remove callsigns via the admin menu.

---

### Infraction Commands

- `/infraction-issue`  
  Issue an infraction to a user, with DM, role updates, and logging.

- `/infraction-void`  
  Void (remove) an infraction by its ID. Marks the infraction as voided, logs the action, and updates the infraction message.

- `/infraction-view <infraction_id>`  
  View all details of a specific infraction by its ID, including voided status and reason.

- `/infraction-list <user> [page]`  
  List all infractions (current and voided) for a user, paginated.

- `/infraction-log`  
  View the last 10 non-voided infractions in an embed.

---

## Persistence

- Interactive embeds (dropdowns/buttons) remain functional after bot restarts.
- Message IDs for persistent embeds are stored in files (e.g. `divisions_message_id.txt`).
- Callsign and infraction data is stored in the `data/` and `logs/` folders.

---

## File Structure

- `cogs/` — All bot features are modularized as cogs.
- `data/` — Databases for economy, leveling, callsigns, and infractions.
- `logs/` — Logs for commands and infractions.
- `.env` — Configuration for all IDs and settings.

---

## Customization

- Edit `.env` to change channel/role IDs, embed colors, images, etc.
- Add or modify cogs in the `cogs/` folder to extend functionality.

---

## Support

If you encounter issues, check:
- Bot permissions in all relevant channels.
- That all IDs in `.env` are correct.
- The bot console/logs for errors.

---

## Credits

Developed for the High Rock Military Corps Discord
