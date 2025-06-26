import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import os
import random
import math
from datetime import datetime, timedelta
from discord.ui import View, Button
from typing import Optional

DB_PATH = os.getenv("ECONOMY_DB_FILE", "data/economy.db")
DAILY_AMOUNT = int(os.getenv("DAILY_AMOUNT", 250))
WORK_BASE = int(os.getenv("WORK_BASE", 100))
WORK_INCREMENT = int(os.getenv("WORK_INCREMENT", 50))
ROLES_INCOME = [
    (1329910391840702515, 100),  # Highest role, highest income
    (1329910389437104220, 75),
    (1329910329701830686, 50),   # Lowest role, lowest income
]

ITEMS_FILE = os.path.join(os.path.dirname(__file__), "econ", "items.txt")

SHOP_ITEMS_PER_PAGE = 5

def load_shop_items():
    items = {}
    if not os.path.exists(ITEMS_FILE):
        return items
    with open(ITEMS_FILE, "r", encoding="utf-8") as f:
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

CRIME_REWARDS = [
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

# Failed attempts:
    {"desc": "You got caught by mall security.", "amount": -120},
    {"desc": "You slipped while running from the scene.", "amount": -100},
    {"desc": "You accidentally robbed a police fundraiser.", "amount": -200},
    {"desc": "You tripped the alarm while escaping.", "amount": -150},
    {"desc": "You panicked and gave the money back.", "amount": -90}

]

ROULETTE_COLORS = {
    "red": 2,
    "black": 2,
    "green": 14
}

class ShopView(View):
    def __init__(self, page=1):
        super().__init__(timeout=60)
        self.page = page

    async def update(self, interaction, page):
        self.page = page
        embed = get_shop_embed(page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, button: Button):
        if self.page > 1:
            await self.update(interaction, self.page - 1)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, button: Button):
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

class SellItemAutocomplete(discord.app_commands.Transformer):
    async def autocomplete(self, interaction: discord.Interaction, current: str):
        items = await interaction.client.get_cog("Economy").get_inventory(interaction.user.id)
        return [
            app_commands.Choice(name=f"{item.title()} ({amount})", value=item)
            for item, amount in items
            if current.lower() in item.lower()
        ][:25]

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_lock = asyncio.Lock()

    async def cog_load(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL,
                    last_daily TEXT,
                    last_work TEXT
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
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT balance, last_daily, last_work FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row:
                    return {"balance": row[0], "last_daily": row[1], "last_work": row[2]}
                else:
                    await db.execute("INSERT INTO users (user_id, balance, last_daily, last_work) VALUES (?, ?, ?, ?)", (user_id, 0, None, None))
                    await db.commit()
                    return {"balance": 0, "last_daily": None, "last_work": None}

    async def update_user(self, user_id, balance=None, last_daily=None, last_work=None):
        user = await self.get_user(user_id)
        balance = balance if balance is not None else user["balance"]
        last_daily = last_daily if last_daily is not None else user["last_daily"]
        last_work = last_work if last_work is not None else user["last_work"]
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET balance = ?, last_daily = ?, last_work = ? WHERE user_id = ?",
                    (balance, last_daily, last_work, user_id)
                )
                await db.commit()

    async def add_item(self, user_id, item, amount):
        async with self.db_lock:
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

    def get_role_income(self, member: discord.Member):
        for role_id, income in ROLES_INCOME:
            if discord.utils.get(member.roles, id=role_id):
                return income
        return 0

    @commands.command(name="balance", aliases=["bal"])
    async def balance_command(self, ctx):
        await self.send_balance_embed(ctx.author, ctx)

    @app_commands.command(name="balance", description="Check your balance.")
    async def balance_slash(self, interaction: discord.Interaction):
        await self.send_balance_embed(interaction.user, interaction)

    async def send_balance_embed(self, user, destination):
        data = await self.get_user(user.id)
        embed = discord.Embed(
            title=f"{user.name}'s Balance",
            description=f"💰 Balance: **{data['balance']}** coins",
            color=0xd0b47b
        )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

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
        else:
            new_balance = data["balance"] + DAILY_AMOUNT
            await self.update_user(user.id, balance=new_balance, last_daily=now.isoformat())
            embed = discord.Embed(
                title="Daily Reward",
                description=f"You claimed your daily and received **{DAILY_AMOUNT}** coins!",
                color=0xd0b47b
            )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="work")
    async def work_command(self, ctx):
        await self.work(ctx.author, ctx)

    @app_commands.command(name="work", description="Work a job for coins.")
    async def work_slash(self, interaction: discord.Interaction):
        await self.work(interaction.user, interaction)

    async def work(self, user, destination):
        data = await self.get_user(user.id)
        now = datetime.utcnow()
        last_work = datetime.fromisoformat(data["last_work"]) if data["last_work"] else None
        if last_work and (now - last_work) < timedelta(minutes=30):
            next_time = last_work + timedelta(minutes=30)
            delta = next_time - now
            embed = discord.Embed(
                title="Work",
                description=f"You are tired! Try again in {delta.seconds // 60}m.",
                color=0xd0b47b
            )
        else:
            # Progressive work: earn more as you work more
            work_count = (now - datetime(2020, 1, 1)).days  # Just a dummy progressive factor
            amount = WORK_BASE + (work_count % 10) * WORK_INCREMENT
            # Add role income
            if isinstance(user, discord.Member):
                amount += self.get_role_income(user)
            new_balance = data["balance"] + amount
            await self.update_user(user.id, balance=new_balance, last_work=now.isoformat())
            embed = discord.Embed(
                title="Work",
                description=f"You worked hard and earned **{amount}** coins!",
                color=0xd0b47b
            )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

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
        else:
            user_data = await self.get_user(user.id)
            target_data = await self.get_user(target.id)
            if target_data["balance"] < 100:
                embed = discord.Embed(
                    title="Rob",
                    description="Target doesn't have enough coins to rob!",
                    color=0xd0b47b
                )
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
                else:
                    loss = random.randint(20, 100)
                    await self.update_user(user.id, balance=max(0, user_data["balance"] - loss))
                    embed = discord.Embed(
                        title="Rob",
                        description=f"You got caught and lost **{loss}** coins!",
                        color=0xd0b47b
                    )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="crime")
    async def crime_command(self, ctx):
        await self.crime(ctx.author, ctx)

    @app_commands.command(name="crime", description="Commit a crime for a chance at coins.")
    async def crime_slash(self, interaction: discord.Interaction):
        await self.crime(interaction.user, interaction)

    async def crime(self, user, destination):
        result = random.choice(CRIME_REWARDS)
        data = await self.get_user(user.id)
        new_balance = max(0, data["balance"] + result["amount"])
        await self.update_user(user.id, balance=new_balance)
        embed = discord.Embed(
            title="Crime",
            description=f"{result['desc']} {'You gained' if result['amount'] > 0 else 'You lost'} **{abs(result['amount'])}** coins!",
            color=0xd0b47b
        )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="shop")
    async def shop_command(self, ctx):
        await self.shop(ctx)

    @app_commands.command(name="shop", description="View the item shop.")
    async def shop_slash(self, interaction: discord.Interaction):
        await self.shop(interaction)

    async def shop(self, destination):
        embed = get_shop_embed(page=1)
        view = ShopView(page=1)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed, view=view)
        else:
            await destination.send(embed=embed, view=view)

    @commands.command(name="buy")
    async def buy_command(self, ctx, *, item: str):
        await self.buy(ctx.author, item.lower(), ctx)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(item="The item to buy")
    async def buy_slash(self, interaction: discord.Interaction, item: str):
        await self.buy(interaction.user, item.lower(), interaction)

    async def buy(self, user, item, destination):
        if item not in SHOP_ITEMS:
            embed = discord.Embed(
                title="Shop",
                description="That item doesn't exist.",
                color=0xd0b47b
            )
        else:
            data = await self.get_user(user.id)
            price = SHOP_ITEMS[item]["price"]
            if data["balance"] < price:
                embed = discord.Embed(
                    title="Shop",
                    description="You don't have enough coins.",
                    color=0xd0b47b
                )
            else:
                await self.update_user(user.id, balance=data["balance"] - price)
                await self.add_item(user.id, item, 1)
                embed = discord.Embed(
                    title="Shop",
                    description=f"You bought a **{item}**!",
                    color=0xd0b47b
                )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory_command(self, ctx):
        await self.inventory(ctx.author, ctx)

    @app_commands.command(name="inventory", description="View your inventory.")
    async def inventory_slash(self, interaction: discord.Interaction):
        await self.inventory(interaction.user, interaction)

    async def inventory(self, user, destination):
        items = await self.get_inventory(user.id)
        if not items:
            desc = "Your inventory is empty."
        else:
            desc = "\n".join([f"**{item.title()}** x{amount}" for item, amount in items])
        embed = discord.Embed(
            title=f"{user.name}'s Inventory",
            description=desc,
            color=0xd0b47b
        )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="roulette")
    async def roulette_command(self, ctx, color: str, amount: int):
        await self.roulette(ctx.author, color.lower(), amount, ctx)

    @app_commands.command(name="roulette", description="Bet on roulette (red, black, green).")
    @app_commands.describe(color="Color to bet on", amount="Amount to bet")
    async def roulette_slash(self, interaction: discord.Interaction, color: str, amount: int):
        await self.roulette(interaction.user, color.lower(), amount, interaction)

    async def roulette(self, user, color, amount, destination):
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

    @commands.command(name="econleaderboard", aliases=["ecoinlb", "ecoinleaderboard", "eco-lb"])
    async def econ_leaderboard_command(self, ctx):
        await self.econ_leaderboard(ctx)

    @app_commands.command(name="econleaderboard", description="Show the top 10 richest users.")
    async def econ_leaderboard_slash(self, interaction: discord.Interaction):
        await self.econ_leaderboard(interaction)

    async def econ_leaderboard(self, destination):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
            )
            top_users = await cursor.fetchall()
        embed = discord.Embed(
            title="💰 Economy Leaderboard",
            description="Top 10 richest users",
            color=0xd0b47b
        )
        if not top_users:
            embed.description = "No users found."
        else:
            lines = []
            for idx, (user_id, balance) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id)
                name = user.mention if user else f"User ID {user_id}"
                lines.append(f"**#{idx}** {name} — **{balance}** coins")
            embed.add_field(name="Ranks", value="\n".join(lines), inline=False)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="fish")
    async def fish_command(self, ctx):
        await self.fish(ctx.author, ctx)

    @app_commands.command(name="fish", description="Go fishing for a chance to catch and sell fish!")
    async def fish_slash(self, interaction: discord.Interaction):
        await self.fish(interaction.user, interaction)

    async def fish(self, user, destination):
        # Check if user has a "fish" in inventory (optional: require a fishing rod or bait)
        catch_chance = random.random()
        if catch_chance < 0.7:
            # Caught a fish!
            await self.add_item(user.id, "fish", 1)
            embed = discord.Embed(
                title="🎣 Fishing",
                description="You cast your line and caught a **fish**! Use `/sell fish` or `!sell fish` to sell it.",
                color=0xd0b47b
            )
        else:
            embed = discord.Embed(
                title="🎣 Fishing",
                description="You didn't catch anything this time. Try again later!",
                color=0xd0b47b
            )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="sell")
    async def sell_command(self, ctx, item: str, amount: Optional[int] = 1):
        await self.sell(ctx.author, item.lower(), amount, ctx)

    @app_commands.command(name="sell", description="Sell an item from your inventory.")
    @app_commands.describe(item="The item to sell", amount="How many to sell")
    @app_commands.autocomplete(item=SellItemAutocomplete().autocomplete)
    async def sell_slash(self, interaction: discord.Interaction, item: str, amount: Optional[int] = 1):
        await self.sell(interaction.user, item.lower(), amount, interaction)

    async def sell(self, user, item, amount, destination):
        items = dict(await self.get_inventory(user.id))
        if item not in SHOP_ITEMS:
            embed = discord.Embed(
                title="Sell",
                description="That item doesn't exist.",
                color=0xd0b47b
            )
        elif items.get(item, 0) < 1:
            embed = discord.Embed(
                title="Sell",
                description=f"You don't have any **{item.title()}** to sell.",
                color=0xd0b47b
            )
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
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))