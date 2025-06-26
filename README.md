# High Rock Military Corps Discord Bot

A custom Discord bot for the High Rock Military Corps community, featuring persistent interactive embeds, ticketing, economy, verification, leveling, and more.

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

---

## Persistence

- Interactive embeds (dropdowns/buttons) remain functional after bot restarts.
- Message IDs for persistent embeds are stored in files (e.g. `divisions_message_id.txt`).

---

## File Structure

- `cogs/` — All bot features are modularized as cogs.
- `data/` — Databases for economy and leveling.
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
