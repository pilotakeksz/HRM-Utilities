import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime
import os

GUILD_ID = 1329908357812981882
TRAINING_ROLE_ID = 1329910342301515838
TRAINING_CHANNEL_ID = 1329910558954098701
TRAINING_PING_ROLE = 1329910324002029599
LOG_CHANNEL_ID = 1343686645815181382

TAN = 0xd0b37b
GREEN = 0x2ecc40
RED = 0xe74c3c

TRAINING_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1382412490771533958/training.png?ex=68958c35&is=68943ab5&hm=3ca01df299c7a68fc60d9bb5dc18e9c008a0065ad2eb75f3f5da180d44249ec4&"
BOTTOM_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=68956491&is=68941311&hm=0b21280ebb311d7869b7c2e8b42f70d31202a2acd375cca1b1f0327d8d7e76c2&"
FOOTER_ICON = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=6895b021&is=68945ea1&hm=5efd99410ebe5a372a0bd1f7fb301b916a6a877ec25a1966368713442b794a4f&"
FOOTER_TEXT = "High Rock Militar Corps Trainings"
LOG_FILE = os.path.join("logs", "training_command.log")

class TrainingVoteView(ui.View):
    def __init__(self, host_id, bot, message=None):
        super().__init__(timeout=None)
        self.voters = set()
        self.host_id = host_id
        self.bot = bot
        self.message = message
        self.locked = False
        self.cancelled = False

    @ui.button(label=None, style=discord.ButtonStyle.success, custom_id='training_tick', emoji='<:tick1:1330953719344402584>')
    async def tick_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.locked or self.cancelled:
            await interaction.response.send_message('Voting is closed.', ephemeral=True)
            return
        self.voters.add(interaction.user.id)
        await interaction.response.send_message('Your vote has been registered!', ephemeral=True)
        await log_action(self.bot, interaction.user, "Training Vote", f"Voted for training. Voters: {self.voters}")

    @ui.button(label=None, style=discord.ButtonStyle.secondary, custom_id='training_members', emoji='<:Member:1343945679390904330>')
    async def member_button(self, interaction: discord.Interaction, button: ui.Button):
        mentions = [f'<@{uid}>' for uid in self.voters]
        msg = '**Voters:**\n' + ('\n'.join(mentions) if mentions else 'None')
        await interaction.response.send_message(msg, ephemeral=True)
        await log_action(self.bot, interaction.user, "Training Vote", f"Viewed voters. Voters: {self.voters}")

    async def send_dm_to_host(self, host, content):
        try:
            await host.send(content)
        except Exception:
            pass

    async def send_voters_dm(self, host, extra=None):
        mentions = [f'<@{uid}>' for uid in self.voters]
        msg = '**Voters:**\n' + ('\n'.join(mentions) if mentions else 'None')
        if extra:
            msg += f"\n\n{extra}"
        await self.send_dm_to_host(host, msg)

    async def lock_training(self, color, content, embed_title, embed_color, bot, host, channel, voters, image, bottom_image, footer_icon, footer_text):
        self.locked = True
        mentions = [f'<@{uid}>' for uid in voters]
        ping = ' '.join(mentions + [host.mention])
        embed1 = discord.Embed(
            color=embed_color,
            title=embed_title
        )
        embed1.set_image(url=image)
        embed1.description = content
        embed2 = discord.Embed(color=embed_color)
        embed2.set_image(url=bottom_image)
        embed2.set_footer(text=footer_text, icon_url=footer_icon)
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass
        await channel.send(content=ping, embeds=[embed1, embed2])

    async def add_end_buttons(self, bot, host, channel):
        view = TrainingEndView(self, bot, host, channel)
        if self.message:
            await self.message.reply(content=f"{host.mention} Please choose:", view=view)

class TrainingEndView(ui.View):
    def __init__(self, vote_view, bot, host, channel):
        super().__init__(timeout=None)
        self.vote_view = vote_view
        self.bot = bot
        self.host = host
        self.channel = channel

    @ui.button(label="Start Training", style=discord.ButtonStyle.success, custom_id="training_start")
    async def start_training(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.vote_view.host_id:
            await interaction.response.send_message("Only the host can start the training.", ephemeral=True)
            return
        await self.vote_view.lock_training(
            color=GREEN,
            content="***The current training session is now locked and in progress.***",
            embed_title="<:HighRockMilitary:1376605942765977800> // Training Session",
            embed_color=GREEN,
            bot=self.bot,
            host=self.host,
            channel=self.channel,
            voters=self.vote_view.voters,
            image=TRAINING_IMAGE,
            bottom_image=BOTTOM_IMAGE,
            footer_icon=FOOTER_ICON,
            footer_text=FOOTER_TEXT
        )
        await interaction.response.send_message("Training started!", ephemeral=True)
        await log_action(self.bot, interaction.user, "Training Vote", "Training started.")

    @ui.button(label="Cancel Training", style=discord.ButtonStyle.danger, custom_id="training_cancel")
    async def cancel_training(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.vote_view.host_id:
            await interaction.response.send_message("Only the host can cancel the training.", ephemeral=True)
            return
        self.vote_view.cancelled = True
        await self.vote_view.lock_training(
            color=RED,
            content="***This training session has been cancelled. We appologise sincerly.***",
            embed_title="<:HighRockMilitary:1376605942765977800> // Training Session",
            embed_color=RED,
            bot=self.bot,
            host=self.host,
            channel=self.channel,
            voters=self.vote_view.voters,
            image=TRAINING_IMAGE,
            bottom_image=BOTTOM_IMAGE,
            footer_icon=FOOTER_ICON,
            footer_text=FOOTER_TEXT
        )
        await interaction.response.send_message("Training cancelled.", ephemeral=True)
        await log_action(self.bot, interaction.user, "Training Vote", "Training cancelled.")

async def log_action(bot, user, action, details):
    os.makedirs("logs", exist_ok=True)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {user} | {action} | {details}\n")
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="Training Log",
            color=0x7289da,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({getattr(user, 'id', 'N/A')})", inline=False)
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Details", value=details, inline=False)
        await channel.send(embed=embed)

class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="training-vote", description="Start a training session vote.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def training_vote(self, interaction: discord.Interaction):
        if not any(r.id == TRAINING_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        channel = interaction.client.get_channel(TRAINING_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Training channel not found.", ephemeral=True)
            return
        now = datetime.datetime.utcnow()
        ten_min = int((now + datetime.timedelta(minutes=10)).timestamp())
        ping = f"<@&{TRAINING_PING_ROLE}>"
        embed1 = discord.Embed(
            color=TAN,
            title="<:HighRockMilitary:1376605942765977800> // Training Session Vote"
        )
        embed1.set_image(url=TRAINING_IMAGE)
        embed1.description = (
            f"> A training session is being hosted by {interaction.user.mention}. You have <t:{ten_min}:R> left to join the training.\n\n"
            f"<:MIAthumbtack1:1365681465806815282>  Training server code: `AXEGK`.\n\n"
            f"> Once in the training server, please do the following:"
        )
        embed1.add_field(
            name="<:MIAdot:1365679087078604840> Firearms",
            value="**Please equip one of the following:**\n> - M4A1\n> - Glock 17",
            inline=True
        )
        embed1.add_field(
            name="<:MIAdot:1365679087078604840>  Uniforms and vehicles",
            value="**Please equip the following uniform:**\n> - [HRM Standard Kit] \n\n**Please spawn one fo the following vehicles:**\n> - 2015 bullhorn prancer [HRM Patrol]\n> - Falcon Interceptor 2019 [HRM Utility]\n> - Chevlon Camion PPV 2000 [HRM Utility]",
            inline=True
        )
        embed2 = discord.Embed(color=TAN)
        embed2.set_image(url=BOTTOM_IMAGE)
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        view = TrainingVoteView(interaction.user.id, self.bot)
        msg = await channel.send(content=ping, embeds=[embed1, embed2], view=view)
        view.message = msg
        await interaction.response.send_message("Training vote started!", ephemeral=True)
        await log_action(self.bot, interaction.user, "Training Vote", "Started training vote.")
        await asyncio.sleep(300)
        host = interaction.user
        await view.send_voters_dm(host)
        await log_action(self.bot, host, "Training Vote", "Sent 5-min DM to host.")
        await asyncio.sleep(300)
        await view.send_voters_dm(host, extra="10 minutes have passed. Please start or cancel the training.")
        await view.add_end_buttons(self.bot, host, channel)
        await log_action(self.bot, host, "Training Vote", "Sent 10-min DM and end buttons to host.")

async def setup(bot):
    await bot.add_cog(Training(bot))
