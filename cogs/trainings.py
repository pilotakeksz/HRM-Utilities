import os
import traceback
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict
import json
import pytz
import re

TRAINING_ROLE_ID = 1329910342301515838  # role allowed to run command
ANNOUNCE_CHANNEL_ID = 1329910495536484374
PING_ROLE_ID = 1329910324002029599
LOG_CHANNEL_ID = 1343686645815181382

YES_EMOJI = discord.PartialEmoji(name="yes", id=1358812809558753401)
NO_EMOJI = discord.PartialEmoji(name="no", id=1358812780890947625)
MEMBER_EMOJI = discord.PartialEmoji(name="Member", id=1343945679390904330)

EMBED_COLOR = 0xd0b47b
IMAGE_URL = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68e8e4dc&is=68e7935c&hm=87d1062f2383b32fc32cdc397b1021296f29aa8caf549b38d3b7137ea8281262&"

LOG_PATH = os.path.join(os.path.dirname(__file__), "../logs/trainings.txt")
SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "training_schedule.json")
TIMEZONE = pytz.timezone('Europe/London')  # Changed from US/Eastern to EU/London

async def log_action(bot: commands.Bot, actor, action: str, extra: str = ""):
    """
    Full action logging:
     - write to local logs/trainings.txt
     - try to post a short message to LOG_CHANNEL_ID
    actor may be a discord.User/Member or a string.
    """
    ts = datetime.now(timezone.utc).isoformat()
    try:
        actor_repr = f"{actor} ({getattr(actor, 'id', '')})" if actor is not None else "Unknown"
    except Exception:
        actor_repr = str(actor)

    line = f"[{ts}] {actor_repr} • {action}"
    if extra:
        # keep extra on one line
        safe_extra = " ".join(str(extra).splitlines())
        line = f"{line} • {safe_extra}"
    # write local file
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # silent fail for local write, but still try to post to channel
        pass

    # send to log channel (best-effort)
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID) or await bot.fetch_channel(LOG_CHANNEL_ID)
        await ch.send(f"`{ts}` {actor_repr} • **{action}** {('• ' + extra) if extra else ''}")
    except Exception:
        # write traceback to file if channel post fails
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass

class ConfirmUnvoteView(discord.ui.View):
    def __init__(self, parent_view: "TrainingVoteView", user_id: int, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.user_id = user_id

    @discord.ui.button(label="Confirm unvote", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You cannot confirm this for someone else.", ephemeral=True)
            return
        self.parent_view.votes.pop(self.user_id, None)
        await self.parent_view._update_message()
        await interaction.response.send_message("Your vote was removed.", ephemeral=True)
        # log unvote
        await log_action(self.parent_view.bot, interaction.user, "unvote_confirmed",
                         extra=f"message_id={getattr(self.parent_view.message, 'id', None)}")
        # notify host about change
        try:
            await self.parent_view.notify_host()
        except Exception:
            await log_action(self.parent_view.bot, "system", "notify_host_failed_after_unvote", extra=f"message_id={getattr(self.parent_view.message, 'id', None)}")
        self.stop()

    async def on_timeout(self):
        self.stop()

class TrainingVoteView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.User, end_time: datetime, message: discord.Message | None = None):
        super().__init__(timeout=None)  # we manually handle timeout
        self.bot = bot
        self.author = author
        self.end_time = end_time
        self.message = message
        self.votes: Dict[int, str] = {}  # user_id -> 'yes'/'no'
        self.started = False

    def counts(self):
        yes = sum(1 for v in self.votes.values() if v == "yes")
        no = sum(1 for v in self.votes.values() if v == "no")
        return yes, no

    async def notify_host(self):
        """DM the host with a short update about current vote counts and lists."""
        if not self.author:
            return
        yes, no = self.counts()
        parts = [f"Training vote update:\n✅ Joining: {yes}\n❌ Not joining: {no}"]
        if self.votes:
            joiners = []
            not_joiners = []
            for uid, v in self.votes.items():
                mention = f"<@{uid}>"
                member = None
                try:
                    if self.message and self.message.guild:
                        member = self.message.guild.get_member(uid)
                except Exception:
                    member = None
                display = member.display_name if member else str(uid)
                if v == "yes":
                    joiners.append(f"{mention} ({display})")
                else:
                    not_joiners.append(f"{mention} ({display})")
            if joiners:
                parts.append("\nJoiners:\n" + "\n".join(joiners))
            if not_joiners:
                parts.append("\nNot joining:\n" + "\n".join(not_joiners))
        try:
            dm = await self.author.create_dm()
            embed = discord.Embed(title="Training vote update", description="\n\n".join(parts), color=EMBED_COLOR)
            embed.set_footer(text=f"Host update • Message ID: {getattr(self.message,'id',None)}")
            await dm.send(embed=embed)
            await log_action(self.bot, self.author, "host_dm_update_sent", extra=f"yes={yes} no={no} message_id={getattr(self.message,'id',None)}")
        except Exception as e:
            await log_action(self.bot, self.author, "host_dm_failed", extra=str(e))

    async def _update_message(self):
        if not self.message:
            return
        yes, no = self.counts()
        embed = self.message.embeds[0]
        # update votes field
        try:
            embed.set_field_at(0, name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
        except Exception:
            # fallback: replace fields
            embed.clear_fields()
            embed.add_field(name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji=YES_EMOJI, label="Join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        existing = self.votes.get(user_id)
        if existing == "yes":
            # prompt confirm unvote
            await interaction.response.send_message("You already voted to join. Confirm unvote to remove your vote.", view=ConfirmUnvoteView(self, user_id), ephemeral=True)
            await log_action(self.bot, interaction.user, "prompt_confirm_unvote",
                             extra=f"vote=yes message_id={getattr(self.message, 'id', None)}")
            return
        self.votes[user_id] = "yes"
        await self._update_message()
        await interaction.response.send_message("Your 'join' vote was recorded.", ephemeral=True)
        await log_action(self.bot, interaction.user, "vote_yes", extra=f"message_id={getattr(self.message, 'id', None)}")
        # notify host on every vote change
        try:
            await self.notify_host()
        except Exception:
            await log_action(self.bot, "system", "notify_host_failed_after_vote_yes", extra=f"user={user_id} message_id={getattr(self.message,'id',None)}")

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji=NO_EMOJI, label="No")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        existing = self.votes.get(user_id)
        if existing == "no":
            await interaction.response.send_message("You already voted not to join. Confirm unvote to remove your vote.", view=ConfirmUnvoteView(self, user_id), ephemeral=True)
            await log_action(self.bot, interaction.user, "prompt_confirm_unvote",
                             extra=f"vote=no message_id={getattr(self.message, 'id', None)}")
            return
        self.votes[user_id] = "no"
        await self._update_message()
        await interaction.response.send_message("Your 'not joining' vote was recorded.", ephemeral=True)
        await log_action(self.bot, interaction.user, "vote_no", extra=f"message_id={getattr(self.message, 'id', None)}")
        # notify host on every vote change
        try:
            await self.notify_host()
        except Exception:
            await log_action(self.bot, "system", "notify_host_failed_after_vote_no", extra=f"user={user_id} message_id={getattr(self.message,'id',None)}")

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji=MEMBER_EMOJI, label="Voters")
    async def who_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        yes_list = []
        no_list = []
        # include mentions so the host (and requester) can see/ping who voted
        for uid, v in self.votes.items():
            mention = f"<@{uid}>"
            member = interaction.guild.get_member(uid) if interaction.guild else None
            name = member.display_name if member else str(uid)
            text = f"{mention} ({name})"
            if v == "yes":
                yes_list.append(text)
            else:
                no_list.append(text)
        yes_text = "\n".join(yes_list) if yes_list else "No one"
        no_text = "\n".join(no_list) if no_list else "No one"
        embed = discord.Embed(title="Who voted", color=EMBED_COLOR)
        embed.add_field(name="✅ Joining", value=yes_text, inline=True)
        embed.add_field(name="❌ Not joining", value=no_text, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_action(self.bot, interaction.user, "who_requested", extra=f"message_id={getattr(self.message, 'id', None)}")

    # Start session button (yellow emoji). Only host can use it and only if at least one YES vote exists.
    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🟨", label="Start Session")
    async def start_session_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only host allowed
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the host can start the session.", ephemeral=True)
            await log_action(self.bot, interaction.user, "start_session_denied_not_host", extra=f"message_id={getattr(self.message,'id',None)}")
            return

        yes_count = sum(1 for v in self.votes.values() if v == "yes")
        if yes_count < 1:
            await interaction.response.send_message("At least one person must have voted YES to start the session.", ephemeral=True)
            await log_action(self.bot, interaction.user, "start_session_denied_no_yes_votes", extra=f"message_id={getattr(self.message,'id',None)}")
            return

        if self.started:
            await interaction.response.send_message("Session has already been started.", ephemeral=True)
            return

        self.started = True
        # disable interactive buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        # DM embed text to voters
        dm_text = (
            "<:MIAthumbtack1:1365681465806815282>  Training server code will be provided by the host.\n\n"
            "> Once you join the server, please join the sheriff team, and do the following:\n\n"
            "**<:Mapecliff_dot:1431744757146587339> Make sure you have a gun equipped.**\n"
            "> `•` [Glock-17 / M4A1 rifle]\n\n"
            "**<:Mapecliff_dot:1431744757146587339> Use the [Standard Kit] uniform.**\n\n"
            "**<:Mapecliff_dot:1431744757146587339> And spawn one of the following vehicles:**\n"
            "> `•` 2015 bullhorn prancer [MCNG Patrol]\n"
            "> `•` Falcon Interceptor 2019 [MCNG Utility]\n"
            "> `•` Chevlon Camion PPV 2000 [MCNG Utility]\n"
        )

        dm_failed = []
        # DM each YES voter as an embed
        for uid, v in list(self.votes.items()):
            if v != "yes":
                continue
            try:
                user = await self.bot.fetch_user(uid)
                dm = await user.create_dm()
                embed = discord.Embed(title="Training starting — AXEGK", description=dm_text, color=EMBED_COLOR)
                embed.set_footer(text=f"Host: {self.author.display_name}")
                await dm.send(embed=embed)
                await log_action(self.bot, user, "dm_sent_start_session", extra=f"by_host={self.author.id} message_id={getattr(self.message,'id',None)}")
            except Exception as e:
                dm_failed.append(str(uid))
                await log_action(self.bot, "system", "dm_failed_start_session", extra=f"user={uid} err={e}")

        # Announce session start, ping host and joining voters
        votes_mentions = " ".join(f"<@{uid}>" for uid, v in self.votes.items() if v == "yes")
        host_mention = f"<@{self.author.id}>"
        announce_embed = discord.Embed(
            title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Training Starting",
            description="Training session has been started by the host.\n\nSee instructions below and join the server when ready.",
            color=EMBED_COLOR
        )
        announce_embed.add_field(name="Host", value=host_mention, inline=True)
        announce_embed.add_field(name="Voters (joining)", value=(votes_mentions or "No one"), inline=False)
        announce_embed.add_field(name="Instructions", value=dm_text, inline=False)
        announce_embed.set_footer(text=f"Started • Host: {self.author.display_name}")
        announce_channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID) or await self.bot.fetch_channel(ANNOUNCE_CHANNEL_ID)
        try:
            await announce_channel.send(content=f"{host_mention} {votes_mentions}", embed=announce_embed)
            await log_action(self.bot, self.author, "session_started_posted", extra=f"message_in={ANNOUNCE_CHANNEL_ID} host={self.author.id}")
        except Exception as e:
            await log_action(self.bot, "system", "session_start_announce_failed", extra=str(e))

        await interaction.response.send_message("Session started. Voters have been DM'd and an announcement was posted.", ephemeral=True)
        await log_action(self.bot, self.author, "session_started", extra=f"yes_count={yes_count} dm_failures={len(dm_failed)} message_id={getattr(self.message,'id',None)}")

    async def finalize(self):
        # disable all buttons and edit message
        for child in self.children:
            child.disabled = True
        if self.message:
            yes, no = self.counts()
            embed = self.message.embeds[0]
            try:
                embed.set_field_at(0, name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
            except Exception:
                embed.clear_fields()
                embed.add_field(name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
            embed.set_footer(text=f"Ended • Host: {self.author.display_name}")
            await self.message.edit(embed=embed, view=self)
        await log_action(self.bot, self.author, "vote_finalized", extra=f"yes={self.counts()[0]} no={self.counts()[1]} message_id={getattr(self.message, 'id', None)}")
        # send DM to author if votes exist
        if self.votes:
            yes, no = self.counts()
            try:
                dm = await self.author.create_dm()
                lines = [f"Training vote ended. Results:\n✅ Joining: {yes}\n❌ Not joining: {no}\n"]
                if yes:
                    joiners = []
                    for uid, v in self.votes.items():
                        if v == "yes":
                            member = self.message.guild.get_member(uid) if self.message and self.message.guild else None
                            joiners.append(member.display_name if member else str(uid))
                    lines.append("Joiners:\n" + ("\n".join(joiners)))
                await dm.send("\n".join(lines))
                await log_action(self.bot, self.author, "dm_sent_results", extra=f"recipient_id={self.author.id} message_id={getattr(self.message, 'id', None)}")
            except Exception as e:
                await log_action(self.bot, self.author, "dm_failed", extra=str(e))

def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_schedule(schedule):
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule, f)

def parse_relative_time(time_str: str) -> timedelta:
    """Parse relative time strings like '2h', '30m', '1d', etc."""
    time_units = {
        'm': 'minutes',
        'h': 'hours',
        'd': 'days',
        'w': 'weeks'
    }
    
    pattern = r'(\d+)([mhdw])'
    match = re.match(pattern, time_str.lower())
    if not match:
        raise ValueError("Invalid time format. Use formats like: 30m, 2h, 1d, 1w")
        
    amount = int(match.group(1))
    unit = match.group(2)
    
    if unit not in time_units:
        raise ValueError("Invalid time unit. Use m (minutes), h (hours), d (days), or w (weeks)")
        
    kwargs = {time_units[unit]: amount}
    return timedelta(**kwargs)

class Trainings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_vote_cooldowns: Dict[int, datetime] = {}
        # Start the schedule checker task
        self.schedule_check_task = bot.loop.create_task(self.check_schedule())

    training = app_commands.Group(name="training", description="Training related commands")

    @training.command(name="vote", description="Create a training vote")
    async def vote(self, interaction: discord.Interaction):
        # log invocation
        await log_action(self.bot, interaction.user, "vote_command_invoked", extra=f"channel_id={getattr(interaction.channel, 'id', None)}")
        # permission check
        user_roles = getattr(interaction.user, "roles", [])
        if not any(r.id == TRAINING_ROLE_ID for r in user_roles):
            await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
            await log_action(self.bot, interaction.user, "vote_command_denied", extra="missing role")
            return

        # server-wide cooldown (30 minutes) per guild; admins bypass
        guild = interaction.guild
        if guild:
            last = self.guild_vote_cooldowns.get(guild.id)
            now = datetime.now(timezone.utc)
            cooldown = timedelta(minutes=30)
            is_admin = getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator
            if last and not is_admin:
                expire = last + cooldown
                if now < expire:
                    remaining = expire - now
                    # relative timestamp for when cooldown expires (use aware timestamp)
                    rel_ts = f"<t:{int(expire.replace(tzinfo=timezone.utc).timestamp())}:R>"
                    await interaction.response.send_message(f"Training vote is on cooldown for this server. Try again {rel_ts}.", ephemeral=True)
                    await log_action(self.bot, interaction.user, "vote_command_on_cooldown", extra=f"guild_id={guild.id} remaining_seconds={int(remaining.total_seconds())}")
                    return
            if is_admin and last:
                # admin bypass - log it
                await log_action(self.bot, interaction.user, "vote_cooldown_bypassed", extra=f"guild_id={guild.id}")

        # compute relative timestamp for 10 minutes from now
        end_dt = datetime.now(timezone.utc) + timedelta(minutes=10)
        epoch = int(end_dt.timestamp())
        rel_ts = f"<t:{epoch}:R>"

        embed = discord.Embed(title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Training Vote", color=EMBED_COLOR, description=(
            "> A training session vote has been cast. In order for a traninig to be hosted, at least 1 vote is required.\n\n"
            "> Please react if you are able to join, the vote lasts ten minutes. The vote will end in " + rel_ts
        ))
        embed.set_image(url=IMAGE_URL)
        embed.set_footer(text=f"Host: {interaction.user.display_name}")
        embed.add_field(name="Votes", value="✅ Joining: 0\n❌ Not joining: 0", inline=False)

        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID) or await self.bot.fetch_channel(ANNOUNCE_CHANNEL_ID)
        content = f"<@&{PING_ROLE_ID}>"
        view = TrainingVoteView(self.bot, interaction.user, end_time=end_dt)
        msg = await channel.send(content=content, embed=embed, view=view)
        view.message = msg

        # set server-wide cooldown timestamp (mark now, timezone-aware)
        if guild:
            self.guild_vote_cooldowns[guild.id] = datetime.now(timezone.utc)

        # log posted
        await log_action(self.bot, interaction.user, "vote_posted", extra=f"channel_id={ANNOUNCE_CHANNEL_ID} message_id={msg.id}")

        # ack to command runner
        await interaction.response.send_message("Training vote posted.", ephemeral=True)
        await log_action(self.bot, interaction.user, "vote_command_acknowledged", extra=f"recipient={interaction.user.id}")

        # schedule finalize after 10 minutes
        async def _wait_and_finalize():
            await asyncio.sleep(600)
            await view.finalize()

        asyncio.create_task(_wait_and_finalize())

    @training.command(name="schedule", description="Schedule a training session")
    @app_commands.describe(
        time="Time until training (e.g. 30m, 2h, 1d, 1w)",
        description="Description of the training"
    )
    async def schedule_training(
        self, 
        interaction: discord.Interaction,
        time: str,
        description: str
    ):
        # Permission check
        if not any(r.id == TRAINING_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to schedule trainings.", ephemeral=True)
            return

        try:
            # Parse relative time
            time_delta = parse_relative_time(time)
            training_time = datetime.now(TIMEZONE) + time_delta
            
            # Load existing schedule
            schedule = load_schedule()
            
            # Create training entry
            training_id = str(len(schedule) + 1)
            schedule[training_id] = {
                "timestamp": training_time.timestamp(),
                "description": description,
                "host": str(interaction.user.id),
                "relative_time": time  # Store original relative time for reference
            }
            
            # Save updated schedule
            save_schedule(schedule)

            # Create announcement embed
            embed = discord.Embed(
                title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Training Scheduled",
                description=description,
                color=EMBED_COLOR
            )
            timestamp = int(training_time.timestamp())
            embed.add_field(
                name="📅 Date & Time", 
                value=f"<t:{timestamp}:F>\n(<t:{timestamp}:R>)",
                inline=False
            )
            embed.add_field(name="Host", value=interaction.user.mention, inline=False)
            embed.set_footer(text=f"Training ID: {training_id}")
            embed.set_image(url=IMAGE_URL)

            # Send announcement
            channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
            await channel.send(
                content=f"<@&{PING_ROLE_ID}> A new training has been scheduled!",
                embed=embed
            )

            await interaction.response.send_message("Training scheduled successfully!", ephemeral=True)
            await log_action(self.bot, interaction.user, "training_scheduled", 
                           extra=f"id={training_id} relative_time={time}")

        except ValueError as e:
            await interaction.response.send_message(
                f"Error: {str(e)}",
                ephemeral=True
            )

    @training.command(name="list-schedule", description="List upcoming scheduled trainings")
    async def list_schedule(self, interaction: discord.Interaction):
        schedule = load_schedule()
        
        if not schedule:
            await interaction.response.send_message("No trainings are currently scheduled.", ephemeral=True)
            return

        embed = discord.Embed(
            title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Scheduled Trainings",
            color=EMBED_COLOR
        )

        # Filter and sort upcoming trainings
        now = datetime.now(TIMEZONE).timestamp()
        upcoming = {
            k: v for k, v in schedule.items() 
            if float(v['timestamp']) > now
        }
        
        if not upcoming:
            await interaction.response.send_message("No upcoming trainings are scheduled.", ephemeral=True)
            return

        sorted_trainings = sorted(upcoming.items(), key=lambda x: float(x[1]['timestamp']))

        for training_id, training in sorted_trainings:
            timestamp = int(float(training['timestamp']))
            host = await self.bot.fetch_user(int(training['host']))
            embed.add_field(
                name=f"Training #{training_id}",
                value=f"📅 <t:{timestamp}:F>\n👤 Host: {host.mention}\n📝 {training['description']}",
                inline=False
            )

        embed.set_footer(text="All times are in ET")
        await interaction.response.send_message(embed=embed)

    @training.command(name="cancel-schedule", description="Cancel a scheduled training")
    @app_commands.describe(training_id="ID of the training to cancel")
    async def cancel_schedule(self, interaction: discord.Interaction, training_id: str):
        if not any(r.id == TRAINING_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to cancel trainings.", ephemeral=True)
            return

        schedule = load_schedule()
        
        if training_id not in schedule:
            await interaction.response.send_message("Training ID not found!", ephemeral=True)
            return

        training = schedule[training_id]
        
        # Check if user is the host or has admin permissions
        is_host = str(interaction.user.id) == training['host']
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_host or is_admin):
            await interaction.response.send_message("You can only cancel trainings you scheduled!", ephemeral=True)
            return

        # Remove the training
        del schedule[training_id]
        save_schedule(schedule)

        # Send cancellation announcement
        embed = discord.Embed(
            title="❌ Training Cancelled",
            description=f"The training scheduled for <t:{int(float(training['timestamp']))}:F> has been cancelled.",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Cancelled by {interaction.user.display_name}")
        
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        await channel.send(embed=embed)

        await interaction.response.send_message("Training cancelled successfully!", ephemeral=True)
        await log_action(self.bot, interaction.user, "training_cancelled", 
                        extra=f"id={training_id}")

    async def check_schedule(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                schedule = load_schedule()
                now = datetime.now(TIMEZONE).timestamp()
                
                # Check for trainings that should start
                for training_id, training in list(schedule.items()):
                    training_time = float(training['timestamp'])
                    
                    # If training time has passed (within last minute to avoid duplicates)
                    if now >= training_time and now - training_time < 60:
                        # Send training vote embed
                        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                        host = await self.bot.fetch_user(int(training['host']))
                        
                        end_dt = datetime.now(timezone.utc) + timedelta(minutes=10)
                        epoch = int(end_dt.timestamp())
                        rel_ts = f"<t:{epoch}:R>"

                        embed = discord.Embed(
                            title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Training Vote", 
                            color=EMBED_COLOR,
                            description=(
                                "> A scheduled training session is starting. In order for a training to be hosted, "
                                "at least 1 vote is required.\n\n"
                                f"> Please react if you are able to join, the vote lasts ten minutes. "
                                f"The vote will end {rel_ts}"
                            )
                        )
                        embed.set_image(url=IMAGE_URL)
                        embed.set_footer(text=f"Host: {host.display_name}")
                        embed.add_field(
                            name="Votes",
                            value="✅ Joining: 0\n❌ Not joining: 0",
                            inline=False
                        )
                        
                        view = TrainingVoteView(self.bot, host, end_time=end_dt)
                        msg = await channel.send(
                            content=f"<@&{PING_ROLE_ID}> Scheduled training is starting!",
                            embed=embed,
                            view=view
                        )
                        view.message = msg

                        # Schedule view finalization
                        async def _wait_and_finalize():
                            await asyncio.sleep(600)
                            await view.finalize()
                        
                        asyncio.create_task(_wait_and_finalize())
                        
                        # Remove the training from schedule
                        del schedule[training_id]
                        save_schedule(schedule)
                        
                        await log_action(
                            self.bot,
                            "system",
                            "scheduled_training_started",
                            extra=f"id={training_id} host={host.id}"
                        )

            except Exception as e:
                # Log any errors but don't stop the task
                await log_action(self.bot, "system", "schedule_check_error", extra=str(e))
            
            # Check every 30 seconds
            await asyncio.sleep(30)

    # Add cleanup on cog unload
    def cog_unload(self):
        if hasattr(self, 'schedule_check_task'):
            self.schedule_check_task.cancel()

async def setup(bot: commands.Bot):
    await bot.add_cog(Trainings(bot))