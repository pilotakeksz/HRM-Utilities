import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import os
import random
from datetime import datetime, timedelta
import math
from discord.ext.commands import cooldown, BucketType, CommandOnCooldown

DB_PATH = os.getenv("ECONOMY_DB_FILE", "data/economy.db")
DAILY_AMOUNT = int(os.getenv("DAILY_AMOUNT", 250))
BANK_ROLE_TIERS = [
    (1329910391840702515, 0.02),  # Highest role, 2%
    (1329910389437104220, 0.015), # Middle role, 1.5%
    (1329910329701830686, 0.01),  # Lowest role, 1%
]

SHOP_ITEMS_PER_PAGE = 5
ECONOMY_CHANNEL_ID = 1329910482194141185

def load_shop_items():
    items = {}
    items_file = os.path.join(os.path.dirname(__file__), "econ", "items.txt")
    if not os.path.exists(items_file):
        return items
    with open(items_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                name, price, desc = line.split("|", 2)
                items[name.lower()] = {"price": int(price), "desc": desc}
            except Exception:
                continue
    return items

SHOP_ITEMS = load_shop_items()

FISH_TYPES = [
    "salmon", "trout", "bass", "catfish", "carp", "goldfish", "pike", "perch", "sturgeon", "eel",
    "anchovy", "sardine", "mackerel", "tuna", "marlin", "snapper", "grouper", "halibut", "flounder", "tilapia",
    "herring", "barracuda", "shad", "sunfish", "bluegill", "crappie", "drum", "gar", "mullet", "walleye"
]
JUNK_TYPES = [
    "boot", "tin can", "torn newspaper", "broken bottle", "driftwood", "old tire", "rusty key", "plastic bag",
    "soggy sock", "broken rod", "bottle cap", "old phone", "sunglasses", "license plate", "toy car", "spoon",
    "fork", "old wallet", "empty wallet", "broken watch"
]

WORK_RESPONSES = [
    "You worked as a **Barista** ☕ and earned",
    "You delivered **Pizza** 🍕 and earned",
    "You walked a **Dog** 🐕 and earned",
    "You mowed a **Lawn** 🌱 and earned",
    "You washed a **Car** 🚗 and earned",
    "You coded a **Website** 💻 and earned",
    "You painted a **Fence** 🎨 and earned",
    "You helped at a **Bakery** 🥐 and earned",
    "You tutored a **Student** 📚 and earned",
    "You cleaned a **Pool** 🏊 and earned",
    "You worked as a **Cashier** 🛒 and earned",
    "You fixed a **Bike** 🚲 and earned",
    "You organized a **Garage** 🧰 and earned",
    "You delivered **Groceries** 🥦 and earned",
    "You worked as a **Receptionist** ☎️ and earned",
    "You DJ'd a **Party** 🎧 and earned",
    "You streamed on **Twitch** 🎮 and earned",
    "You made a **YouTube video** 📹 and earned",
    "You walked a neighbor's **iguana** 🦎 and earned",
    "You ran a **lemonade stand** 🍋 and earned",
    "You did **yard work** 🧹 and earned",
    "You cleaned gutters 🧽 and earned",
    "You assembled IKEA furniture 🔧 and earned",
    "You did someone's taxes 🧾 and earned",
    "You ran a bake sale 🧁 and earned",
    "You played music on the street 🎸 and earned",
    "You fixed a computer 🖥️ and earned",
    "You did voice acting 🎤 and earned",
    "You made balloon animals 🎈 and earned",
    "You worked as a mascot 🦁 and earned",
    "You fed a wild capybara <:capy:1381521913238523955> and earned",
    "You worked a job in the local cinema 🍿 and earned"
]

CRIME_REWARDS = [
    {"desc": "You hacked a vending machine! 🤖", "amount": 200},
    {"desc": "You stole a bike! 🚲", "amount": 150},
    {"desc": "You robbed a lemonade stand! 🍋", "amount": 100},
    {"desc": "You failed and paid a fine. 💸", "amount": -100},
    {"desc": "You got caught and paid bail. 🚔", "amount": -200},
    {"desc": "You spray painted a wall! 🎨", "amount": 120},
    {"desc": "You jaywalked across a busy street! 🚦", "amount": 80},
    {"desc": "You pickpocketed a tourist! 🎒", "amount": 140},
    {"desc": "You snuck into a movie theater! 🎬", "amount": 90},
    {"desc": "You ran an illegal lemonade stand! 🍋", "amount": 110},
    {"desc": "You cheated at cards in a back alley! 🃏", "amount": 160},
    {"desc": "You hacked a claw machine! 🕹️", "amount": 130},
    {"desc": "You tricked someone with a fake raffle! 🎟️", "amount": 170},
    {"desc": "You faked a talent show act for tips! 🎤", "amount": 100},
    {"desc": "You shoplifted a candy bar! 🍫", "amount": 70},
    {"desc": "You pretended to be a parking inspector! 🅿️", "amount": 150},
    {"desc": "You ran a fake car wash scam! 🚗", "amount": 180},
    {"desc": "You siphoned Wi-Fi from your neighbor! 📶", "amount": 90},
    {"desc": "You resold school lunch tickets! 🥪", "amount": 110},
    {"desc": "You forged a library card! 📖", "amount": 60},
    {"desc": "You got caught by mall security. 🚨", "amount": -120},
    {"desc": "You slipped while running from the scene. 🏃", "amount": -100},
    {"desc": "You accidentally robbed a police fundraiser. 🚓", "amount": -200},
    {"desc": "You tripped the alarm while escaping. 🔔", "amount": -150},
    {"desc": "You panicked and gave the money back. 😱", "amount": -90}
]

def log_econ_action(command: str, user: discord.User, amount: int = None, item: str = None, extra: str = ""):
    log_dir = os.path.join(os.path.dirname(__file__), "../logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "economy_actions.txt")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    user_str = f"{user} ({user.id})"
    parts = [f"[{timestamp}]", f"User: {user_str}", f"Command: {command}"]
    if amount is not None:
        parts.append(f"Amount: {amount}")
    if item:
        parts.append(f"Item: {item}")
    if extra:
        parts.append(f"Extra: {extra}")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(" | ".join(parts) + "\n")

def economy_channel_only():
    async def predicate(ctx_or_interaction):
        # For commands.Context
        if hasattr(ctx_or_interaction, "channel") and getattr(ctx_or_interaction, "channel", None):
            return ctx_or_interaction.channel.id == ECONOMY_CHANNEL_ID
        # For discord.Interaction
        if hasattr(ctx_or_interaction, "channel_id"):
            return ctx_or_interaction.channel_id == ECONOMY_CHANNEL_ID
        return False
    return commands.check(predicate)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.apply_bank_interest.start()

    async def cog_load(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL,
                    last_daily TEXT,
                    last_work TEXT,
                    bank INTEGER DEFAULT 0
                )
            """)
            # --- FIXED INVENTORY TABLE ---
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item TEXT,
                    amount INTEGER,
                    value INTEGER DEFAULT NULL
                    -- No PRIMARY KEY here; SQLite will use implicit rowid
                )
            """)
            await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT balance, last_daily, last_work, bank FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "balance": row[0],
                    "last_daily": row[1],
                    "last_work": row[2],
                    "bank": row[3] if row[3] is not None else 0
                }
            else:
                await db.execute("INSERT INTO users (user_id, balance, last_daily, last_work, bank) VALUES (?, ?, ?, ?, ?)", (user_id, 0, None, None, 0))
                await db.commit()
                return {"balance": 0, "last_daily": None, "last_work": None, "bank": 0}

    async def update_user(self, user_id, balance=None, last_daily=None, last_work=None, bank=None):
        user = await self.get_user(user_id)
        balance = balance if balance is not None else user["balance"]
        last_daily = last_daily if last_daily is not None else user["last_daily"]
        last_work = last_work if last_work is not None else user["last_work"]
        bank = bank if bank is not None else user["bank"]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = ?, last_daily = ?, last_work = ?, bank = ? WHERE user_id = ?",
                (balance, last_daily, last_work, bank, user_id)
            )
            await db.commit()

    # --- NEW add_item ---
    async def add_item(self, user_id, item, amount, value=None):
        async with aiosqlite.connect(DB_PATH) as db:
            # For fish/junk, store each instance with its value
            if value is not None:
                for _ in range(amount):
                    await db.execute(
                        "INSERT INTO inventory (user_id, item, amount, value) VALUES (?, ?, ?, ?)",
                        (user_id, item, 1, value)
                    )
            else:
                # For normal items, just update amount (value is NULL)
                cursor = await db.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ? AND value IS NULL", (user_id, item))
                row = await cursor.fetchone()
                if row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE user_id = ? AND item = ? AND value IS NULL", (amount, user_id, item))
                else:
                    await db.execute("INSERT INTO inventory (user_id, item, amount, value) VALUES (?, ?, ?, NULL)", (user_id, item, amount))
            await db.commit()

    # --- NEW get_inventory ---
    async def get_inventory(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT item, amount, value FROM inventory WHERE user_id = ?", (user_id,))
            return await cursor.fetchall()

    # --- DAILY ---
    def get_daily_amount(self, member):
        for role_id, amount in [
            (1329910391840702515, 1000),
            (1329910389437104220, 500),
            (1329910329701830686, 250),
        ]:
            if hasattr(member, "roles") and any(r.id == role_id for r in getattr(member, "roles", [])):
                return amount
        return DAILY_AMOUNT

    @commands.command(name="daily")
    @economy_channel_only()
    @cooldown(1, 86400, BucketType.user)
    async def daily_command(self, ctx):
        await self._daily(ctx.author, ctx)

    @app_commands.command(name="daily", description="Claim your daily reward.")
    @commands.check(lambda i: i.channel_id == ECONOMY_CHANNEL_ID)
    async def daily_slash(self, interaction: discord.Interaction):
        await self._daily(interaction.user, interaction)

    async def _daily(self, user, destination):
        data = await self.get_user(user.id)
        now = datetime.utcnow()
        last_daily = data["last_daily"]
        if last_daily:
            last_daily_dt = datetime.fromisoformat(last_daily)
            if now - last_daily_dt < timedelta(days=1):
                next_time = last_daily_dt + timedelta(days=1)
                seconds = int((next_time - now).total_seconds())
                hours, remainder = divmod(seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                msg = f"⏳ You have already claimed your daily. Try again in {hours}h {minutes}m {seconds}s."
                if hasattr(destination, "response"):
                    await destination.response.send_message(msg, ephemeral=True)
                else:
                    await destination.send(msg)
                return
        amount = self.get_daily_amount(user)
        new_balance = data["balance"] + amount
        await self.update_user(user.id, balance=new_balance, last_daily=now.isoformat())
        embed = discord.Embed(
            title="Daily Reward",
            description=f"You claimed your daily reward of **{amount}** coins!",
            color=0xd0b47b
        )
        log_econ_action("daily", user, amount=amount)
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK SYSTEM ---
    def get_bank_interest(self, member):
        for role_id, interest in BANK_ROLE_TIERS:
            if hasattr(member, "roles") and any(r.id == role_id for r in getattr(member, "roles", [])):
                return interest
        return 0.0

    @tasks.loop(hours=24)
    async def apply_bank_interest(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, bank FROM users") as cursor:
                async for row in cursor:
                    user_id, bank = row
                    member = self.bot.get_user(user_id)
                    if not member:
                        try:
                            member = await self.bot.fetch_user(user_id)
                        except Exception:
                            continue
                    interest = self.get_bank_interest(member)
                    if interest > 0 and bank > 0:
                        interest_amount = int(bank * interest)
                        await db.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (interest_amount, user_id))
            await db.commit()

    # --- BALANCE ---
    @commands.command(name="bal", aliases=["balance"])
    async def balance_command(self, ctx):
        await self.show_balance(ctx.author, ctx)

    @app_commands.command(name="balance", description="Show your wallet and bank balance.")
    async def balance_slash(self, interaction: discord.Interaction):
        await self.show_balance(interaction.user, interaction)

    async def show_balance(self, user, destination):
        data = await self.get_user(user.id)
        embed = discord.Embed(
            title=f"{user.name}'s Balance",
            description=(
                f"💰 **Wallet:** {data['balance']} coins\n"
                f"🏦 **Bank:** {data['bank']} coins\n"
                f"📊 **Total:** {data['balance'] + data['bank']} coins"
            ),
            color=0xd0b47b
        )
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- SELL ALL ---
    @commands.command(name="sellall")
    async def sellall_command(self, ctx):
        await self.sell_all(ctx.author, ctx)

    @app_commands.command(name="sellall", description="Sell all items in your inventory.")
    async def sellall_slash(self, interaction: discord.Interaction):
        await self.sell_all(interaction.user, interaction)

    async def sell_all(self, user, destination):
        # --- NEW LOGIC ---
        inventory = await self.get_inventory(user.id)
        total_earned = 0
        sold_items = []
        async with aiosqlite.connect(DB_PATH) as db:
            for item, amount, value in inventory:
                if amount > 0 and item in SHOP_ITEMS and value is None:
                    price = SHOP_ITEMS[item]["price"]
                    earned = price * amount
                    await db.execute("UPDATE inventory SET amount = amount - ? WHERE user_id = ? AND item = ? AND value IS NULL", (amount, user.id, item))
                    data = await self.get_user(user.id)
                    await self.update_user(user.id, balance=data["balance"] + earned)
                    total_earned += earned
                    sold_items.append(f"**{item.title()}** x{amount} (**{earned}** coins)")
                    log_econ_action("sellall", user, amount=earned, item=item, extra=f"Quantity: {amount}")
            await db.commit()
        if sold_items:
            desc = "You sold:\n" + "\n".join(sold_items) + f"\n\nTotal earned: **{total_earned}** coins!"
        else:
            desc = "You have no items to sell."
        embed = discord.Embed(
            title="Sell All",
            description=desc,
            color=0xd0b47b
        )
        log_econ_action("sellall-summary", user, amount=total_earned, extra="All items sold")
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ECON LEADERBOARD ---
    @commands.command(name="eclb", aliases=["econlb", "econleaderboard"])
    async def eclb_command(self, ctx):
        await self.econ_leaderboard(ctx)

    @app_commands.command(name="econleaderboard", description="Show the top 10 richest users (wallet + bank).")
    async def eclb_slash(self, interaction: discord.Interaction):
        await self.econ_leaderboard(interaction)

    async def econ_leaderboard(self, destination):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, balance, bank FROM users")
            rows = await cursor.fetchall()
        leaderboard = sorted(rows, key=lambda r: (r[1] or 0) + (r[2] or 0), reverse=True)[:10]
        place_emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 7

        embed = discord.Embed(
            title="Economy Leaderboard",
            description="Top 10 users by wallet + bank",
            color=0xd0b47b
        )

        if not leaderboard:
            embed.description = "No users found."
        else:
            lines = []
            guild = None
            if hasattr(destination, "guild") and destination.guild:
                guild = destination.guild
            elif hasattr(destination, "user") and hasattr(destination, "guild_id"):
                guild = self.bot.get_guild(destination.guild_id)
            for idx, (user_id, balance, bank) in enumerate(leaderboard, start=1):
                member = guild.get_member(user_id) if guild else None
                name = member.mention if member else f"<@{user_id}>"
                emoji = place_emojis[idx - 1] if idx <= len(place_emojis) else "🏅"
                lines.append(
                    f"{emoji} **#{idx}** {name}\nWallet: **{balance}** | Bank: **{bank}** | Total: **{balance + bank}**"
                )
            embed.add_field(name="Ranks", value="\n".join(lines), inline=False)

        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- WORK ---
    @commands.command(name="work")
    @cooldown(1, 120, BucketType.user)
    async def work_command(self, ctx):
        await self._work(ctx.author, ctx)

    @app_commands.command(name="work", description="Work a random job for coins (2 min cooldown).")
    async def work_slash(self, interaction: discord.Interaction):
        await self._work(interaction.user, interaction)

    async def _work(self, user, destination):
        data = await self.get_user(user.id)
        amount = round(random.randint(5, 500) / 5) * 5
        job_response = random.choice(WORK_RESPONSES)
        new_balance = data["balance"] + amount
        await self.update_user(user.id, balance=new_balance, last_work=datetime.utcnow().isoformat())
        embed = discord.Embed(
            title="Work",
            description=f"{job_response} **{amount}** coins!",
            color=0xd0b47b
        )
        log_econ_action("work", user, amount=amount)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- GARAGE ---
    @commands.command(name="garage")
    async def garage_command(self, ctx):
        await self.garage(ctx.author, ctx)

    @app_commands.command(name="garage", description="Do garage jobs for $1 each (20 jobs).")
    async def garage_slash(self, interaction: discord.Interaction):
        await self.garage(interaction.user, interaction)

    async def garage(self, user, destination):
        jobs = 20
        amount = jobs * 1
        data = await self.get_user(user.id)
        new_balance = data["balance"] + amount
        await self.update_user(user.id, balance=new_balance)
        embed = discord.Embed(
            title="Garage Jobs",
            description=f"You completed {jobs} garage jobs and earned **{amount}** coins!",
            color=0xd0b47b
        )
        log_econ_action("garage", user, amount=amount)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- FISHING ---
    @commands.command(name="fish")
    @cooldown(1, 2, BucketType.user)
    async def fish_command(self, ctx):
        await self.fish(ctx.author, ctx)

    @app_commands.command(name="fish", description="Go fishing for a random fish or junk!")
    async def fish_slash(self, interaction: discord.Interaction):
        await self.fish(interaction.user, interaction)

    async def fish(self, user, destination):
        # 60% chance for junk, 40% chance for fish
        if random.random() < 0.6:
            fish = random.choice(JUNK_TYPES)
            value = 1
        else:
            fish = random.choice(FISH_TYPES)
            value = round(random.randint(100, 1000) / 5) * 5
        await self.add_item(user.id, fish, 1, value=value)
        embed = discord.Embed(
            title="🎣 Fishing",
            description=f"You caught a **{fish.title()}** worth **{value}** coins! Use `/sell {fish}` or `!sell {fish}` to sell it.",
            color=0xd0b47b
        )
        log_econ_action("fish", user, amount=value, item=fish)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- SELL ---
    @commands.command(name="sell")
    async def sell_command(self, ctx, item: str, amount: int = 1):
        await self.sell(ctx.author, item.lower(), amount, ctx)

    @app_commands.command(name="sell", description="Sell an item from your inventory.")
    @app_commands.describe(item="The item to sell", amount="How many to sell")
    async def sell_slash(self, interaction: discord.Interaction, item: str, amount: int = 1):
        await self.sell(interaction.user, item.lower(), amount, interaction)

    async def sell(self, user, item, amount, destination):
        inventory = await self.get_inventory(user.id)
        # --- NEW LOGIC ---
        # For fish/junk, sell by stored value; for normal items, use static price
        fish_junk = FISH_TYPES + JUNK_TYPES
        if item not in SHOP_ITEMS:
            embed = discord.Embed(
                title="Sell",
                description="That item doesn't exist.",
                color=0xd0b47b
            )
            log_econ_action("sell_fail", user, item=item)
        else:
            # Count how many of this item user has (separate fish/junk and normal)
            if item in fish_junk:
                # Get all instances with value (fish/junk)
                owned = [(amt, val) for itm, amt, val in inventory if itm == item and val is not None]
                total_owned = sum(amt for amt, _ in owned)
                if total_owned < 1:
                    embed = discord.Embed(
                        title="Sell",
                        description=f"You don't have any **{item.title()}** to sell.",
                        color=0xd0b47b
                    )
                    log_econ_action("sell_fail", user, item=item, extra="No items")
                else:
                    sell_amount = min(amount, total_owned)
                    # Get the values of the first N fish/junk
                    async with aiosqlite.connect(DB_PATH) as db:
                        cursor = await db.execute(
                            "SELECT rowid, value FROM inventory WHERE user_id = ? AND item = ? AND value IS NOT NULL LIMIT ?",
                            (user.id, item, sell_amount)
                        )
                        rows = await cursor.fetchall()
                        if not rows:
                            embed = discord.Embed(
                                title="Sell",
                                description=f"You don't have any **{item.title()}** to sell.",
                                color=0xd0b47b
                            )
                            log_econ_action("sell_fail", user, item=item, extra="No items")
                        else:
                            total = sum(row[1] for row in rows)
                            # Delete sold fish/junk
                            rowids = [row[0] for row in rows]
                            for rid in rowids:
                                await db.execute("DELETE FROM inventory WHERE rowid = ?", (rid,))
                            await db.commit()
                            data = await self.get_user(user.id)
                            await self.update_user(user.id, balance=data["balance"] + total)
                            embed = discord.Embed(
                                title="Sell",
                                description=f"You sold **{sell_amount} {item.title()}** for **{total}** coins!",
                                color=0xd0b47b
                            )
                            log_econ_action("sell", user, amount=total, item=item, extra=f"Quantity: {sell_amount}")
            else:
                # Normal items (static price)
                owned = [(amt, val) for itm, amt, val in inventory if itm == item and val is None]
                total_owned = sum(amt for amt, _ in owned)
                if total_owned < 1:
                    embed = discord.Embed(
                        title="Sell",
                        description=f"You don't have any **{item.title()}** to sell.",
                        color=0xd0b47b
                    )
                    log_econ_action("sell_fail", user, item=item, extra="No items")
                else:
                    sell_amount = min(amount, total_owned)
                    price = SHOP_ITEMS[item]["price"]
                    total = price * sell_amount
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE inventory SET amount = amount - ? WHERE user_id = ? AND item = ? AND value IS NULL", (sell_amount, user.id, item))
                        await db.commit()
                    data = await self.get_user(user.id)
                    await self.update_user(user.id, balance=data["balance"] + total)
                    embed = discord.Embed(
                        title="Sell",
                        description=f"You sold **{sell_amount} {item.title()}** for **{total}** coins!",
                        color=0xd0b47b
                    )
                    log_econ_action("sell", user, amount=total, item=item, extra=f"Quantity: {sell_amount}")
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- INVENTORY ---
    @commands.command(name="inventory", aliases=["inv"])
    async def inventory_command(self, ctx):
        await self.show_inventory(ctx.author, ctx)

    @app_commands.command(name="inventory", description="Show your inventory.")
    async def inventory_slash(self, interaction: discord.Interaction):
        await self.show_inventory(interaction.user, interaction)

    async def show_inventory(self, user, destination):
        inventory = await self.get_inventory(user.id)
        # Group by item, show total count (fish/junk and normal)
        item_counts = {}
        for item, amount, value in inventory:
            if value is None:
                item_counts[item] = item_counts.get(item, 0) + amount
            else:
                item_counts[item] = item_counts.get(item, 0) + 1
        nonzero_items = [(item, amt) for item, amt in item_counts.items() if amt > 0]
        if not nonzero_items:
            desc = "Your inventory is empty."
        else:
            desc = "\n".join(f"**{item.title()}** × {amt}" for item, amt in nonzero_items)
        embed = discord.Embed(
            title=f"{user.name}'s Inventory",
            description=desc,
            color=0xd0b47b
        )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- SELL AUTOCOMPLETE FOR SLASH COMMAND ---
    @sell_slash.autocomplete("item")
    async def sell_item_autocomplete(self, interaction: discord.Interaction, current: str):
        inventory = await self.get_inventory(interaction.user.id)
        item_counts = {}
        for item, amount, value in inventory:
            if value is None:
                item_counts[item] = item_counts.get(item, 0) + amount
            else:
                item_counts[item] = item_counts.get(item, 0) + 1
        choices = [
            app_commands.Choice(
                name=f"{item.title()} ({amt})",
                value=item
            )
            for item, amt in item_counts.items()
            if amt > 0
        ]
        return choices[:25]

    # --- SELL ALL FISH/JUNK ---
    @commands.command(name="sellallfish")
    async def sellallfish_command(self, ctx):
        await self.sell_all_fish(ctx.author, ctx)

    @app_commands.command(name="sellallfish", description="Sell all fish and junk items in your inventory.")
    async def sellallfish_slash(self, interaction: discord.Interaction):
        await self.sell_all_fish(interaction.user, interaction)

    async def sell_all_fish(self, user, destination):
        inventory = await self.get_inventory(user.id)
        fish_types = FISH_TYPES + JUNK_TYPES
        total_earned = 0
        sold_items = []
        async with aiosqlite.connect(DB_PATH) as db:
            for item in fish_types:
                # Get all instances with value
                cursor = await db.execute(
                    "SELECT rowid, value FROM inventory WHERE user_id = ? AND item = ? AND value IS NOT NULL",
                    (user.id, item)
                )
                rows = await cursor.fetchall()
                if rows:
                    earned = sum(row[1] for row in rows)
                    for rid, _ in rows:
                        await db.execute("DELETE FROM inventory WHERE rowid = ?", (rid,))
                    await db.commit()
                    data = await self.get_user(user.id)
                    await self.update_user(user.id, balance=data["balance"] + earned)
                    total_earned += earned
                    sold_items.append(f"**{item.title()}** x{len(rows)} (**{earned}** coins)")
                    log_econ_action("sell-all-fish", user, amount=earned, item=item, extra=f"Quantity: {len(rows)}")
            await db.commit()
        if sold_items:
            desc = "You sold:\n" + "\n".join(sold_items) + f"\n\nTotal earned: **{total_earned}** coins!"
        else:
            desc = "You have no fish or junk items to sell."
        embed = discord.Embed(
            title="Sell All Fish",
            description=desc,
            color=0xd0b47b
        )
        log_econ_action("sell-all-fish-summary", user, amount=total_earned, extra="All fish sold")
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK ---
    @commands.command(name="bank")
    async def bank_command(self, ctx):
        await self.show_bank(ctx.author, ctx)

    @app_commands.command(name="bank", description="Show your bank balance and interest rate.")
    async def bank_slash(self, interaction: discord.Interaction):
        await self.show_bank(interaction.user, interaction)

    async def show_bank(self, user, destination):
        data = await self.get_user(user.id)
        interest = self.get_bank_interest(user)
        embed = discord.Embed(
            title=f"{user.name}'s Bank",
            description=(
                f"🏦 **Bank Balance:** {data['bank']} coins\n"
                f"💸 **Interest Rate:** {interest*100:.2f}% per day"
            ),
            color=0x00bfae
        )
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- DEPOSIT ---
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit_command(self, ctx, amount: int):
        await self.deposit(ctx.author, amount, ctx)

    @app_commands.command(name="deposit", description="Deposit coins from your wallet to your bank.")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit_slash(self, interaction: discord.Interaction, amount: int):
        await self.deposit(interaction.user, amount, interaction)

    async def deposit(self, user, amount, destination):
        data = await self.get_user(user.id)
        if amount <= 0 or data["balance"] < amount:
            embed = discord.Embed(
                title="Deposit",
                description="Invalid amount or insufficient wallet funds.",
                color=0x00bfae
            )
            log_econ_action("deposit_fail", user, amount=amount)
        else:
            await self.update_user(user.id, balance=data["balance"] - amount, bank=data["bank"] + amount)
            embed = discord.Embed(
                title="Deposit",
                description=f"You deposited **{amount}** coins from your wallet to your bank.",
                color=0x00bfae
            )
            log_econ_action("deposit", user, amount=amount)
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ROB (wallet only, not bank) ---
    @commands.command(name="rob")
    @cooldown(1, 180, BucketType.user)
    async def rob_command(self, ctx, target: discord.Member):
        await self.rob(ctx.author, target, ctx)

    @app_commands.command(name="rob", description="Try to rob another user (wallet only).")
    @app_commands.describe(target="The user to rob")
    async def rob_slash(self, interaction: discord.Interaction, target: discord.Member):
        await self.rob(interaction.user, target, interaction)

    async def rob(self, user, target, destination):
        if user.id == target.id:
            embed = discord.Embed(
                title="Rob",
                description="You can't rob yourself!",
                color=0xd0b47b
            )
            log_econ_action("rob_fail", user, extra="Tried to rob self")
        else:
            user_data = await self.get_user(user.id)
            target_data = await self.get_user(target.id)
            if target_data["balance"] < 100:
                embed = discord.Embed(
                    title="Rob",
                    description="Target doesn't have enough coins in their wallet to rob!",
                    color=0xd0b47b
                )
                log_econ_action("rob_fail", user, extra=f"Target {target} ({target.id}) too poor")
            else:
                success = random.random() < 0.5
                if success:
                    stolen = random.randint(50, min(500, target_data["balance"]))
                    await self.update_user(user.id, balance=user_data["balance"] + stolen)
                    await self.update_user(target.id, balance=target_data["balance"] - stolen)
                    embed = discord.Embed(
                        title="Rob",
                        description=f"You robbed {target.mention} and stole **{stolen}** coins from their wallet!",
                        color=0xd0b47b
                    )
                    log_econ_action("rob", user, amount=stolen, extra=f"target={target} ({target.id})")
                else:
                    loss = random.randint(20, 100)
                    await self.update_user(user.id, balance=max(0, user_data["balance"] - loss))
                    embed = discord.Embed(
                        title="Rob",
                        description=f"You got caught and lost **{loss}** coins!",
                        color=0xd0b47b
                    )
                    log_econ_action("rob_fail", user, amount=loss, extra=f"target={target} ({target.id})")
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- SHOP ---
    @commands.command(name="shop")
    async def shop_command(self, ctx, page: int = 1):
        await self.shop(ctx, page)

    @app_commands.command(name="shop", description="View the item shop.")
    @app_commands.describe(page="Page number")
    async def shop_slash(self, interaction: discord.Interaction, page: int = 1):
        await self.shop(interaction, page)

    async def shop(self, destination, page=1):
        embed = get_shop_embed(page)
        view = ShopView(page=page)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed, view=view)
        else:
            await destination.send(embed=embed, view=view)

    # --- ROULETTE ---
    @commands.command(name="roulette")
    async def roulette_command(self, ctx, color: str, amount: int):
        await self.roulette(ctx.author, color.lower(), amount, ctx)

    @app_commands.command(name="roulette", description="Bet on roulette (red, black, green).")
    @app_commands.describe(color="Color to bet on", amount="Amount to bet")
    async def roulette_slash(self, interaction: discord.Interaction, color: str, amount: int):
        await self.roulette(interaction.user, color.lower(), amount, interaction)

    async def roulette(self, user, color, amount, destination):
        ROULETTE_COLORS = {"red": 2, "black": 2, "green": 14}
        if color not in ROULETTE_COLORS:
            embed = discord.Embed(
                title="Roulette",
                description="Invalid color. Choose red, black, or green.",
                color=0xd0b47b
            )
        else:
            data = await self.get_user(user.id)
            if amount > data["balance"] or amount <= 0:
                embed = discord.Embed(
                    title="Roulette",
                    description="Invalid bet amount.",
                    color=0xd0b47b
                )
            else:
                win_color = random.choices(
                    population=["red", "black", "green"],
                    weights=[18, 18, 2],
                    k=1
                )[0]
                if color == win_color:
                    multiplier = ROULETTE_COLORS[color]
                    winnings = amount * multiplier
                    new_balance = data["balance"] + winnings
                    result = f"You won! The ball landed on **{win_color}**. You won **{winnings}** coins!"
                else:
                    winnings = -amount
                    new_balance = data["balance"] + winnings
                    result = f"You lost! The ball landed on **{win_color}**. You lost **{amount}** coins."
                await self.update_user(user.id, balance=new_balance)
                embed = discord.Embed(
                    title="Roulette",
                    description=result,
                    color=0xd0b47b
                )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- CRIME ---
    @commands.command(name="crime")
    @cooldown(1, 180, BucketType.user)
    async def crime_command(self, ctx):
        await self.crime(ctx.author, ctx)

    @app_commands.command(name="crime", description="Commit a crime for a chance at coins.")
    async def crime_slash(self, interaction: discord.Interaction):
        await self.crime(interaction.user, interaction)

    async def crime(self, user, destination):
        data = await self.get_user(user.id)
        result = random.choice(CRIME_REWARDS)
        new_balance = max(0, data["balance"] + result["amount"])
        await self.update_user(user.id, balance=new_balance)
        embed = discord.Embed(
            title="Crime",
            description=f"{result['desc']} {'You gained' if result['amount'] > 0 else 'You lost'} **{abs(result['amount'])}** coins!",
            color=0xd0b47b
        )
        log_econ_action("crime", user, amount=result["amount"], extra=result["desc"])
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK HEIST ---
    @commands.command(name="bankheist")
    @cooldown(1, 300, BucketType.user)
    async def bankheist_command(self, ctx, amount: int):
        await self.bankheist(ctx.author, amount, ctx)

    @app_commands.command(name="bankheist", description="Attempt a risky bank heist for big rewards!")
    @app_commands.describe(amount="How much to risk from your bank")
    async def bankheist_slash(self, interaction: discord.Interaction, amount: int):
        await self.bankheist(interaction.user, amount, interaction)

    async def bankheist(self, user, amount, destination):
        data = await self.get_user(user.id)
        if amount <= 0 or data["bank"] < amount:
            embed = discord.Embed(
                title="Bank Heist",
                description="Invalid amount or insufficient bank funds.",
                color=0xd0b47b
            )
            log_econ_action("bankheist_fail", user, amount=amount)
        else:
            success = random.random() < 0.3  # 30% chance to succeed
            if success:
                winnings = amount * 2
                await self.update_user(user.id, bank=data["bank"] - amount, balance=data["balance"] + winnings)
                embed = discord.Embed(
                    title="Bank Heist",
                    description=f"You pulled off the heist and got **{winnings}** coins!",
                    color=0xd0b47b
                )
                log_econ_action("bankheist", user, amount=winnings)
            else:
                await self.update_user(user.id, bank=data["bank"] - amount)
                embed = discord.Embed(
                    title="Bank Heist",
                    description=f"You got caught! You lost **{amount}** coins from your bank.",
                    color=0xd0b47b
                )
                log_econ_action("bankheist_fail", user, amount=amount)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ERROR HANDLER FOR COOLDOWNS ---
    @work_command.error
    @fish_command.error
    @crime_command.error
    @bankheist_command.error
    @rob_command.error
    async def cooldown_error(self, ctx, error):
        if isinstance(error, CommandOnCooldown):
            seconds = int(error.retry_after)
            minutes, seconds = divmod(seconds, 60)
            msg = f"⏳ You're on cooldown! Try again in {minutes}m {seconds}s."
            if hasattr(ctx, "response"):
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.send(msg)
        else:
            raise error

    # --- BUY ---
    @commands.command(name="buy")
    async def buy_command(self, ctx, item: str, amount: int = 1):
        await self.buy(ctx.author, item.lower(), amount, ctx)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(item="The item to buy", amount="How many to buy")
    async def buy_slash(self, interaction: discord.Interaction, item: str, amount: int = 1):
        await self.buy(interaction.user, item.lower(), amount, interaction)

    async def buy(self, user, item, amount, destination):
        if item not in SHOP_ITEMS:
            embed = discord.Embed(
                title="Buy",
                description="That item doesn't exist in the shop.",
                color=0xd0b47b
            )
            log_econ_action("buy_fail", user, item=item, extra="Not in shop")
        elif amount <= 0:
            embed = discord.Embed(
                title="Buy",
                description="Amount must be at least 1.",
                color=0xd0b47b
            )
            log_econ_action("buy_fail", user, item=item, extra="Invalid amount")
        else:
            price = SHOP_ITEMS[item]["price"]
            total_cost = price * amount
            data = await self.get_user(user.id)
            if data["balance"] < total_cost:
                embed = discord.Embed(
                    title="Buy",
                    description=f"You don't have enough coins. You need **{total_cost}** coins.",
                    color=0xd0b47b
                )
                log_econ_action("buy_fail", user, item=item, amount=total_cost, extra="Insufficient funds")
            else:
                await self.update_user(user.id, balance=data["balance"] - total_cost)
                await self.add_item(user.id, item, amount)
                embed = discord.Embed(
                    title="Buy",
                    description=f"You bought **{amount} {item.title()}** for **{total_cost}** coins!",
                    color=0xd0b47b
                )
                log_econ_action("buy", user, amount=total_cost, item=item, extra=f"Quantity: {amount}")
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- WITHDRAW ---
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw_command(self, ctx, amount: int):
        await self.withdraw(ctx.author, amount, ctx)

    @app_commands.command(name="withdraw", description="Withdraw coins from your bank to your wallet.")
    @app_commands.describe(amount="Amount to withdraw")
    async def withdraw_slash(self, interaction: discord.Interaction, amount: int):
        await self.withdraw(interaction.user, amount, interaction)

    async def withdraw(self, user, amount, destination):
        data = await self.get_user(user.id)
        if amount <= 0 or data["bank"] < amount:
            embed = discord.Embed(
                title="Withdraw",
                description="Invalid amount or insufficient bank funds.",
                color=0xd0b47b
            )
            log_econ_action("withdraw_fail", user, amount=amount)
        else:
            await self.update_user(user.id, balance=data["balance"] + amount, bank=data["bank"] - amount)
            embed = discord.Embed(
                title="Withdraw",
                description=f"You withdrew **{amount}** coins from your bank to your wallet.",
                color=0x00bfae
            )
            log_econ_action("withdraw", user, amount=amount)
        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ENSURE ONLY WALLET IS USED FOR SPENDING ---
    # In all commands that spend coins (buy, bet, crime, rob, etc.), always use data["balance"] (wallet) only.
    # No changes needed if you already use data["balance"] for all spending checks and updates.

def get_shop_embed(page=1):
    items = list(SHOP_ITEMS.items())
    total_pages = max(1, math.ceil(len(items) / SHOP_ITEMS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * SHOP_ITEMS_PER_PAGE
    end = start + SHOP_ITEMS_PER_PAGE
    embed = discord.Embed(
        title=f"Shop (Page {page}/{total_pages})",
        color=0xd0b47b
    )
    for name, data in items[start:end]:
        embed.add_field(
            name=f"{name.title()} — {data['price']} coins",
            value=data['desc'],
            inline=False
        )
    embed.set_footer(text="Use !buy <item> <amount> or /buy to purchase. Use !shop <page> to view more.")
    return embed

class ShopView(discord.ui.View):
    def __init__(self, page=1):
        super().__init__(timeout=60)
        self.page = page

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
            embed = get_shop_embed(self.page)
            await interaction.response.edit_message(embed=embed, view=ShopView(page=self.page))
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = list(SHOP_ITEMS.items())
        total_pages = max(1, math.ceil(len(items) / SHOP_ITEMS_PER_PAGE))
        if self.page < total_pages:
            self.page += 1
            embed = get_shop_embed(self.page)
            await interaction.response.edit_message(embed=embed, view=ShopView(page=self.page))
        else:
            await interaction.response.defer()

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))