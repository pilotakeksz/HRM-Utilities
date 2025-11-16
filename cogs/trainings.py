import os
import traceback
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
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
RESULT_CHANNEL_ID = 1329910498350727188  # channel to post individual result embeds
RESULTS_LOG_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def build_result_embeds(trainer, trainee: discord.User, result: str, cotrainer: Optional[discord.User], remarks: str, notes: str):
    """Create the visual and summary embeds for a training result.
    Embeds will not include numeric IDs or timestamps; the summary embed has the same colour as the visual.
    """
    # choose color and image based on pass/fail
    if result.lower().startswith("pass"):
        image_url = "https://cdn.discordapp.com/attachments/1409252771978280973/1439393464394580008/Template.png"
        color = discord.Colour.green()
    else:
        image_url = "https://media.discordapp.net/attachments/1409252771978280973/1439393779722485942/Template.png"
        color = discord.Colour.red()

    # big visual embed
    emb_visual = discord.Embed(title=f"Training Result — {trainee.display_name}", color=color)
    emb_visual.set_image(url=image_url)

    # summary embed (with image, same colour as visual)
    emb2 = discord.Embed(title="<:MaplecliffNationalGaurd:1409463907294384169> `//` Training results", color=color)
    trainer_text = f"> {trainer.mention}"
    cotext = f"> {cotrainer.mention}" if cotrainer else "> None"
    emb2.add_field(name="<:Member:1343945679390904330> Trainer", value=trainer_text, inline=True)
    emb2.add_field(name="<:Member:1343945679390904330> Co-trainer", value=cotext, inline=True)
    emb2.add_field(name="<:Member:1343945679390904330> Trainee", value=f"> {trainee.mention}", inline=False)
    emb2.add_field(name="📊 Result", value=f">{'<:yes:1358812809558753401> PASS' if result.lower().startswith('pass') else '<:no:1358812780890947625> FAIL'}", inline=True)
    if remarks:
        emb2.add_field(name="📝 Remarks", value=f"> {remarks}", inline=False)
    if notes:
        emb2.add_field(name="📌 Notes", value=f"> {notes}", inline=False)
    emb2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=691a551c&is=6919039c&hm=e3875f03b5f806cd119131d923c940d68345f15296d23fd9e3a1ef3ed633bcc8&")
    return emb_visual, emb2


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


async def log_training_result(bot: commands.Bot, trainer, trainee: discord.User, result: str, cotrainer: Optional[discord.User], remarks: str, notes: str):
    """Log a training result: post embed to RESULT_CHANNEL_ID, DM trainee, and write a local JSON log line and log to LOG_CHANNEL_ID as embed.
    Uses shared embed builder so previews and sent embeds match. Embeds do not include numeric IDs or timestamps.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # build embeds using module-level helper
    emb_visual, emb2 = build_result_embeds(trainer, trainee, result, cotrainer, remarks, notes)

    # Send to RESULTS channel (both embeds in one message)
    try:
        out_ch = bot.get_channel(RESULT_CHANNEL_ID) or await bot.fetch_channel(RESULT_CHANNEL_ID)
        if out_ch:
            await out_ch.send(content=f"{trainee.mention}", embeds=[emb_visual, emb2])
    except Exception:
        pass

    # DM trainee (both embeds in one message)
    try:
        dm = await trainee.create_dm()
        await dm.send(embeds=[emb_visual, emb2])
    except Exception:
        pass

    # Log to central log channel as embed (no numeric IDs)
    try:
        log_ch = bot.get_channel(LOG_CHANNEL_ID) or await bot.fetch_channel(LOG_CHANNEL_ID)
        if log_ch:
            log_emb = discord.Embed(title="Training result logged", colour=discord.Colour.blurple())
            log_emb.add_field(name="Trainee", value=f"{trainee.mention}", inline=True)
            log_emb.add_field(name="Result", value=result, inline=True)
            log_emb.add_field(name="Trainer", value=f"{trainer.mention}", inline=True)
            if cotrainer:
                log_emb.add_field(name="Co-trainer", value=f"{cotrainer.mention}", inline=True)
            if remarks:
                log_emb.add_field(name="Remarks", value=remarks, inline=False)
            if notes:
                log_emb.add_field(name="Notes", value=notes, inline=False)
            await log_ch.send(embed=log_emb)
    except Exception:
        pass

    # Append to local results log
    try:
        os.makedirs(RESULTS_LOG_FOLDER, exist_ok=True)
        path = os.path.join(RESULTS_LOG_FOLDER, f"training_results_{datetime.now(timezone.utc).date().isoformat()}.log")
        rec = {
            "timestamp": ts,
            "trainer": getattr(trainer, 'id', str(trainer)),
            "cotrainer": getattr(cotrainer, 'id', None) if cotrainer else None,
            "trainee": getattr(trainee, 'id', str(trainee)),
            "result": result,
            "remarks": remarks,
            "notes": notes,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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
        # Acknowledge the interaction quickly to avoid an interaction timeout
        # (sending DMs and editing the message can take longer than the 3s limit)
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            # If we can't defer (rare), continue — we'll try to send a normal response later
            pass
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
            "<:MCNGdot:1433174947899113614> The training server code is **AXEGK**\n\n"
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

        # Use a followup message since we already deferred the interaction above
        try:
            await interaction.followup.send("Session started. Voters have been DM'd and an announcement was posted.", ephemeral=True)
        except Exception:
            # Fallback if followup fails
            try:
                await interaction.response.send_message("Session started. Voters have been DM'd and an announcement was posted.", ephemeral=True)
            except Exception:
                pass
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
        # Store last yes-voters for convenience (per-guild)
        try:
            if self.message and self.message.guild:
                guild_id = self.message.guild.id
                yes_ids = [uid for uid, v in self.votes.items() if v == "yes"]
                if not hasattr(self.bot, "_last_training_votes"):
                    self.bot._last_training_votes = {}
                self.bot._last_training_votes[guild_id] = yes_ids
        except Exception:
            pass

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

    

    @training.command(name="result", description="Record a training result (trainer role only)")
    @app_commands.describe(
        trainee="Trainee (select a member)",
        result="Result (pass or fail)",
        remarks="Remarks (mandatory)",
        cotrainer="Optional co-trainer (select a member)",
        notes="Notes (optional)"
    )
    @app_commands.choices(result=[
        app_commands.Choice(name="Pass", value="pass"),
        app_commands.Choice(name="Fail", value="fail"),
    ])
    async def result(
        self,
        interaction: discord.Interaction,
        trainee: discord.Member,
        result: app_commands.Choice[str],
        remarks: str,
        cotrainer: Optional[discord.Member] = None,
        notes: Optional[str] = "",
    ):
        # permission check
        if not any(r.id == TRAINING_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to record training results.", ephemeral=True)
            return

        trainer = interaction.user
        # Build preview embeds and ask for confirmation before sending
        try:
            emb_visual, emb2 = build_result_embeds(trainer, trainee, result.value, cotrainer, remarks or "", notes or "")
            view = ConfirmResultView(self.bot, trainer, trainee, result.value, cotrainer, remarks or "", notes or "")
            # send ephemeral preview with confirmation buttons
            await interaction.response.send_message(embeds=[emb_visual, emb2], view=view, ephemeral=True)
            await log_action(self.bot, trainer, "training_result_preview_shown", extra=f"trainee={getattr(trainee,'id',None)} result={result.value}")
        except Exception as e:
            await interaction.response.send_message(f"Failed to build preview: {e}", ephemeral=True)
            await log_action(self.bot, trainer, "training_result_preview_failed", extra=str(e))

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


# -------------------- Training Results UI & Command --------------------
class AddTraineesModal(discord.ui.Modal, title="Add Trainees"):
    trainee_list = discord.ui.TextInput(label="Trainees (IDs or mentions, space/comma separated)", style=discord.TextStyle.long)

    def __init__(self, parent_view: "TrainingResultView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.trainee_list.value
        ids = parse_trainee_ids(raw)
        self.parent_view.add_trainees(ids)
        await interaction.response.send_message(f"Added {len(ids)} trainees.", ephemeral=True)


class TrainingIndividualModal(discord.ui.Modal):
    def __init__(self, parent_view: "TrainingResultView", trainee_id: Optional[int] = None):
        title = "Individual Training Result"
        super().__init__(title=title)
        self.parent_view = parent_view
        self.trainee_id = trainee_id
        self.trainee = discord.ui.TextInput(label="Trainee ID or mention", style=discord.TextStyle.short, required=True, default=str(trainee_id) if trainee_id else "")
        self.result = discord.ui.TextInput(label="Result (pass/fail)", style=discord.TextStyle.short, required=True)
        self.remarks = discord.ui.TextInput(label="Remarks", style=discord.TextStyle.long, required=False)
        self.notes = discord.ui.TextInput(label="Notes", style=discord.TextStyle.long, required=False)
        self.add_item(self.trainee)
        self.add_item(self.result)
        self.add_item(self.remarks)
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        trainee_ids = parse_trainee_ids(self.trainee.value)
        if not trainee_ids:
            await interaction.response.send_message("Could not parse trainee ID.", ephemeral=True)
            return
        tid = trainee_ids[0]
        res = self.result.value.strip()
        remarks = self.remarks.value.strip()
        notes = self.notes.value.strip()
        self.parent_view.individual_results[tid] = {"result": res, "remarks": remarks, "notes": notes}
        if tid not in self.parent_view.trainees:
            self.parent_view.trainees.append(tid)
        await interaction.response.send_message(f"Recorded individual result for <@{tid}>.", ephemeral=True)
        try:
            # update original message
            await interaction.edit_original_response(embed=self.parent_view.build_embed(), view=self.parent_view)
        except Exception:
            pass


class GroupModal(discord.ui.Modal, title="Apply Group Result"):
    common_result = discord.ui.TextInput(label="Result for all (pass/fail)", style=discord.TextStyle.short)
    remarks = discord.ui.TextInput(label="Remarks (optional)", style=discord.TextStyle.long, required=False)
    notes = discord.ui.TextInput(label="Notes (optional)", style=discord.TextStyle.long, required=False)

    def __init__(self, parent_view: "TrainingResultView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.group_result = {"result": self.common_result.value.strip(), "remarks": self.remarks.value.strip(), "notes": self.notes.value.strip()}
        await interaction.response.send_message("Group result recorded.", ephemeral=True)
        try:
            await interaction.edit_original_response(embed=self.parent_view.build_embed(), view=self.parent_view)
        except Exception:
            pass


class SetCotrainerModal(discord.ui.Modal, title="Set Co-trainer"):
    cotrainer = discord.ui.TextInput(label="Co-trainer ID or mention (leave blank for none)", style=discord.TextStyle.short, required=False)

    def __init__(self, parent_view: "TrainingResultView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.cotrainer.value.strip()
        if not raw:
            self.parent_view.cotrainer = None
            await interaction.response.send_message("Co-trainer cleared.", ephemeral=True)
            try:
                await interaction.edit_original_response(embed=self.parent_view.build_embed(), view=self.parent_view)
            except Exception:
                pass
            return
        ids = parse_trainee_ids(raw)
        if not ids:
            await interaction.response.send_message("Could not parse co-trainer ID.", ephemeral=True)
            return
        self.parent_view.cotrainer = ids[0]
        await interaction.response.send_message(f"Co-trainer set to <@{ids[0]}>.", ephemeral=True)
        try:
            await interaction.edit_original_response(embed=self.parent_view.build_embed(), view=self.parent_view)
        except Exception:
            pass


class ImmediateIndividualModal(discord.ui.Modal, title="Record Individual Result"):
    trainee = discord.ui.TextInput(label="Trainee ID or mention", style=discord.TextStyle.short, required=True)
    result = discord.ui.TextInput(label="Result (pass/fail)", style=discord.TextStyle.short, required=True)
    remarks = discord.ui.TextInput(label="Remarks (optional)", style=discord.TextStyle.long, required=False)
    notes = discord.ui.TextInput(label="Notes (optional)", style=discord.TextStyle.long, required=False)

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        trainer = interaction.user
        raw = self.trainee.value.strip()
        ids = parse_trainee_ids(raw)
        if not ids:
            await interaction.response.send_message("Could not parse trainee ID.", ephemeral=True)
            return
        tid = ids[0]
        try:
            trainee = await interaction.client.fetch_user(tid)
        except Exception as e:
            await interaction.response.send_message(f"Failed to fetch trainee user: {e}", ephemeral=True)
            return
        res = self.result.value.strip()
        remarks = self.remarks.value.strip()
        notes = self.notes.value.strip()
        try:
            await log_training_result(interaction.client, trainer, trainee, res, None, remarks, notes)
            await interaction.response.send_message(f"Recorded result for <@{tid}>.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to record result: {e}", ephemeral=True)


class ImmediateGroupModal(discord.ui.Modal, title="Record Group Results"):
    trainee_list = discord.ui.TextInput(label="Trainees (IDs or mentions, space/comma separated)", style=discord.TextStyle.long, required=True)
    cotrainer = discord.ui.TextInput(label="Co-trainer ID or mention (optional)", style=discord.TextStyle.short, required=False)
    result = discord.ui.TextInput(label="Result for all (pass/fail)", style=discord.TextStyle.short, required=True)
    remarks = discord.ui.TextInput(label="Remarks (optional)", style=discord.TextStyle.long, required=False)
    notes = discord.ui.TextInput(label="Notes (optional)", style=discord.TextStyle.long, required=False)

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        trainer = interaction.user
        raw = self.trainee_list.value
        ids = parse_trainee_ids(raw)
        if not ids:
            await interaction.response.send_message("No trainees parsed from input.", ephemeral=True)
            return
        cot = None
        cot_raw = self.cotrainer.value.strip() if self.cotrainer.value else ""
        if cot_raw:
            cot_ids = parse_trainee_ids(cot_raw)
            if cot_ids:
                try:
                    cot = await interaction.client.fetch_user(cot_ids[0])
                except Exception:
                    cot = None

        res = self.result.value.strip()
        remarks = self.remarks.value.strip()
        notes = self.notes.value.strip()

        successes = 0
        failures = 0
        for tid in ids:
            try:
                trainee = await interaction.client.fetch_user(tid)
                await log_training_result(interaction.client, trainer, trainee, res, cot, remarks, notes)
                successes += 1
            except Exception:
                failures += 1

        await interaction.response.send_message(f"Sent results: {successes} succeeded, {failures} failed.", ephemeral=True)


def parse_trainee_ids(raw: str) -> List[int]:
    out: List[int] = []
    if not raw:
        return out
    parts = re.split(r"[\s,]+", raw.strip())
    for p in parts:
        if not p:
            continue
        # mention form <@!id> or <@id>
        m = re.match(r"<@!?([0-9]+)>", p)
        if m:
            out.append(int(m.group(1)))
            continue
        if p.isdigit():
            out.append(int(p))
            continue
    return out


class ConfirmationView(discord.ui.View):
    def __init__(self, parent_view: "TrainingResultView", payload: List[Dict]):
        super().__init__(timeout=120)
        self.parent_view = parent_view
        self.payload = payload

    @discord.ui.button(label="Confirm and Send", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        # perform sending for each
        for item in self.payload:
            trainee = await self.parent_view.bot.fetch_user(item['trainee'])
            cot = await (self.parent_view.bot.fetch_user(item['cotrainer']) if item.get('cotrainer') else None)
            await log_training_result(self.parent_view.bot, interaction.user, trainee, item['result'], cot, item.get('remarks',''), item.get('notes',''))
        await interaction.followup.send(f"Sent results for {len(self.payload)} trainees.", ephemeral=True)
        # close the parent view message
        try:
            await interaction.edit_original_response(embed=self.parent_view.build_embed(final=True), view=self.parent_view)
        except Exception:
            pass
        self.stop()


class ConfirmResultView(discord.ui.View):
    def __init__(self, bot: commands.Bot, trainer: discord.User, trainee: discord.User, result: str, cotrainer: Optional[discord.User], remarks: str, notes: str, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.trainer = trainer
        self.trainee = trainee
        self.result = result
        self.cotrainer = cotrainer
        self.remarks = remarks
        self.notes = notes

    @discord.ui.button(label="Confirm and Send", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # only trainer may confirm
        if interaction.user.id != getattr(self.trainer, 'id', None):
            await interaction.response.send_message("Only the trainer may confirm.", ephemeral=True)
            return
        # disable buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        try:
            await log_training_result(self.bot, self.trainer, self.trainee, self.result, self.cotrainer, self.remarks or "", self.notes or "")
            await interaction.response.edit_message(content="Result sent.", view=self)
            await log_action(self.bot, self.trainer, "training_result_confirmed", extra=f"trainee={getattr(self.trainee,'id',None)} result={self.result}")
        except Exception as e:
            await interaction.response.send_message(f"Failed to send result: {e}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != getattr(self.trainer, 'id', None):
            await interaction.response.send_message("Only the trainer may cancel.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()



class TrainingResultView(discord.ui.View):
    def __init__(self, bot: commands.Bot, trainer: discord.User):
        super().__init__(timeout=None)
        self.bot = bot
        self.trainer = trainer
        self.trainees: List[int] = []
        self.individual_results: Dict[int, Dict] = {}
        self.group_result: Optional[Dict] = None
        self.cotrainer: Optional[int] = None

    def add_trainees(self, ids: List[int]):
        for i in ids:
            if i not in self.trainees:
                self.trainees.append(i)

    def build_embed(self, final: bool = False) -> discord.Embed:
        emb = discord.Embed(title="Training Results Builder", color=EMBED_COLOR)
        emb.add_field(name="Trainer", value=f"{self.trainer.mention}", inline=True)
        emb.add_field(name="Co-trainer", value=(f"<@{self.cotrainer}>" if self.cotrainer else "None"), inline=True)
        emb.add_field(name="Trainees count", value=str(len(self.trainees)), inline=True)
        lines = []
        for tid in self.trainees:
            if tid in self.individual_results:
                r = self.individual_results[tid]
                lines.append(f"<@{tid}> — {r['result']} — {r.get('remarks','')}")
            elif self.group_result:
                lines.append(f"<@{tid}> — {self.group_result['result']} (group)")
            else:
                lines.append(f"<@{tid}> — (no result)")
        emb.description = "\n".join(lines) if lines else "No trainees added yet."
        if final:
            emb.set_footer(text="Results sent")
        return emb

    @discord.ui.button(label="Add trainees (paste IDs)", style=discord.ButtonStyle.primary)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddTraineesModal(self))

    @discord.ui.button(label="Set co-trainer", style=discord.ButtonStyle.secondary)
    async def set_cotrainer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetCotrainerModal(self))

    @discord.ui.button(label="Add all from last vote", style=discord.ButtonStyle.secondary)
    async def add_last_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        ids = []
        try:
            ids = getattr(self.bot, '_last_training_votes', {}).get(guild.id, [])
        except Exception:
            ids = []
        if not ids:
            await interaction.response.send_message("No recent vote data available.", ephemeral=True)
            return
        self.add_trainees(ids)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Individualise next", style=discord.ButtonStyle.success)
    async def individualise(self, interaction: discord.Interaction, button: discord.ui.Button):
        # find next trainee without individual result
        for tid in self.trainees:
            if tid not in self.individual_results:
                await interaction.response.send_modal(TrainingIndividualModal(self, trainee_id=tid))
                return
        await interaction.response.send_message("No trainees left to individualise.", ephemeral=True)

    @discord.ui.button(label="Apply group result", style=discord.ButtonStyle.primary)
    async def group_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GroupModal(self))

    @discord.ui.button(label="Preview & Confirm", style=discord.ButtonStyle.success, row=2)
    async def preview_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # build payload
        payload = []
        for tid in self.trainees:
            entry = {"trainee": tid}
            if tid in self.individual_results:
                entry.update(self.individual_results[tid])
            elif self.group_result:
                entry.update(self.group_result)
            else:
                entry.update({"result": "(no result)", "remarks": "", "notes": ""})
            entry['cotrainer'] = None
            entry['cotrainer'] = self.cotrainer
            payload.append(entry)
        # build confirmation embed
        emb = discord.Embed(title="Confirm Training Results", color=EMBED_COLOR)
        for p in payload:
            emb.add_field(name=f"<@{p['trainee']}>", value=f"Result: {p['result']}\nRemarks: {p.get('remarks','')}\nNotes: {p.get('notes','')}", inline=False)
        view = ConfirmationView(self, payload)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled result entry.", ephemeral=True)