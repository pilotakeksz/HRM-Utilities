# 🟩 HRM-Utilities Discord Bot

A comprehensive Discord bot designed for the High Rock Military Corps server, featuring advanced moderation tools, economy systems, leveling, ticket management, and more.

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Commands](#-commands)
- [Systems Overview](#-systems-overview)
- [File Structure](#-file-structure)
- [Contributing](#-contributing)
- [Credits](#-credits)

## ✨ Features

### 🎯 Core Systems
- **Persistent Interactive Embeds**: Divisions, About Us, Regulations, and Assistance embeds with dropdowns/buttons
- **Advanced Ticket System**: Multi-type ticket creation with transcript logging and auto-deletion
- **Comprehensive Economy System**: Daily rewards, shop, inventory, fishing, gambling, and banking
- **Progressive Leveling System**: XP-based leveling with automatic role rewards
- **Verification & Welcome**: Automated member verification and welcome messages
- **Application System**: Streamlined application process for new members
- **Suggestion Box**: Community suggestion submission and management

### 🛡️ Moderation Tools
- **Infraction System**: Issue, void, view, and list infractions with DM notifications
- **Blacklist System**: Comprehensive blacklist management with role updates
- **Archive System**: Interactive archive browsing with role-based restrictions
- **Callsign Management**: Unique callsign assignment with admin controls

### 🎮 Interactive Features
- **AFK System**: Set and manage AFK status
- **MDT (Mobile Data Terminal)**: Advanced data management interface
- **Bulletin System**: Server announcements and updates
- **Miscellaneous Tools**: Ping, uptime, and utility commands

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- Discord Application ID
- Base64-encoded Discord Bot Token

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd HRM-Utilities
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

### Environment Configuration
Create two files in the root directory:

1. **`.env`** for unencoded settings
2. **`.env.token`** for the base64-encoded bot token

#### Example `.env`
```env
# Application and guild IDs
APPLICATION_ID=your_application_id_here
GUILD_ID=your_primary_guild_id_here

# Role IDs (example placeholders)
CIVILIAN_ROLE=1234567890123456789
MC_ROLE=1234567890123456789
HC_ROLE=1234567890123456789
TICKET_HANDLER_ROLE=1234567890123456789
ADMIN_ID=1234567890123456789

# Channel & Category IDs
CHANNEL_ASSISTANCE=1234567890123456789
CHANNEL_TICKET_LOGS=1234567890123456789
ECONOMY_CHANNEL_ID=1234567890123456789
CATEGORY_GENERAL=1234567890123456789
CATEGORY_MANAGEMENT=1234567890123456789
CATEGORY_ARCHIVED=1234567890123456789

# Embed Configuration
EMBED_COLOUR=0x00ff00
EMBED_FOOTER=High Rock Military Corps
EMBED_ICON=https://example.com/icon.png
EMBED1_IMAGE=https://example.com/image1.png
EMBED2_IMAGE=https://example.com/image2.png

# Economy & Leveling
DAILY_AMOUNT=250
XP_PER_MESSAGE=10
XP_INCREMENT_PER_LEVEL=25
XP_BASE_REQUIREMENT=100

# Database Paths (optional defaults)
ECONOMY_DB_FILE=data/economy.db
DB_FILE=data/leveling.db
```

#### Example `.env.token`
```env
# Base64-encoded Discord bot token
DISCORD_BOT_TOKEN_BASE64=your_base64_encoded_bot_token_here
```

### Required Permissions
The bot requires the following Discord permissions:
- Send Messages
- Embed Links
- Attach Files
- Manage Channels
- Manage Roles
- Read Message History
- Use Slash Commands

### Server Setup
1. **Create Required Channels**:
   - Economy channel (for economy commands)
   - Ticket logs channel
   - Assistance channel
2. **Create Required Categories**:
   - General tickets category
   - Management tickets category
   - Archived tickets category
3. **Create Required Roles**:
   - Civilian role
   - MC (Management) role
   - HC (High Command) role
   - Ticket Handler role
   - Level roles (5, 10, 15, …, 100)

## ⚡ HTTP Server
On startup, the bot also serves the `HTTP/` directory on port **8080**. Access static assets at `http://<host>:8080/`.

## 🏃‍♂️ Run the Bot
```bash
python bot.py
```

## 📝 Commands
*(...remaining sections unchanged...)*