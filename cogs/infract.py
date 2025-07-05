import os
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import uuid
from typing import Optional

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
    "Activity Notice": {"color": discord.Color.teal(), "roles": []},  # New type
}

def log_to_file(user_id, channel_id, message, embed=False):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | Embed: {embed} | Message: {message}\n")
    with open(INFRACTION_LOG_TEXT, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | {message}\n")

def log_command_to_txt(command_name, user, channel, **fields):
    log_path = os.path.join("logs", f"{command_name}.txt")
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user} ({user.id}) | Channel: {channel} ({getattr(channel, 'id', channel)})\n")
        for k, v in fields.items():
            f.write(f"  {k}: {v}\n")
        f.write("\n")

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

class ActivityNoticeModal(discord.ui.Modal, title="Issue Activity Notice"):
    required_time = discord.ui.TextInput(
        label="Required Duty Time (hours)",
        placeholder="e.g. 5",
        required=True,
        min_length=1,
        max_length=10
    )
    reason = discord.ui.TextInput(
        label="Reason for Activity Notice",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=5,
        max_length=200
    )

    def __init__(self, cog, personnel, interaction):
        super().__init__()
        self.cog = cog
        self.personnel = personnel
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        infraction_id = str(uuid.uuid4())
        required_time = self.required_time.value
        reason = self.reason.value
        issued_by = interaction.user
        personnel = self.personnel
        proof_url = None
        action = "Activity Notice"
        now = datetime.datetime.utcnow().isoformat()
        inf_channel = interaction.guild.get_channel(INFRACTION_CHANNEL_ID)
        embed = discord.Embed(
            title=f"Infraction: {action}",
            color=INFRACTION_TYPES[action]["color"],
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{personnel}", inline=True)
        embed.add_field(name="Issued by", value=f"{issued_by}", inline=True)
        embed.add_field(name="Required Duty Time", value=f"{required_time} hours", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Infraction ID", value=str(infraction_id), inline=True)
        msg = await inf_channel.send(content=personnel.mention, embed=embed)

        # DM the user
        try:
            dm_embed = discord.Embed(
                title="You have received an Activity Notice",
                description=(
                    f"You have received an Activity Notice in **{interaction.guild.name}**.\n\n"
                    f"**Required Duty Time:** {required_time} hours\n"
                    f"**Reason:** {reason}\n"
                    f"**Infraction ID:** {infraction_id}"
                ),
                color=INFRACTION_TYPES[action]["color"]
            )
            dm_embed.set_footer(text=f"Issued by: {issued_by}")
            await personnel.send(embed=dm_embed)
        except Exception as e:
            print(f"Failed to DM user: {e}")

        await self.cog.add_infraction(
            infraction_id, personnel, issued_by, action, f"Required Duty Time: {required_time} | {reason}", proof_url, msg.id
        )

        # Log to logging file
        log_to_file(
            issued_by.id,
            interaction.channel.id,
            f"Issued Activity Notice to {personnel.id} | Required Duty Time: {required_time} | Reason: {reason} | Infraction ID: {infraction_id}",
            embed=True
        )
        await interaction.response.send_message(f"Activity Notice issued and logged. Infraction ID: {infraction_id}", ephemeral=True)

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
                    message_id INTEGER,
                    voided INTEGER DEFAULT 0,
                    void_reason TEXT
                )
            """)
            await db.commit()

    async def add_infraction(self, infraction_id, user, issued_by, action, reason, proof, message_id=None):
        now = datetime.datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO infractions (
                    infraction_id, user_id, user_name, moderator_id, moderator_name,
                    action, reason, proof, date, message_id, voided, void_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """, (infraction_id, user.id, str(user), issued_by.id, str(issued_by), action, reason, proof, now, message_id))
            await db.commit()
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
        # Get current role states
        has_w1 = any(r.id == WARNING_1_ROLE_ID for r in member.roles)
        has_w2 = any(r.id == WARNING_2_ROLE_ID for r in member.roles)
        has_s1 = any(r.id == STRIKE_1_ROLE_ID for r in member.roles)
        has_s2 = any(r.id == STRIKE_2_ROLE_ID for r in member.roles)
        has_s3 = any(r.id == STRIKE_3_ROLE_ID for r in member.roles)
        has_susp = any(r.id == SUSPENDED_ROLE_ID for r in member.roles)

        if action == "Warning":
            # Escalate to strike if already has both warnings
            if has_w1 and has_w2:
                roles_to_remove += [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]
                # Escalate to next strike
                if has_s1 and has_s2:
                    # Already has S1 and S2, next is S3+Suspension
                    roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                    if has_s3:
                        # Already has S3, should terminate
                        return "terminate"
                    else:
                        roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
                elif has_s1:
                    roles_to_add.append(STRIKE_2_ROLE_ID)
                else:
                    roles_to_add.append(STRIKE_1_ROLE_ID)
            elif has_w1:
                roles_to_add.append(WARNING_2_ROLE_ID)
            else:
                roles_to_add.append(WARNING_1_ROLE_ID)
        elif action == "Strike":
            # Escalate to S3+Suspension if already has S1 and S2
            if has_s1 and has_s2:
                roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                if has_s3:
                    # Already has S3, should terminate
                    return "terminate"
                else:
                    roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
            elif has_s1:
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
        return None

    @app_commands.command(name="infraction-issue", description="Issue an infraction to personnel.")
    @app_commands.describe(personnel="User to discipline", action="Type", reason="Reason", proof="Proof file")
    async def infraction_issue(self, interaction: discord.Interaction, personnel: discord.Member, action: str, reason: str = None, proof: discord.Attachment = None):
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

        if action == "Activity Notice":
            await interaction.response.send_modal(ActivityNoticeModal(self, personnel, interaction))
            return

        # Log command usage to txt
        log_command_to_txt(
            "infraction-issue",
            interaction.user,
            interaction.channel,
            personnel=f"{personnel} ({personnel.id})",
            action=action,
            reason=reason,
            proof=proof.url if proof else "None"
        )

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
        result = await self.update_roles(personnel, action, interaction.guild, add=True)
        if result == "terminate":
            await interaction.followup.send(
                f"⚠️ {personnel.mention} has reached the maximum strikes. Please proceed with termination.",
                ephemeral=True
            )

        # Log to logging file (one line per infraction)
        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Issued infraction to {personnel.id} | Type: {action} | Reason: {reason} | Infraction ID: {infraction_id} | DM sent: {dm_success}",
            embed=True
        )
        await interaction.followup.send(f"Infraction issued and logged. Infraction ID: {infraction_id}", ephemeral=True)

        # After issuing the infraction, send a log embed to the log channel
        log_channel = interaction.guild.get_channel(INFRACTION_VIEW_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Infraction Issued",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{personnel} ({personnel.id})", inline=False)
            log_embed.add_field(name="By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            log_embed.add_field(name="Action", value=action, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Proof", value=proof.url if proof else "None", inline=False)
            log_embed.add_field(name="Infraction ID", value=infraction_id, inline=False)
            log_embed.set_footer(text=f"Logged at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            await log_channel.send(embed=log_embed)

    @infraction_issue.autocomplete('action')
    async def infraction_action_autocomplete(self, interaction: discord.Interaction, current: str):
        actions = ["Warning", "Strike", "Demotion", "Termination", "Suspension", "Activity Notice"]
        return [
            app_commands.Choice(name=action, value=action)
            for action in actions if current.lower() in action.lower()
        ][:25]

    @app_commands.command(name="infraction-log", description="View the infraction log (last 10 entries).")
    async def infraction_log(self, interaction: discord.Interaction):
        """Show the last 10 non-voided infractions in an embed."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT infraction_id, user_name, moderator_name, action, reason, proof, date, voided, void_reason FROM infractions WHERE voided = 0 ORDER BY date DESC LIMIT 10"
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
                infraction_id, user_name, moderator_name, action, reason, proof, date, voided, void_reason = row
                date_fmt = datetime.datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
                value = (
                    f"**User:** {user_name}\n"
                    f"**By:** {moderator_name}\n"
                    f"**Type:** {action}\n"
                    f"**Reason:** {reason}\n"
                    f"**Proof:** {proof or 'None'}\n"
                    f"**Date:** {date_fmt}\n"
                    f"**ID:** `{infraction_id}`\n"
                )
                if voided:
                    value += f"**VOIDED**: {void_reason or 'No reason provided.'}\n"
                embed.add_field(name="\u200b", value=value, inline=False)
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
                "SELECT infraction_id, user_name, moderator_name, action, reason, proof, date FROM infractions WHERE voided = 0 ORDER BY date DESC LIMIT 10"
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
            now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
            embed.set_footer(text=f"Generated: {now_utc}")
        await channel.send(embed=embed)
        await ctx.send("Infraction log sent.")

    @app_commands.command(name="infraction-void", description="Void (remove) an infraction by its ID.")
    @app_commands.describe(infraction_id="The infraction ID to void", reason="Reason for voiding this infraction")
    async def infraction_void(self, interaction: discord.Interaction, infraction_id: str, reason: str):
        try:
            # Permission check
            if not any(r.id == INFRACTION_PERMISSIONS_ROLE_ID for r in getattr(interaction.user, "roles", [])):
                await interaction.response.send_message("You do not have permission to void infractions.", ephemeral=True)
                return

            # Fetch infraction details and message_id from the database
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, user_name, action, reason, date, message_id, voided FROM infractions WHERE infraction_id = ?",
                    (infraction_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    await interaction.response.send_message("Infraction not found.", ephemeral=True)
                    return
                user_id, user_name, action, orig_reason, date, message_id, voided = row

                if voided:
                    await interaction.response.send_message("This infraction is already voided.", ephemeral=True)
                    return

                # Mark as voided
                await db.execute(
                    "UPDATE infractions SET voided = 1, void_reason = ? WHERE infraction_id = ?",
                    (reason, infraction_id)
                )
                await db.commit()

            # Remove from logs/infraction.txt (optional, or you can keep for history)
            log_file = os.path.join("logs", "infraction.txt")
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                with open(log_file, "w", encoding="utf-8") as f:
                    for line in lines:
                        if infraction_id not in line:
                            f.write(line)

            # Edit the original infraction message to show voided status
            inf_channel = interaction.guild.get_channel(INFRACTION_CHANNEL_ID)
            if inf_channel and message_id:
                try:
                    msg = await inf_channel.fetch_message(message_id)
                    voided_embed = discord.Embed(
                        title="Infraction Voided",
                        description=(
                            f"**Infraction ID:** `{infraction_id}`\n"
                            f"**User:** {user_name} (`{user_id}`)\n"
                            f"**Original Action:** {action}\n"
                            f"**Original Reason:** {orig_reason}\n"
                            f"**Voided By:** {interaction.user.mention}\n"
                            f"**Void Reason:** {reason}"
                        ),
                        color=discord.Color.green()
                    )
                    now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
                    voided_embed.set_footer(text=f"Voided: {now_utc}")
                    await msg.edit(embed=voided_embed, content="~~This infraction has been voided.~~")
                except Exception:
                    pass

            # DM the user about the voided infraction
            try:
                user = await interaction.guild.fetch_member(user_id)
                dm_embed = discord.Embed(
                    title="Your Infraction Was Voided",
                    description=(
                        f"An infraction issued to you in **{interaction.guild.name}** has been voided.\n\n"
                        f"**Original Action:** {action}\n"
                        f"**Original Reason:** {orig_reason}\n"
                        f"**Voided By:** {interaction.user.mention}\n"
                        f"**Void Reason:** {reason}"
                    ),
                    color=discord.Color.green()
                )
                now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
                dm_embed.set_footer(text=f"Voided: {now_utc}")
                await user.send(embed=dm_embed)
                # --- REVERSE ROLES LOGIC ---
                # Remove discipline roles if appropriate
                member = user
                guild = interaction.guild
                if action == "Warning":
                    # Remove warning roles
                    for rid in [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]:
                        role = guild.get_role(rid)
                        if role and role in member.roles:
                            await member.remove_roles(role, reason="Infraction voided")
                elif action == "Strike":
                    # Remove strike roles and suspension if present
                    for rid in [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]:
                        role = guild.get_role(rid)
                        if role and role in member.roles:
                            await member.remove_roles(role, reason="Infraction voided")
                elif action == "Suspension":
                    # Remove suspension role
                    role = guild.get_role(SUSPENDED_ROLE_ID)
                    if role and role in member.roles:
                        await member.remove_roles(role, reason="Infraction voided")
                elif action == "Termination":
                    # Remove all discipline roles
                    for rid in [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID, STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]:
                        role = guild.get_role(rid)
                        if role and role in member.roles:
                            await member.remove_roles(role, reason="Infraction voided")
                # Demotion: no roles to remove
            except Exception:
                pass

            # Log the void action
            now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
            log_to_file(
                interaction.user.id,
                interaction.channel.id,
                f"Voided infraction {infraction_id} for user {user_name} ({user_id}). Original action: {action}. Void reason: {reason}",
                embed=False
            )

            # Log command usage to txt
            log_command_to_txt(
                "infraction-void",
                interaction.user,
                interaction.channel,
                infraction_id=infraction_id,
                target_user=f"{user_name} ({user_id})",
                action=action,
                original_reason=orig_reason,
                void_reason=reason
            )

            # After voiding, send a log embed to the log channel
            log_channel = interaction.guild.get_channel(INFRACTION_VIEW_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="Infraction Voided",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.add_field(name="Infraction ID", value=infraction_id, inline=False)
                log_embed.add_field(name="User", value=f"{user_name} ({user_id})", inline=False)
                log_embed.add_field(name="By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
                log_embed.add_field(name="Original Action", value=action, inline=True)
                log_embed.add_field(name="Original Reason", value=orig_reason, inline=False)
                log_embed.add_field(name="Void Reason", value=reason, inline=False)
                log_embed.set_footer(text=f"Logged at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
                await log_channel.send(embed=log_embed)

            # Respond to the moderator
            embed = discord.Embed(
                title="Infraction Voided",
                description=(
                    f"**Infraction ID:** `{infraction_id}`\n"
                    f"**User:** {user_name} (`{user_id}`)\n"
                    f"**Original Action:** {action}\n"
                    f"**Original Reason:** {orig_reason}\n"
                    f"**Voided By:** {interaction.user.mention}\n"
                    f"**Void Reason:** {reason}"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Voided: {now_utc}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            # Always respond, even on error
            try:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="infraction-view", description="View all details of a specific infraction by its ID.")
    @app_commands.describe(infraction_id="The infraction ID to view")
    async def infraction_view(self, interaction: discord.Interaction, infraction_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT infraction_id, user_id, user_name, moderator_id, moderator_name, action, reason, proof, date, voided, void_reason FROM infractions WHERE infraction_id = ?",
                (infraction_id,)
            )
            row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("Infraction not found.", ephemeral=True)
            return

        (infraction_id, user_id, user_name, moderator_id, moderator_name, action, reason, proof, date, voided, void_reason) = row
        embed = discord.Embed(
            title=f"Infraction Details: {infraction_id}",
            color=discord.Color.green() if voided else INFRACTION_TYPES.get(action, {}).get("color", discord.Color.default()),
            timestamp=datetime.datetime.fromisoformat(date)
        )
        embed.add_field(name="User", value=f"{user_name} (`{user_id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator_name} (`{moderator_id}`)", inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Proof", value=proof or "None", inline=False)
        embed.add_field(name="Date", value=date, inline=False)
        embed.add_field(name="Voided", value="Yes" if voided else "No", inline=True)
        if voided:
            embed.add_field(name="Void Reason", value=void_reason or "No reason provided.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="infraction-list", description="List all infractions for a user, paginated.")
    @app_commands.describe(user="The user to list infractions for", page="Page number (default 1)")
    async def infraction_list(self, interaction: discord.Interaction, user: discord.Member, page: Optional[int] = 1):
        PAGE_SIZE = 5
        offset = (page - 1) * PAGE_SIZE
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT infraction_id, action, reason, date, voided, void_reason FROM infractions WHERE user_id = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                (user.id, PAGE_SIZE, offset)
            )
            rows = await cursor.fetchall()
            # For total count
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM infractions WHERE user_id = ?",
                (user.id,)
            )
            total = (await count_cursor.fetchone())[0]

        if not rows:
            await interaction.response.send_message("No infractions found for this user on this page.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Infractions for {user} (Page {page}/{(total + PAGE_SIZE - 1)//PAGE_SIZE})",
            color=discord.Color.orange()
        )
        for row in rows:
            infraction_id, action, reason, date, voided, void_reason = row
            value = (
                f"**Type:** {action}\n"
                f"**Reason:** {reason}\n"
                f"**Date:** {date}\n"
                f"**ID:** `{infraction_id}`\n"
            )
            if voided:
                value += f"**VOIDED**: {void_reason or 'No reason provided.'}\n"
            embed.add_field(name="\u200b", value=value, inline=False)
        embed.set_footer(text=f"Total Infractions: {total}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Infraction(bot))