import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import datetime
import asyncio

INFRACTION_DB = "data/infractions.db"
CASE_ID_FILE = "data/infraction_case_id.txt"
LOG_DIR = "logs"

INFRACTION_CHANNEL_ID = int(os.getenv("INFRACTION_CHANNEL_ID"))
INFRACTION_LOG_CHANNEL_ID = int(os.getenv("INFRACTION_LOG_CHANNEL_ID"))
PERSONNEL_ROLE_ID = int(os.getenv("PERSONNEL_ROLE_ID"))
INFRACTION_PERMISSIONS_ROLE_ID = int(os.getenv("INFRACTION_PERMISSIONS_ROLE_ID"))
WARNING_1_ROLE_ID = int(os.getenv("WARNING_1_ROLE_ID"))
WARNING_2_ROLE_ID = int(os.getenv("WARNING_2_ROLE_ID"))
STRIKE_1_ROLE_ID = int(os.getenv("STRIKE_1_ROLE_ID"))
STRIKE_2_ROLE_ID = int(os.getenv("STRIKE_2_ROLE_ID"))
STRIKE_3_ROLE_ID = int(os.getenv("STRIKE_3_ROLE_ID"))
SUSPENDED_ROLE_ID = int(os.getenv("SUSPENDED_ROLE_ID"))

INFRACTION_TYPES = {
    "Warning": {"color": discord.Color.yellow(), "roles": [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]},
    "Strike": {"color": discord.Color.orange(), "roles": [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID]},
    "Demotion": {"color": discord.Color.red(), "roles": []},
    "Termination": {"color": discord.Color.dark_red(), "roles": []},
}

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def get_next_case_id():
    if not os.path.exists(CASE_ID_FILE):
        with open(CASE_ID_FILE, "w") as f:
            f.write("1")
        return 1
    with open(CASE_ID_FILE, "r+") as f:
        cid = int(f.read().strip())
        f.seek(0)
        f.write(str(cid + 1))
        f.truncate()
    return cid

def log_to_file(case_id, action, moderator, user, inf_type, reason, proof):
    ensure_log_dir()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    filename = os.path.join(LOG_DIR, f"case_{case_id}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Case ID: {case_id}\n")
        f.write(f"Date: {now}\n")
        f.write(f"Action: {action}\n")
        f.write(f"Moderator: {moderator} ({moderator.id})\n")
        f.write(f"User: {user} ({user.id})\n")
        f.write(f"Type: {inf_type}\n")
        f.write(f"Reason: {reason}\n")
        f.write(f"Proof: {proof}\n")

class Infraction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = INFRACTION_DB

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS infractions (
                    case_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    user_name TEXT,
                    moderator_id INTEGER,
                    moderator_name TEXT,
                    action TEXT,
                    reason TEXT,
                    proof TEXT,
                    date TEXT,
                    voided INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    async def get_user_infractions(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM infractions WHERE user_id = ? ORDER BY date DESC", (user_id,))
            return await cursor.fetchall()

    async def get_case(self, case_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM infractions WHERE case_id = ?", (case_id,))
            return await cursor.fetchone()

    async def add_infraction(self, case_id, user, moderator, action, reason, proof):
        now = datetime.datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO infractions (case_id, user_id, user_name, moderator_id, moderator_name, action, reason, proof, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (case_id, user.id, str(user), moderator.id, str(moderator), action, reason, proof, now))
            await db.commit()

    async def void_infraction(self, case_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE infractions SET voided = 1 WHERE case_id = ?", (case_id,))
            await db.commit()

    def get_infraction_embed(self, case_id, user, moderator, action, reason, proof, date, voided=False):
        color = INFRACTION_TYPES.get(action, {}).get("color", discord.Color.default())
        embed = discord.Embed(
            title=f"Infraction: {action}",
            color=color,
            timestamp=datetime.datetime.fromisoformat(date)
        )
        embed.add_field(name="User", value=f"{user}", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Proof", value=proof or "None", inline=False)
        embed.add_field(name="Case ID", value=str(case_id), inline=True)
        if voided:
            embed.add_field(name="Voided", value="✅ This infraction has been voided.", inline=False)
        return embed

    async def update_roles(self, member, action, guild, add=True):
        # Handles role logic for warnings/strikes/suspension/termination
        roles_to_add = []
        roles_to_remove = []
        if action == "Warning":
            # Check current warning/strike roles
            has_warning1 = any(r.id == WARNING_1_ROLE_ID for r in member.roles)
            has_warning2 = any(r.id == WARNING_2_ROLE_ID for r in member.roles)
            has_strike1 = any(r.id == STRIKE_1_ROLE_ID for r in member.roles)
            has_strike2 = any(r.id == STRIKE_2_ROLE_ID for r in member.roles)
            has_strike3 = any(r.id == STRIKE_3_ROLE_ID for r in member.roles)
            if has_warning1 and has_warning2:
                # Upgrade to Strike 1
                roles_to_remove += [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]
                roles_to_add.append(STRIKE_1_ROLE_ID)
            elif has_warning1:
                roles_to_add.append(WARNING_2_ROLE_ID)
            else:
                roles_to_add.append(WARNING_1_ROLE_ID)
        elif action == "Strike":
            has_strike1 = any(r.id == STRIKE_1_ROLE_ID for r in member.roles)
            has_strike2 = any(r.id == STRIKE_2_ROLE_ID for r in member.roles)
            has_strike3 = any(r.id == STRIKE_3_ROLE_ID for r in member.roles)
            if has_strike1 and has_strike2:
                # Upgrade to Strike 3 (10 day suspension)
                roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
            elif has_strike1:
                roles_to_add.append(STRIKE_2_ROLE_ID)
            else:
                roles_to_add.append(STRIKE_1_ROLE_ID)
        elif action == "Demotion":
            # No specific role logic, handled manually
            pass
        elif action == "Termination":
            # Remove all discipline roles, add none (termination handled manually)
            roles_to_remove += [
                WARNING_1_ROLE_ID, WARNING_2_ROLE_ID,
                STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID
            ]
        # Apply roles
        for rid in roles_to_remove:
            role = guild.get_role(rid)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Infraction system discipline update")
        for rid in roles_to_add:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                await member.add_roles(role, reason="Infraction system discipline update")

    @app_commands.command(name="infraction-issue", description="Issue an infraction to personnel.")
    @app_commands.describe(personnel="User to discipline", action="Type", reason="Reason", proof="Proof (link)")
    async def infraction_issue(self, interaction: discord.Interaction, personnel: discord.Member, action: str, reason: str, proof: str = None):
        # Permission checks
        if not any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to issue infractions.", ephemeral=True)
            return
        if not any(r.id == PERSONNEL_ROLE_ID for r in personnel.roles):
            await interaction.response.send_message("Target is not personnel.", ephemeral=True)
            return
        if action not in INFRACTION_TYPES:
            await interaction.response.send_message("Invalid infraction type.", ephemeral=True)
            return

        # Confirmation
        embed = self.get_infraction_embed("Pending", personnel, interaction.user, action, reason, proof, datetime.datetime.utcnow().isoformat())
        await interaction.response.send_message("Please confirm issuing this infraction:", embed=embed, ephemeral=True, view=ConfirmView())
        confirm_inter = await ConfirmView().wait_for_confirm(interaction)
        if not confirm_inter:
            await interaction.followup.send("Infraction cancelled.", ephemeral=True)
            return

        # Issue infraction
        case_id = get_next_case_id()
        await self.add_infraction(case_id, personnel, interaction.user, action, reason, proof)
        await self.update_roles(personnel, action, interaction.guild, add=True)
        embed = self.get_infraction_embed(case_id, personnel, interaction.user, action, reason, proof, datetime.datetime.utcnow().isoformat())
        # Send to infraction channel
        inf_channel = interaction.guild.get_channel(INFRACTION_CHANNEL_ID)
        await inf_channel.send(embed=embed)
        # DM user
        try:
            await personnel.send(embed=embed)
        except Exception:
            pass
        # Log to logging channel
        log_channel = interaction.guild.get_channel(INFRACTION_LOG_CHANNEL_ID)
        await log_channel.send(embed=embed)
        # Log to file
        log_to_file(case_id, "ISSUE", interaction.user, personnel, action, reason, proof)
        await interaction.followup.send(f"Infraction issued and logged. Case ID: {case_id}", ephemeral=True)

    @app_commands.command(name="infraction-void", description="Void an infraction by case ID.")
    @app_commands.describe(case_id="Case ID to void")
    async def infraction_void(self, interaction: discord.Interaction, case_id: int):
        if not any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to void infractions.", ephemeral=True)
            return
        case = await self.get_case(case_id)
        if not case:
            await interaction.response.send_message("Case not found.", ephemeral=True)
            return
        user_id = case[1]
        action = case[5]
        guild = interaction.guild
        member = guild.get_member(user_id)
        await self.void_infraction(case_id)
        # Remove discipline roles
        if member:
            await self.update_roles(member, action, guild, add=False)
        # DM user
        try:
            if member:
                await member.send(f"Your infraction (Case ID: {case_id}) has been voided.")
        except Exception:
            pass
        # Log to logging channel
        embed = self.get_infraction_embed(case_id, case[2], case[4], action, case[6], case[7], case[8], voided=True)
        log_channel = guild.get_channel(INFRACTION_LOG_CHANNEL_ID)
        await log_channel.send(embed=embed)
        # Log to file
        log_to_file(case_id, "VOID", interaction.user, member or user_id, action, case[6], case[7])
        await interaction.response.send_message(f"Infraction {case_id} voided and roles updated.", ephemeral=True)

    @app_commands.command(name="infraction-list", description="List a user's infractions.")
    @app_commands.describe(user="User to list infractions for")
    async def infraction_list(self, interaction: discord.Interaction, user: discord.Member):
        # Permission check
        is_infraction_staff = any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in interaction.user.roles)
        is_personnel = any(r.id == PERSONNEL_ROLE_ID for r in interaction.user.roles)
        if not (is_infraction_staff or (is_personnel and user.id == interaction.user.id)):
            await interaction.response.send_message("You do not have permission to view this user's infractions.", ephemeral=True)
            return
        infractions = await self.get_user_infractions(user.id)
        if not infractions:
            await interaction.response.send_message("No infractions found for this user.", ephemeral=True)
            return
        # Pagination
        pages = [infractions[i:i+5] for i in range(0, len(infractions), 5)]
        page = 0
        embed = discord.Embed(title=f"Infractions for {user}", color=discord.Color.orange())
        for inf in pages[page]:
            embed.add_field(
                name=f"Case {inf[0]} - {inf[5]}",
                value=f"Date: {inf[8][:10]}\nReason: {inf[6]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="infraction-view", description="View a specific infraction by case ID.")
    @app_commands.describe(case_id="Case ID to view")
    async def infraction_view(self, interaction: discord.Interaction, case_id: int):
        is_infraction_staff = any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in interaction.user.roles)
        is_personnel = any(r.id == PERSONNEL_ROLE_ID for r in interaction.user.roles)
        if not (is_infraction_staff or is_personnel):
            await interaction.response.send_message("You do not have permission to view infractions.", ephemeral=True)
            return
        case = await self.get_case(case_id)
        if not case:
            await interaction.response.send_message("Case not found.", ephemeral=True)
            return
        embed = self.get_infraction_embed(case[0], case[2], case[4], case[5], case[6], case[7], case[8], voided=bool(case[9]))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        # Log to logging channel
        log_channel = interaction.guild.get_channel(INFRACTION_LOG_CHANNEL_ID)
        await log_channel.send(embed=embed)
        # Log to file
        log_to_file(case_id, "VIEW", interaction.user, case[2], case[5], case[6], case[7])

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

    async def wait_for_confirm(self, interaction):
        await self.wait()
        return self.value

async def setup(bot: commands.Bot):
    await bot.add_cog(Infraction(bot))