import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from typing import Dict

TRAINING_ROLE_ID = 1329910342301515838  # role allowed to run command
ANNOUNCE_CHANNEL_ID = 1329910495536484374
PING_ROLE_ID = 1329910324002029599

YES_EMOJI = discord.PartialEmoji(name="yes", id=1358812809558753401)
NO_EMOJI = discord.PartialEmoji(name="no", id=1358812780890947625)
MEMBER_EMOJI = discord.PartialEmoji(name="Member", id=1343945679390904330)

EMBED_COLOR = 0xd0b47b
IMAGE_URL = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68e8e4dc&is=68e7935c&hm=87d1062f2383b32fc32cdc397b1021296f29aa8caf549b38d3b7137ea8281262&"

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

    def counts(self):
        yes = sum(1 for v in self.votes.values() if v == "yes")
        no = sum(1 for v in self.votes.values() if v == "no")
        return yes, no

    async def _update_message(self):
        if not self.message:
            return
        yes, no = self.counts()
        embed = self.message.embeds[0]
        # update footer or description with live counts
        embed.set_field_at(0, name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji=YES_EMOJI, label="Join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        existing = self.votes.get(user_id)
        if existing == "yes":
            # prompt confirm unvote
            await interaction.response.send_message("You already voted to join. Confirm unvote to remove your vote.", view=ConfirmUnvoteView(self, user_id), ephemeral=True)
            return
        self.votes[user_id] = "yes"
        await self._update_message()
        await interaction.response.send_message("Your 'join' vote was recorded.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji=NO_EMOJI, label="No")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        existing = self.votes.get(user_id)
        if existing == "no":
            await interaction.response.send_message("You already voted not to join. Confirm unvote to remove your vote.", view=ConfirmUnvoteView(self, user_id), ephemeral=True)
            return
        self.votes[user_id] = "no"
        await self._update_message()
        await interaction.response.send_message("Your 'not joining' vote was recorded.", ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji=MEMBER_EMOJI, label="Who voted")
    async def who_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        yes_list = []
        no_list = []
        for uid, v in self.votes.items():
            member = interaction.guild.get_member(uid) if interaction.guild else None
            name = member.display_name if member else str(uid)
            if v == "yes":
                yes_list.append(name)
            else:
                no_list.append(name)
        yes_text = "\n".join(yes_list) if yes_list else "No one"
        no_text = "\n".join(no_list) if no_list else "No one"
        embed = discord.Embed(title="Who voted", color=EMBED_COLOR)
        embed.add_field(name="✅ Joining", value=yes_text, inline=True)
        embed.add_field(name="❌ Not joining", value=no_text, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def finalize(self):
        # disable all buttons and edit message
        for child in self.children:
            child.disabled = True
        if self.message:
            yes, no = self.counts()
            embed = self.message.embeds[0]
            embed.set_field_at(0, name="Votes", value=f"✅ Joining: {yes}\n❌ Not joining: {no}", inline=False)
            embed.set_footer(text=f"Ended • Host: {self.author.display_name}")
            await self.message.edit(embed=embed, view=self)
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
            except Exception:
                pass

class Trainings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    training = app_commands.Group(name="training", description="Training related commands")

    @training.command(name="vote", description="Create a training vote")
    async def vote(self, interaction: discord.Interaction):
        # permission check
        if not any(r.id == TRAINING_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
            return

        # compute relative timestamp for 10 minutes from now
        end_dt = datetime.utcnow() + timedelta(minutes=10)
        epoch = int(end_dt.timestamp())
        rel_ts = f"<t:{epoch}:R>"

        embed = discord.Embed(title=":MaplecliffNationalGaurd: // Training Vote", color=EMBED_COLOR, description=(
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

        # ack to command runner
        await interaction.response.send_message("Training vote posted.", ephemeral=True)

        # schedule finalize after 10 minutes
        async def _wait_and_finalize():
            await asyncio.sleep(600)
            await view.finalize()

        asyncio.create_task(_wait_and_finalize())

async def setup(bot: commands.Bot):
    await bot.add_cog(Trainings(bot))