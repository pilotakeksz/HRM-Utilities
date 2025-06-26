import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.getenv("ECONOMY_DB_FILE", "data/economy.db")
DAILY_AMOUNT = int(os.getenv("DAILY_AMOUNT", 250))
BANK_INTEREST = 0.01  # 1% daily interest, can be made dynamic per-role
ROULETTE_COLORS = {"red": 2, "black": 2, "green": 14}

WORK_RESPONSES = [
    "You worked as a **Barista** and earned",
    "You delivered **Pizza** and earned",
    "You walked a **Dog** and earned",
    "You mowed a **Lawn** and earned",
    "You washed a **Car** and earned",
    "You coded a **Website** and earned",
    "You painted a **Fence** and earned",
    "You helped at a **Bakery** and earned",
    "You tutored a **Student** and earned",
    "You cleaned a **Pool** and earned",
    "You worked as a **Cashier** and earned",
    "You fixed a **Bike** and earned",
    "You organized a **Garage** and earned",
    "You delivered **Groceries** and earned",
    "You worked as a **Receptionist** and earned"
]

SHOP_ITEMS = {
    "can of tuna": {"price": 50, "desc": "A delicious can of tuna."},
    "fish": {"price": 100, "desc": "A fresh fish."},
    "plane": {"price": 5000, "desc": "A private plane."},
    "skittles": {"price": 25, "desc": "Taste the rainbow!"},
    "banana": {"price": 15, "desc": "A slippery snack."},
    "beanbag chair": {"price": 200, "desc": "Perfect for chilling."},
    "toy sword": {"price": 100, "desc": "Not very sharp, but it looks cool."},
    "cursed amulet": {"price": 400, "desc": "Gives mysterious powers."},
    "RC car": {"price": 300, "desc": "Zoom around and annoy your friends."},
    "lava lamp": {"price": 150, "desc": "Groovy vibes in a bottle."},
    "invisibility cloak": {"price": 2500, "desc": "Totally real and not just a bedsheet."},
    "rubber duck": {"price": 10, "desc": "Squeaky and suspiciously judgmental."},
    "wifi booster": {"price": 800, "desc": "Steal signals from across the street."},
    "golden shovel": {"price": 450, "desc": "For digging... or flexing."},
    "keyboard cleaner": {"price": 75, "desc": "Because your crimes are dirty."},
    "fake mustache": {"price": 60, "desc": "Instant disguise, 60% effective."},
    "alien plushie": {"price": 130, "desc": "It's watching you. Always."},
    "time machine manual": {"price": 9999, "desc": "Too bad the machine's sold separately."},
}

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
    {"desc": "You got caught by mall security.", "amount": -120},
    {"desc": "You slipped while running from the scene.", "amount": -100},
    {"desc": "You accidentally robbed a police fundraiser.", "amount": -200},
    {"desc": "You tripped the alarm while escaping.", "amount": -150},
    {"desc": "You panicked and gave the money back.", "amount": -90}
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
            amount = round(random.randint(50, 500) / 5) * 5
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

    # --- STORE ---
    @commands.command(name="shop")
    async def shop_command(self, ctx):
        await self.shop(ctx)

    @app_commands.command(name="shop", description="View the item shop.")
    async def shop_slash(self, interaction: discord.Interaction):
        await self.shop(interaction)

    async def shop(self, destination):
        embed = discord.Embed(
            title="🛒 Item Shop",
            color=0xd0b47b
        )
        for item, info in SHOP_ITEMS.items():
            embed.add_field(name=f"{item.title()} - {info['price']} coins", value=info["desc"], inline=False)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- ROULETTE ---
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

    # --- CRIME ---
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
            guild = None
            if hasattr(destination, "guild"):
                guild = destination.guild
            elif hasattr(destination, "guild_id"):
                guild = self.bot.get_guild(destination.guild_id)
            if guild:
                member = guild.get_member(user.id)
                if member:
                    for role in member.roles:
                        if role.name.lower().startswith("daily"):
                            bonus += 50  # Example: +50 per daily role
            total = DAILY_AMOUNT + bonus
            new_balance = data["balance"] + total
            await self.update_user(user.id, balance=new_balance, last_daily=now.isoformat())
            embed = discord.Embed(
                title="Daily Reward",
                description=f"You claimed your daily and received **{DAILY_AMOUNT}** coins!{' Bonus: ' + str(bonus) if bonus else ''}",
                color=0xd0b47b
            )
            log_econ_action("daily", user, amount=total)
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
        embed = discord.Embed(
            title=f"{user.name}'s Bank",
            description=f"🏦 Bank Balance: **{data['bank']}** coins\nInterest Rate: **{BANK_INTEREST*100:.2f}%** per day",
            color=0xd0b47b
        )
        log_econ_action("bank", user)
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # --- BANK INTEREST (run daily, example only) ---
    async def apply_bank_interest(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET bank = bank + CAST(bank * ? AS INTEGER)", (BANK_INTEREST,)
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

    # --- BANK HEIST (simple version) ---
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))