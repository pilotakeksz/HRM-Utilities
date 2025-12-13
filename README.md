

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
- Discord Bot Token
- Discord Application ID

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd HRM-Utilities
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Environment Configuration
Create a `.env` file in the root directory with the following variables:

```env
# Bot Configuration
DISCORD_BOT_TOKEN=your_bot_token_here
APPLICATION_ID=your_application_id_here

# Role IDs
CIVILIAN_ROLE=1234567890123456789
MC_ROLE=1234567890123456789
HC_ROLE=1234567890123456789
TICKET_HANDLER_ROLE=1234567890123456789
ADMIN_ID=1234567890123456789

# Channel IDs
CHANNEL_ASSISTANCE=1234567890123456789
CHANNEL_TICKET_LOGS=1234567890123456789
ECONOMY_CHANNEL_ID=1234567890123456789

# Category IDs
CATEGORY_GENERAL=1234567890123456789
CATEGORY_MANAGEMENT=1234567890123456789
CATEGORY_ARCHIVED=1234567890123456789

# Embed Configuration
EMBED_COLOUR=0x00ff00
EMBED_FOOTER=High Rock Military Corps
EMBED_ICON=https://example.com/icon.png
EMBED1_IMAGE=https://example.com/image1.png
EMBED2_IMAGE=https://example.com/image2.png

# Economy Settings
DAILY_AMOUNT=250
XP_PER_MESSAGE=10
XP_INCREMENT_PER_LEVEL=25
XP_BASE_REQUIREMENT=100

# Bank Interest Role Tiers
BANK_ROLE_TIERS=1329910391840702515,0.02,1329910389437104220,0.015,1329910329701830686,0.01

# Level Roles (Level: Role ID)
LEVEL_ROLES=5:1368257473546551369,10:1368257734922866880,15:1368257891319939124

# External Links
MIA_REDIRECT=https://discord.gg/mia-server

# Database Paths
ECONOMY_DB_FILE=data/economy.db
DB_FILE=data/leveling.db
```

### Step 4: Run the Bot
```bash
python bot.py
```

## ⚙️ Configuration

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
   - Level roles (5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100)

## 📝 Commands

### 🎮 General Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `!ping` | Check bot latency | `!ping` | All users |
| `!uptime` | Show bot uptime | `!uptime` | All users |
| `!say <message>` | Make the bot say something | `!say Hello world!` | Admin only |

### 🏦 Economy Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/daily` | Claim daily reward | `/daily` | All users |
| `/balance` | Show wallet and bank balance | `/balance` | All users |
| `/work` | Work for coins (2 min cooldown) | `/work` | All users |
| `/fish` | Go fishing for items | `/fish` | All users |
| `/shop` | View item shop | `/shop [page]` | All users |
| `/buy <item> [amount]` | Buy items from shop | `/buy apple 5` | All users |
| `/sell <item> [amount]` | Sell items from inventory | `/sell apple 3` | All users |
| `/inventory` | Show your inventory | `/inventory` | All users |
| `/bank` | Show bank balance and interest | `/bank` | All users |
| `/deposit <amount>` | Deposit coins to bank | `/deposit 1000` | All users |
| `/withdraw <amount>` | Withdraw coins from bank | `/withdraw 500` | All users |
| `/rob <user>` | Try to rob another user | `/rob @user` | All users |
| `/crime` | Commit a crime for coins | `/crime` | All users |
| `/roulette <color> <amount>` | Bet on roulette | `/roulette red 100` | All users |
| `/bankheist <amount>` | Attempt bank heist | `/bankheist 1000` | All users |
| `/garage` | Do garage jobs | `/garage` | All users |
| `/econleaderboard` | Show richest users | `/econleaderboard` | All users |

### 📊 Leveling Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/rank` | Check your level and XP | `/rank` | All users |
| `/leaderboard` | Show top 10 users | `/leaderboard` | All users |

### 🎫 Ticket System Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/ticket-add <user>` | Add user to your ticket | `/ticket-add @user` | Civilians |
| `/ticket-remove <user>` | Remove user from your ticket | `/ticket-remove @user` | Civilians |

### 🛡️ Moderation Commands

#### Infraction System
| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/infraction-issue` | Issue an infraction | `/infraction-issue` | High Command |
| `/infraction-void <id>` | Void an infraction | `/infraction-void 123` | High Command |
| `/infraction-view <id>` | View infraction details | `/infraction-view 123` | All users (own) / HC |
| `/infraction-list <user> [page]` | List user infractions | `/infraction-list @user 1` | All users (own) / HC |

#### Quarantine / Leaderboard
| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `!qboard` / `!quarantine_leaderboard` | Show top users quarantined while holding the special role, or query a user's count (`!qboard @user`) | `!qboard` / `!qboard @user` | All users (per-user queries restricted to admins for other users) |
| `/infraction-log` | View recent infractions | `/infraction-log` | High Command |

#### Blacklist System
| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/blacklist` | Blacklist a user | `/blacklist` | High Command |
| `/blacklist-by-id <user_id>` | Blacklist by user ID | `/blacklist-by-id 123456789` | High Command |
| `/blacklist-void <id>` | Void a blacklist | `/blacklist-void 123` | High Command |
| `/blacklist-view <id>` | View blacklist details | `/blacklist-view 123` | All users (own) / HC |
| `/blacklist-list <user> [page]` | List user blacklists | `/blacklist-list @user 1` | All users (own) / HC |

### 📚 Archive System Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/archive` | Open archive interface | `/archive` | All users |
| `/archive-viewall` | View all archive entries | `/archive-viewall` | All users |
| `!sendtoarchive <date> <name> <text>` | Save archive entry | `!sendtoarchive 2024-01-15 John Hello` | Archive roles |

### 🎖️ Callsign Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `/callsign` | View or request callsign | `/callsign` | All users |
| `/callsign-admin` | Admin callsign management | `/callsign-admin` | Admins |

### 🎯 Management Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|-------------|
| `!divisions` | Send divisions embed | `!divisions` | Admin only |
| `!aboutus` | Send About Us embed | `!aboutus` | Owner only |
| `!regulations` | Send regulations embed | `!regulations` | Owner only |
| `!assistance` | Send assistance embed | `!assistance` | Admin only |
| `!verification` | Send verification embed | `!verification` | Admin only |

## 🔧 Systems Overview

### Economy System
The economy system features:
- **Daily Rewards**: Configurable daily amounts with role-based bonuses
- **Work System**: Random jobs with 2-minute cooldown
- **Fishing**: Catch fish and junk items
- **Shop System**: Buy and sell items with inventory management
- **Banking**: Deposit/withdraw with interest rates based on roles
- **Gambling**: Roulette and bank heist games
- **Robbery**: Risk-based stealing from other users
- **Garage Jobs**: Simple 20-job system for $1 each

### Leveling System
- **XP Gain**: Configurable XP per message
- **Progressive Levels**: Each level requires more XP than the last
- **Role Rewards**: Automatic role assignment at specific levels
- **Leaderboards**: Top 10 users by XP and level
- **Rank Tracking**: Individual user ranking system

### Ticket System
- **Multi-Type Tickets**: General support and management tickets
- **Transcript Logging**: Automatic transcript generation and storage
- **Auto-Deletion**: Scheduled ticket deletion after closure
- **User Management**: Add/remove users from tickets
- **HTML Transcripts**: Both text and HTML transcript formats

### Moderation Systems
- **Infraction Tracking**: Comprehensive infraction management
- **Blacklist System**: Server-wide blacklist with role management
- **DM Notifications**: Automatic user notifications
- **Logging**: All actions logged to files and channels
- **Pagination**: Easy browsing of user history

### Archive System
- **Interactive UI**: Dropdown-based archive browsing
- **Role Restrictions**: Configurable access control
- **Date Organization**: Archive entries organized by date
- **Search Functionality**: Find entries by name and date

## 📁 File Structure

```
HRM-Utilities/
├── bot.py                 # Main bot file
├── requirements.txt       # Python dependencies
├── README.md             # This documentation
├── .env                  # Environment configuration
├── .gitignore           # Git ignore file
├── cogs/                # Bot command modules
│   ├── about_us.py      # About Us embed system
│   ├── afk.py          # AFK status management
│   ├── applications.py  # Application system
│   ├── archive_commands.py # Archive system
│   ├── blacklist.py    # Blacklist management
│   ├── bulletin.py     # Bulletin system
│   ├── callsign.py     # Callsign management
│   ├── delete_archive.py # Archive deletion
│   ├── divisons.py     # Divisions embed
│   ├── economy.py      # Economy system
│   ├── embed.py        # Embed utilities
│   ├── infract.py      # Infraction system
│   ├── invest.py       # Investment system
│   ├── leveling.py     # Leveling system
│   ├── MDT.py          # Mobile Data Terminal
│   ├── misc.py         # Miscellaneous commands
│   ├── Rules.py        # Rules embed system
│   ├── say.py          # Say command
│   ├── suggestion.py   # Suggestion system
│   ├── ticket_system.py # Ticket management
│   ├── verification.py # Verification system
│   ├── welcome.py      # Welcome system
│   └── econ/           # Economy data
│       └── items.txt   # Shop items configuration
├── data/               # Database files
├── logs/               # Log files
├── transcripts/        # Ticket transcripts
└── hrm-utilities/      # Additional utilities
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Development Guidelines
- Follow Python PEP 8 style guidelines
- Add comments for complex logic
- Update documentation for new features
- Test commands before submitting

## 📄 License

This project is developed for the High Rock Military Corps Discord server.

## 👥 Credits

**Development Team:**
- **x pilotakeksz - Tuna 🐟 x** - Lead Developer
- **x spigoned - Lazeoftheb x** - Co-Developer

**Special Thanks:**
- High Rock Military Corps community
- Discord.py development team
- All contributors and testers

---

**Version:** 2.0.0  
**Last Updated:** January 2024  
**Discord Server:** High Rock Military Corps
