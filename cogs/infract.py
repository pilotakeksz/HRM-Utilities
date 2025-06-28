import os
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import uuid

INFRACTION_DB = "data/infractions.db"
LOG_FILE = "logs/infraction_command.log"

INFRACTION_LOG_TEXT = os.path.join("logs", "infraction.txt")
INFRACTION_VIEW_CHANNEL_ID = 1343686645815181382

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
    "Suspension": {"color": discord.Color.blue(), "roles": [SUSPENDED_ROLE_ID]},
}

def log_to_file(user_id, channel_id, message, embed=False):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | Embed: {embed} | Message: {message}\n")
    # Also log to infraction.txt in logs folder (plain text, one line per infraction)
    with open(INFRACTION_LOG_TEXT, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | {message}\n")

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

class Infraction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = INFRACTION_DB

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS infractions (
                    infraction_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    user_name TEXT,
                    moderator_id INTEGER,
                    moderator_name TEXT,
                    action TEXT,
                    reason TEXT,
                    proof TEXT,
                    date TEXT,
                    message_id INTEGER
                )
            """)
            await db.commit()

    async def add_infraction(self, infraction_id, user, issued_by, action, reason, proof, message_id=None):
        now = datetime.datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO infractions (infraction_id, user_id, user_name, moderator_id, moderator_name, action, reason, proof, date, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (infraction_id, user.id, str(user), issued_by.id, str(issued_by), action, reason, proof, now, message_id))
            await db.commit()
        # Log to infraction.txt as well (for easy viewing)
        with open(INFRACTION_LOG_TEXT, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {user} ({user.id}) | By: {issued_by} ({issued_by.id}) | {action} | Reason: {reason} | Proof: {proof or 'None'} | Infraction ID: {infraction_id}\n")

    def get_infraction_embed(self, infraction_id, user, issued_by, action, reason, proof, date):
        color = INFRACTION_TYPES.get(action, {}).get("color", discord.Color.default())
        embed = discord.Embed(
            title=f"Infraction: {action}",
            color=color,
            timestamp=datetime.datetime.fromisoformat(date)
        )
        embed.add_field(name="User", value=f"{user}", inline=True)
        embed.add_field(name="Issued by", value=f"{issued_by}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Proof", value=proof or "None", inline=False)
        embed.add_field(name="Infraction ID", value=str(infraction_id), inline=True)
        return embed

    async def update_roles(self, member, action, guild, add=True):
        roles_to_add = []
        roles_to_remove = []
        if action == "Warning":
            has_warning1 = any(r.id == WARNING_1_ROLE_ID for r in member.roles)
            has_warning2 = any(r.id == WARNING_2_ROLE_ID for r in member.roles)
            if has_warning1 and has_warning2:
                roles_to_remove += [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]
                roles_to_add.append(STRIKE_1_ROLE_ID)
            elif has_warning1:
                roles_to_add.append(WARNING_2_ROLE_ID)
            else:
                roles_to_add.append(WARNING_1_ROLE_ID)
        elif action == "Strike":
            has_strike1 = any(r.id == STRIKE_1_ROLE_ID for r in member.roles)
            has_strike2 = any(r.id == STRIKE_2_ROLE_ID for r in member.roles)
            if has_strike1 and has_strike2:
                roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
            elif has_strike1:
                roles_to_add.append(STRIKE_2_ROLE_ID)
            else:
                roles_to_add.append(STRIKE_1_ROLE_ID)
        elif action == "Suspension":
            roles_to_add.append(SUSPENDED_ROLE_ID)
            roles_to_remove += [
                WARNING_1_ROLE_ID, WARNING_2_ROLE_ID,
                STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID
            ]
        elif action == "Demotion":
            pass
        elif action == "Termination":
            roles_to_remove += [
                WARNING_1_ROLE_ID, WARNING_2_ROLE_ID,
                STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID
            ]
        for rid in roles_to_remove:
            role = guild.get_role(rid)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Infraction system discipline update")
        for rid in roles_to_add:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                await member.add_roles(role, reason="Infraction system discipline update")

    @app_commands.command(name="infraction-issue", description="Issue an infraction to personnel.")
    @app_commands.describe(personnel="User to discipline", action="Type", reason="Reason", proof="Proof file")
    async def infraction_issue(self, interaction: discord.Interaction, personnel: discord.Member, action: str, reason: str, proof: discord.Attachment = None):
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

        proof_url = proof.url if proof else None
        embed = self.get_infraction_embed("Pending", personnel, interaction.user, action, reason, proof_url, datetime.datetime.utcnow().isoformat())
        if proof and proof.content_type and proof.content_type.startswith("image/"):
            embed.set_image(url=proof.url)
        view = ConfirmView()
        await interaction.response.send_message("Please confirm issuing this infraction:", embed=embed, ephemeral=True, view=view)
        await view.wait()
        if not view.value:
            await interaction.followup.send("Infraction cancelled.", ephemeral=True)
            return

        # Issue infraction
        infraction_id = str(uuid.uuid4())
        inf_channel = interaction.guild.get_channel(INFRACTION_CHANNEL_ID)
        embed = self.get_infraction_embed(infraction_id, personnel, interaction.user, action, reason, proof_url, datetime.datetime.utcnow().isoformat())
        if proof and proof.content_type and proof.content_type.startswith("image/"):
            embed.set_image(url=proof.url)
            msg = await inf_channel.send(content=personnel.mention, embed=embed)
        elif proof:
            msg = await inf_channel.send(content=personnel.mention, embed=embed, file=await proof.to_file())
        else:
            msg = await inf_channel.send(content=personnel.mention, embed=embed)

        # DM the infracted user
        dm_success = False
        try:
            dm_embed = discord.Embed(
                title="You have received an infraction",
                description=(
                    f"You have received an infraction in **{interaction.guild.name}**.\n\n"
                    f"**Type:** {action}\n"
                    f"**Reason:** {reason}\n"
                    f"**Infraction ID:** {infraction_id}"
                ),
                color=INFRACTION_TYPES.get(action, {}).get("color", discord.Color.default())
            )
            dm_embed.set_footer(text=f"Issued by: {interaction.user}")
            if proof and proof.content_type and proof.content_type.startswith("image/"):
                dm_embed.set_image(url=proof.url)
            await personnel.send(embed=dm_embed)
            dm_success = True
        except Exception as e:
            print(f"Failed to DM user: {e}")

        await self.add_infraction(infraction_id, personnel, interaction.user, action, reason, proof_url, msg.id)
        await self.update_roles(personnel, action, interaction.guild, add=True)

        # Log to logging file (one line per infraction)
        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Issued infraction to {personnel.id} | Type: {action} | Reason: {reason} | Infraction ID: {infraction_id} | DM sent: {dm_success}",
            embed=True
        )
        await interaction.followup.send(f"Infraction issued and logged. Infraction ID: {infraction_id}", ephemeral=True)

    @infraction_issue.autocomplete('action')
    async def infraction_action_autocomplete(self, interaction: discord.Interaction, current: str):
        actions = ["Warning", "Strike", "Demotion", "Termination", "Suspension"]
        return [
            app_commands.Choice(name=action, value=action)
            for action in actions if current.lower() in action.lower()
        ][:25]

    @app_commands.command(name="infraction-log", description="View the infraction log (last 10 entries).")
    async def infraction_log(self, interaction: discord.Interaction):
        """Show the last 10 infractions in an embed, for channel 1343686645815181382."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT infraction_id, user_name, moderator_name, action, reason, proof, date FROM infractions ORDER BY date DESC LIMIT 10"
            )
            rows = await cursor.fetchall()
        if not rows:
            embed = discord.Embed(
                title="Infraction Log",
                description="No infractions found.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="Recent Infractions",
                description="Last 10 infractions issued.",
                color=discord.Color.orange()
            )
            for row in rows:
                infraction_id, user_name, moderator_name, action, reason, proof, date = row
                date_fmt = datetime.datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
                value = (
                    f"**User:** {user_name}\n"
                    f"**By:** {moderator_name}\n"
                    f"**Type:** {action}\n"
                    f"**Reason:** {reason}\n"
                    f"**Proof:** {proof or 'None'}\n"
                    f"**Date:** {date_fmt}\n"
                    f"**ID:** `{infraction_id}`"
                )
                embed.add_field(name="\u200b", value=value, inline=False)
            # Add UTC footer
            now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
            embed.set_footer(text=f"Generated: {now_utc}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="infractionlog")
    async def infractionlog_command(self, ctx):
        """Send the last 10 infractions to the log channel as an embed."""
        channel = self.bot.get_channel(INFRACTION_VIEW_CHANNEL_ID)
        if not channel:
            await ctx.send("Log channel not found.")
            return
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT infraction_id, user_name, moderator_name, action, reason, proof, date FROM infractions ORDER BY date DESC LIMIT 10"
            )
            rows = await cursor.fetchall()
        if not rows:
            embed = discord.Embed(
                title="Infraction Log",
                description="No infractions found.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="Recent Infractions",
                description="Last 10 infractions issued.",
                color=discord.Color.orange()
            )
            for row in rows:
                infraction_id, user_name, moderator_name, action, reason, proof, date = row
                date_fmt = datetime.datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
                value = (
                    f"**User:** {user_name}\n"
                    f"**By:** {moderator_name}\n"
                    f"**Type:** {action}\n"
                    f"**Reason:** {reason}\n"
                    f"**Proof:** {proof or 'None'}\n"
                    f"**Date:** {date_fmt}\n"
                    f"**ID:** `{infraction_id}`"
                )
                embed.add_field(name="\u200b", value=value, inline=False)
            # Add UTC footer
            now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
            embed.set_footer(text=f"Generated: {now_utc}")
        await channel.send(embed=embed)
        await ctx.send("Infraction log sent.")

    @app_commands.command(name="infraction-void", description="Void (remove) an infraction by its ID.")
    @app_commands.describe(infraction_id="The infraction ID to void", reason="Reason for voiding this infraction")
    async def infraction_void(self, interaction: discord.Interaction, infraction_id: str, reason: str):
        # Permission check (same as issue)
        if not any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to void infractions.", ephemeral=True)
            return

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, user_name, action, reason, date FROM infractions WHERE infraction_id = ?",
                (infraction_id,)
            )
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("Infraction not found.", ephemeral=True)
                return

            # Optionally, you could delete or mark as voided. Here, we delete:
            await db.execute("DELETE FROM infractions WHERE infraction_id = ?", (infraction_id,))
            await db.commit()

        # Log the void action
        now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Voided infraction {infraction_id} for user {row[1]} ({row[0]}). Original action: {row[2]}. Void reason: {reason}",
            embed=False
        )

        embed = discord.Embed(
            title="Infraction Voided",
            description=(
                f"**Infraction ID:** `{infraction_id}`\n"
                f"**User:** {row[1]} (`{row[0]}`)\n"
                f"**Original Action:** {row[2]}\n"
                f"**Original Reason:** {row[3]}\n"
                f"**Voided By:** {interaction.user.mention}\n"
                f"**Void Reason:** {reason}"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Voided: {now_utc}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Infraction(bot))