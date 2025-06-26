import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
from datetime import datetime, timedelta
import math

DB_PATH = os.getenv("ECONOMY_DB_FILE", "data/economy.db")
DAILY_AMOUNT = int(os.getenv("DAILY_AMOUNT", 250))
BANK_ROLE_TIERS = [
    (1329910391840702515, 0.02),  # Highest role, 2%
    (1329910389437104220, 0.015), # Middle role, 1.5%
    (1329910329701830686, 0.01),  # Lowest role, 1%
]
SHOP_ITEMS_PER_PAGE = 5

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
    "You worked as a mascot 🦁 and earned"
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

class ShopView(discord.ui.View):
    def __init__(self, page=1):
        super().__init__(timeout=60)
        self.page = page

    async def update(self, interaction, page):
        self.page = page
        embed = get_shop_embed(page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            await self.update(interaction, self.page - 1)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = math.ceil(len(SHOP_ITEMS) / SHOP_ITEMS_PER_PAGE)
        if self.page < max_page:
            await self.update(interaction, self.page + 1)
        else:
            await interaction.response.defer()

def get_shop_embed(page=1):
    embed = discord.Embed(
        title="🛒 Item Shop",
        color=0xd0b47b
    )
    items = list(SHOP_ITEMS.items())
    max_page = max(1, math.ceil(len(items) / SHOP_ITEMS_PER_PAGE))
    page = max(1, min(page, max_page))
    start = (page - 1) * SHOP_ITEMS_PER_PAGE
    end = start + SHOP_ITEMS_PER_PAGE
    for item, info in items[start:end]:
        embed.add_field(name=f"{item.title()} - {info['price']} coins", value=info["desc"], inline=False)
    embed.set_footer(text=f"Page {page}/{max_page}")
    return embed

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item TEXT,
                    amount INTEGER,
                    PRIMARY KEY (user_id, item)
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

    async def add_item(self, user_id, item, amount):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
            row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE inventory SET amount = amount + ? WHERE user_id = ? AND item = ?", (amount, user_id, item))
            else:
                await db.execute("INSERT INTO inventory (user_id, item, amount) VALUES (?, ?, ?)", (user_id, item, amount))
            await db.commit()

    async def get_inventory(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT item, amount FROM inventory WHERE user_id = ?", (user_id,))
            return await cursor.fetchall()

    # --- WORK ---
    @commands.command(name="work")
    async def work_command(self, ctx):
        await self._work(ctx.author, ctx)

    @app_commands.command(name="work", description="Work a random job for coins (2 min cooldown).")
    async def work_slash(self, interaction: discord.Interaction):
        await self._work(interaction.user, interaction)

    async def _work(self, user, destination):
        data = await self.get_user(user.id)
        now = datetime.utcnow()
        last_work = datetime.fromisoformat(data["last_work"]) if data["last_work"] else None
        cooldown_seconds = 120
        if last_work and (now - last_work) < timedelta(seconds=cooldown_seconds):
            next_time = last_work + timedelta(seconds=cooldown_seconds)
            delta = next_time - now
            minutes, seconds = divmod(delta.seconds, 60)
            embed = discord.Embed(
                title="Work",
                description=f"You're tired! Try again in {minutes}m {seconds}s.",
                color=0xd0b47b
            )
            log_econ_action("work_fail", user, extra=f"Cooldown {minutes}m {seconds}s")
        else:
            amount = round(random.randint(5, 500) / 5) * 5
            job_response = random.choice(WORK_RESPONSES)
            new_balance = data["balance"] + amount
            await self.update_user(user.id, balance=new_balance, last_work=now.isoformat())
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
    async def fish_command(self, ctx):
        await self.fish(ctx.author, ctx)

    @app_commands.command(name="fish", description="Go fishing for a random fish or junk!")
    async def fish_slash(self, interaction: discord.Interaction):
        await self.fish(interaction.user, interaction)

    async def fish(self, user, destination):
        # 80% chance fish, 20% junk
        if random.random() < 0.8:
            fish = random.choice(FISH_TYPES)
            value = round(random.randint(100, 1000) / 5) * 5
        else:
            fish = random.choice(JUNK_TYPES)
            value = 1
        await self.add_item(user.id, fish, 1)
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
        items = dict(await self.get_inventory(user.id))
        if item not in SHOP_ITEMS:
            embed = discord.Embed(
                title="Sell",
                description="That item doesn't exist.",
                color=0xd0b47b
            )
            log_econ_action("sell_fail", user, item=item)
        elif items.get(item, 0) < 1:
            embed = discord.Embed(
                title="Sell",
                description=f"You don't have any **{item.title()}** to sell.",
                color=0xd0b47b
            )
            log_econ_action("sell_fail", user, item=item, extra="No items")
        else:
            sell_amount = min(amount, items[item])
            price = SHOP_ITEMS[item]["price"]
            total = price * sell_amount
            data = await self.get_user(user.id)
            await self.add_item(user.id, item, -sell_amount)
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

    # --- SELL ALL FISH/JUNK ---
    @commands.command(name="sellallfish")
    async def sellallfish_command(self, ctx):
        await self.sell_all_fish(ctx.author, ctx)

    @app_commands.command(name="sellallfish", description="Sell all fish and junk items in your inventory.")
    async def sellallfish_slash(self, interaction: discord.Interaction):
        await self.sell_all_fish(interaction.user, interaction)

    async def sell_all_fish(self, user, destination):
        inventory = dict(await self.get_inventory(user.id))
        fish_types = FISH_TYPES + JUNK_TYPES
        total_earned = 0
        sold_items = []
        for item in fish_types:
            amount = inventory.get(item, 0)
            if amount > 0 and item in SHOP_ITEMS:
                price = SHOP_ITEMS[item]["price"]
                earned = price * amount
                await self.add_item(user.id, item, -amount)
                data = await self.get_user(user.id)
                await self.update_user(user.id, balance=data["balance"] + earned)
                total_earned += earned
                sold_items.append(f"**{item.title()}** x{amount} (**{earned}** coins)")
                log_econ_action("sell-all-fish", user, amount=earned, item=item, extra=f"Quantity: {amount}")
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
    async def crime_command(self, ctx):
        await self.crime(ctx.author, ctx)

    @app_commands.command(name="crime", description="Commit a crime for a chance at coins.")
    async def crime_slash(self, interaction: discord.Interaction):
        await self.crime(interaction.user, interaction)

    async def crime(self, user, destination):
        result = random.choice([
            {"desc": "You hacked a vending machine!", "amount": 200},
            {"desc": "You stole a bike!", "amount": 150},
            {"desc": "You robbed a lemonade stand!", "amount": 100},
            {"desc": "You failed and paid a fine.", "amount": -100},
            {"desc": "You got caught and paid bail.", "amount": -200},
            {"desc": "You spray painted a wall!", "amount": 120},
            {"desc": "You jaywalked across a busy street!", "amount": 80},
            {"desc": "You pickpocketed a tourist!", "amount": 140},
            {"desc": "You snuck into a movie theater!", "amount": 90},
            {"desc": "You ran an illegal lemonade stand!", "amount": 110},
            {"desc": "You cheated at cards in a back alley!", "amount": 160},
            {"desc": "You hacked a claw machine!", "amount": 130},
            {"desc": "You tricked someone with a fake raffle!", "amount": 170},
            {"desc": "You faked a talent show act for tips!", "amount": 100},
            {"desc": "You shoplifted a candy bar!", "amount": 70},
            {"desc": "You pretended to be a parking inspector!", "amount": 150},
            {"desc": "You ran a fake car wash scam!", "amount": 180},
            {"desc": "You siphoned Wi-Fi from your neighbor!", "amount": 90},
            {"desc": "You resold school lunch tickets!", "amount": 110},
            {"desc": "You forged a library card!", "amount": 60},
            {"desc": "You got caught by mall security.", "amount": -120},
            {"desc": "You slipped while running from the scene.", "amount": -100},
            {"desc": "You accidentally robbed a police fundraiser.", "amount": -200},
            {"desc": "You tripped the alarm while escaping.", "amount": -150},
            {"desc": "You panicked and gave the money back.", "amount": -90}
        ])
        data = await self.get_user(user.id)
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

    # --- DAILY ---
    @commands.command(name="daily")
    async def daily_command(self, ctx):
        await self.daily(ctx.author, ctx)

    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily_slash(self, interaction: discord.Interaction):
        await self.daily(interaction.user, interaction)

    async def daily(self, user, destination):
        data = await self.get_user(user.id)
        now = datetime.utcnow()
        last_daily = datetime.fromisoformat(data["last_daily"]) if data["last_daily"] else None
        if last_daily and (now - last_daily) < timedelta(hours=24):
            next_time = last_daily + timedelta(hours=24)
            delta = next_time - now
            embed = discord.Embed(
                title="Daily Reward",
                description=f"You've already claimed your daily! Come back in {delta.seconds // 3600}h {(delta.seconds // 60) % 60}m.",
                color=0xd0b47b
            )
            log_econ_action("daily_fail", user, extra=f"Cooldown {delta}")
        else:
            # Daily roles bonus
            bonus = 0
            bonus_details = []
            guild = None
            if hasattr(destination, "guild"):
                guild = destination.guild
            elif hasattr(destination, "guild_id"):
                guild = self.bot.get_guild(destination.guild_id)
            if guild:
                member = guild.get_member(user.id)
                if member:
                    for role_id, role_bonus in BANK_ROLE_TIERS:
                        role = guild.get_role(role_id)
                        if role and role in member.roles:
                            bonus += 50
                            bonus_details.append(f"{role.name}: +50 coins")
            total = DAILY_AMOUNT + bonus
            new_balance = data["balance"] + total
            await self.update_user(user.id, balance=new_balance, last_daily=now.isoformat())
            bonus_str = "\n".join(bonus_details) if bonus_details else "No daily bonus roles."
            embed = discord.Embed(
                title="Daily Reward",
                description=f"You claimed your daily and received **{DAILY_AMOUNT}** coins!\n{bonus_str}",
                color=0xd0b47b
            )
            log_econ_action("daily", user, amount=total, extra=bonus_str)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK ---
    @commands.command(name="bank")
    async def bank_command(self, ctx):
        await self.bank(ctx.author, ctx)

    @app_commands.command(name="bank", description="View your bank balance and interest.")
    async def bank_slash(self, interaction: discord.Interaction):
        await self.bank(interaction.user, interaction)

    async def bank(self, user, destination):
        data = await self.get_user(user.id)
        interest = self.get_bank_interest(user)
        embed = discord.Embed(
            title=f"{user.name}'s Bank",
            description=f"🏦 Bank Balance: **{data['bank']}** coins\nInterest Rate: **{interest*100:.2f}%** per day",
            color=0xd0b47b
        )
        log_econ_action("bank", user)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- DEPOSIT ---
    @commands.command(name="deposit")
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
                description="Invalid amount or insufficient funds.",
                color=0xd0b47b
            )
            log_econ_action("deposit_fail", user, amount=amount)
        else:
            await self.update_user(user.id, balance=data["balance"] - amount, bank=data["bank"] + amount)
            embed = discord.Embed(
                title="Deposit",
                description=f"You deposited **{amount}** coins into your bank.",
                color=0xd0b47b
            )
            log_econ_action("deposit", user, amount=amount)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- INTEREST ---
    async def apply_bank_interest(self):
        async with aiosqlite.connect(DB_PATH) as db:
            for role_id, interest in BANK_ROLE_TIERS:
                await db.execute(
                    f"UPDATE users SET bank = bank + CAST(bank * {interest} AS INTEGER) WHERE user_id IN (SELECT user_id FROM users)"
                )
            await db.commit()

    # --- ROB ---
    @commands.command(name="rob")
    async def rob_command(self, ctx, target: discord.Member):
        await self.rob(ctx.author, target, ctx)

    @app_commands.command(name="rob", description="Try to rob another user.")
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
                    description="Target doesn't have enough coins to rob!",
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
                        description=f"You robbed {target.mention} and stole **{stolen}** coins!",
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
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK HEIST ---
    @commands.command(name="bankheist")
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

    # --- LEADERBOARD ---
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard_command(self, ctx):
        await self.leaderboard(ctx)

    @app_commands.command(name="leaderboard", description="Show the top 10 richest users.")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await self.leaderboard(interaction)

    async def leaderboard(self, destination):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
            )
            top_users = await cursor.fetchall()
        embed = discord.Embed(
            title="🏆 Economy Leaderboard",
            description="Top 10 richest users 💰",
            color=0xf1c40f
        )
        if not top_users:
            embed.description = "No users found."
        else:
            medals = ["🥇", "🥈", "🥉"] + ["💸"] * 7
            lines = []
            for idx, (user_id, balance) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id)
                name = user.mention if user else f"User ID {user_id}"
                medal = medals[idx - 1] if idx <= len(medals) else ""
                lines.append(f"{medal} **#{idx}** {name} — **{balance}** coins")
            embed.add_field(name="Ranks", value="\n".join(lines), inline=False)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ECONOMY LEADERBOARD ---
    @commands.command(name="eclb", aliases=["ecotop", "ecolb", "ecoinlb", "ecoinleaderboard", "eco-lb"])
    async def eclb_command(self, ctx):
        await self.eclb(ctx)

    @app_commands.command(name="eclb", description="Show the top 10 richest users (economy).")
    async def eclb_slash(self, interaction: discord.Interaction):
        await self.eclb(interaction)

    async def eclb(self, destination):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
            )
            top_users = await cursor.fetchall()
        embed = discord.Embed(
            title="🏆 Economy Leaderboard",
            description="Top 10 richest users 💰",
            color=0xf1c40f
        )
        if not top_users:
            embed.description = "No users found." #test
        else:
            medals = ["🥇", "🥈", "🥉"] + ["💸"] * 7
            lines = []
            for idx, (user_id, balance) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id)
                name = user.mention if user else f"User ID {user_id}"
                medal = medals[idx - 1] if idx <= len(medals) else ""
                lines.append(f"{medal} **#{idx}** {name} — **{balance}** coins")
            embed.add_field(name="Ranks", value="\n".join(lines), inline=False)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))