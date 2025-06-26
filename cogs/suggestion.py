import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random
import pickle

SUGGESTION_CHANNEL_ID = 1329910476171378769
SUGGESTION_MANAGER_ROLE = 1329910241835352064
EMBED_COLOR = 0xd0b47b
APPROVED_COLOR = 0x43b581  # green
DENIED_COLOR = 0xed4245    # red
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=685cffa1&is=685bae21&hm=db6b95d431e55f76eca4e55ca48b7709d7f8bdf1ec1ef77e949b1d0beaa50f42&"
YES_EMOJI = "<:tick1:1330953719344402584>"
NO_EMOJI = "<:xmark1:1330953708766363821>"

VOTES_FILE = "suggestion_votes.pkl"
MESSAGE_MAP_FILE = "suggestion_message_map.pkl"

def load_pickle(filename, default):
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            return pickle.load(f)
    return default

def save_pickle(filename, data):
    with open(filename, "wb") as f:
        pickle.dump(data, f) #test

def progress_bar(yes, no):
    total = yes + no
    if total == 0:
        return "🟩🟩🟩🟩🟩🟥🟥🟥🟥🟥 0%"
    percent = int((yes / total) * 10)
    bar = "🟩" * percent + "🟥" * (10 - percent)
    percent_num = int((yes / total) * 100)
    return f"{bar} {percent_num}%"

class SuggestionView(discord.ui.View):
    def __init__(self, suggestion_id, yes=0, no=0, disabled=False):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id
        self.yes = yes
        self.no = no
        self.disabled = disabled
        self.add_item(SuggestionYesButton(suggestion_id, yes, disabled))
        self.add_item(SuggestionNoButton(suggestion_id, no, disabled))

    @classmethod
    def from_votes(cls, suggestion_id, votes, disabled=False):
        yes = len(votes.get("yes", set()))
        no = len(votes.get("no", set()))
        return cls(suggestion_id, yes=yes, no=no, disabled=disabled)

class SuggestionYesButton(discord.ui.Button):
    def __init__(self, suggestion_id, yes, disabled):
        super().__init__(
            label=str(yes),
            style=discord.ButtonStyle.green,
            emoji=YES_EMOJI,
            custom_id=f"suggest_yes_{suggestion_id}",
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        view: SuggestionView = self.view
        await view.handle_vote(interaction, "yes")

class SuggestionNoButton(discord.ui.Button):
    def __init__(self, suggestion_id, no, disabled):
        super().__init__(
            label=str(no),
            style=discord.ButtonStyle.red,
            emoji=NO_EMOJI,
            custom_id=f"suggest_no_{suggestion_id}",
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        view: SuggestionView = self.view
        await view.handle_vote(interaction, "no")

# Add persistence logic to the view
class SuggestionView(discord.ui.View):
    def __init__(self, suggestion_id, yes=0, no=0, disabled=False):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id
        self.yes = yes
        self.no = no
        self.disabled = disabled
        self.add_item(SuggestionYesButton(suggestion_id, yes, disabled))
        self.add_item(SuggestionNoButton(suggestion_id, no, disabled))

    async def handle_vote(self, interaction: discord.Interaction, vote_type: str):
        cog: Suggestion = interaction.client.get_cog("Suggestion")
        suggestion_id = self.suggestion_id
        user_id = interaction.user.id
        if suggestion_id not in cog.votes:
            cog.votes[suggestion_id] = {"yes": set(), "no": set()}
        # Remove from both sets to allow changing vote
        cog.votes[suggestion_id]["yes"].discard(user_id)
        cog.votes[suggestion_id]["no"].discard(user_id)
        cog.votes[suggestion_id][vote_type].add(user_id)
        yes = len(cog.votes[suggestion_id]["yes"])
        no = len(cog.votes[suggestion_id]["no"])
        # Update embed
        channel = interaction.channel
        message = await channel.fetch_message(interaction.message.id)
        embed = message.embeds[0]
        embed.set_field_at(2, name="Votes", value=progress_bar(yes, no), inline=False)
        new_view = SuggestionView(self.suggestion_id, yes=yes, no=no)
        await message.edit(embed=embed, view=new_view)
        await interaction.response.defer()

    @property
    def persistent_custom_id(self):
        return [item.custom_id for item in self.children if hasattr(item, "custom_id")]

class Suggestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load persisted votes and message_map
        self.votes = load_pickle(VOTES_FILE, {})
        self.message_map = load_pickle(MESSAGE_MAP_FILE, {})
        # Re-add persistent views for all suggestions with active voting
        for suggestion_id, msg_id in self.message_map.items():
            votes = self.votes.get(suggestion_id, {"yes": set(), "no": set()})
            # Only add view if not approved/denied (i.e., message still has voting)
            # You may want to persist status in the future for more robustness
            self.bot.add_view(SuggestionView.from_votes(suggestion_id, votes))

    def save_votes(self):
        save_pickle(VOTES_FILE, self.votes)
        save_pickle(MESSAGE_MAP_FILE, self.message_map)

    @app_commands.command(name="suggestion-submit", description="Submit a suggestion")
    @app_commands.describe(title="Title of your suggestion", suggestion="Your suggestion text")
    async def suggestion_submit(self, interaction: discord.Interaction, title: str, suggestion: str):
        suggestion_id = random.randint(100000, 999999)
        embed = discord.Embed(
            title=title,
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=THUMBNAIL_URL)
        embed.add_field(name="**Suggestor:**", value=interaction.user.mention, inline=False)
        embed.add_field(name="**Suggestion:**", value=suggestion, inline=False)
        embed.add_field(name="Votes", value=progress_bar(0, 0), inline=False)
        embed.set_footer(text=f"Suggestion ID: {suggestion_id}")

        channel = interaction.guild.get_channel(SUGGESTION_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Suggestion channel not found.", ephemeral=True)
            return

        view = SuggestionView(suggestion_id)
        msg = await channel.send(embed=embed, view=view)
        self.votes[suggestion_id] = {"yes": set(), "no": set()}
        self.message_map[suggestion_id] = msg.id
        self.save_votes()

        # Register persistent view for this suggestion
        self.bot.add_view(SuggestionView.from_votes(suggestion_id, self.votes[suggestion_id]))

        await interaction.response.send_message(f"Suggestion submitted to {channel.mention}!", ephemeral=True)

    @app_commands.command(name="suggestion-approve", description="Approve a suggestion (managers only)")
    @app_commands.describe(suggestion_id="Suggestion ID to approve")
    async def suggestion_approve(self, interaction: discord.Interaction, suggestion_id: int):
        if not any(role.id == SUGGESTION_MANAGER_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to approve suggestions.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(SUGGESTION_CHANNEL_ID)
        msg_id = self.message_map.get(suggestion_id)
        if not msg_id:
            await interaction.response.send_message("Suggestion not found.", ephemeral=True)
            return
        msg = await channel.fetch_message(msg_id)
        embed = msg.embeds[0]
        embed.color = APPROVED_COLOR
        # Remove the percentage indicator and percentage from the Votes field
        embed.remove_field(2)
        embed.insert_field_at(0, name="✅ **APPROVED**", value="This suggestion has been approved.", inline=False)
        embed.set_footer(text=f"Suggestion ID: {suggestion_id} | Approved by {interaction.user.display_name}")
        # Remove the buttons by setting view to None
        await msg.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion approved.", ephemeral=True)

    @app_commands.command(name="suggestion-deny", description="Deny a suggestion (managers only)")
    @app_commands.describe(suggestion_id="Suggestion ID to deny", reason="Reason for denial (optional)")
    async def suggestion_deny(self, interaction: discord.Interaction, suggestion_id: int, reason: str = None):
        if not any(role.id == SUGGESTION_MANAGER_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to deny suggestions.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(SUGGESTION_CHANNEL_ID)
        msg_id = self.message_map.get(suggestion_id)
        if not msg_id:
            await interaction.response.send_message("Suggestion not found.", ephemeral=True)
            return
        msg = await channel.fetch_message(msg_id)
        embed = msg.embeds[0]
        embed.color = DENIED_COLOR
        # Remove the percentage indicator and percentage from the Votes field
        embed.remove_field(2)
        embed.insert_field_at(0, name="❌ **DENIED**", value="This suggestion has been denied.", inline=False)
        if reason:
            embed.add_field(name="Denial Reason", value=reason, inline=False)
        embed.set_footer(text=f"Suggestion ID: {suggestion_id} | Denied by {interaction.user.display_name}")
        # Remove the buttons by setting view to None
        await msg.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion denied.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestion(bot))