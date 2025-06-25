import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random
from discord.ui import View, Button

SUGGESTION_CHANNEL_ID = 1329910476171378769
SUGGESTION_MANAGER_ROLE = 1329910241835352064
EMBED_COLOR = 0xd0b47b
APPROVED_COLOR = 0x43b581  # green
DENIED_COLOR = 0xed4245    # red
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=685cffa1&is=685bae21&hm=db6b95d431e55f76eca4e55ca48b7709d7f8bdf1ec1ef77e949b1d0beaa50f42&"
YES_EMOJI = "<:yes:1358812809558753401>"
NO_EMOJI = "<:no:1358812780890947625>"

def progress_bar(yes, no):
    total = yes + no
    if total == 0:
        return "🟩🟩🟩🟩🟩🟥🟥🟥🟥🟥 0%"
    percent = int((yes / total) * 10)
    bar = "🟩" * percent + "🟥" * (10 - percent)
    percent_num = int((yes / total) * 100)
    return f"{bar} {percent_num}%"

class SuggestionView(View):
    def __init__(self, suggestion_id, yes=0, no=0, disabled=False):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id
        self.yes = yes
        self.no = no
        self.disabled = disabled
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(Button(label=str(self.yes), style=discord.ButtonStyle.green, emoji=YES_EMOJI, custom_id=f"suggest_yes_{self.suggestion_id}", disabled=self.disabled))
        self.add_item(Button(label=str(self.no), style=discord.ButtonStyle.red, emoji=NO_EMOJI, custom_id=f"suggest_no_{self.suggestion_id}", disabled=self.disabled))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Prevent the author from voting multiple times (optional: implement per-user voting)
        return True

class Suggestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.votes = {}  # suggestion_id: {"yes": set(user_ids), "no": set(user_ids)}
        self.message_map = {}  # suggestion_id: message_id

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

        await interaction.response.send_message(f"Suggestion submitted to {channel.mention}!", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("suggest_yes_") or custom_id.startswith("suggest_no_"):
            suggestion_id = int(custom_id.split("_")[-1])
            user_id = interaction.user.id
            if suggestion_id not in self.votes:
                self.votes[suggestion_id] = {"yes": set(), "no": set()}
            # Remove from both sets to allow changing vote
            self.votes[suggestion_id]["yes"].discard(user_id)
            self.votes[suggestion_id]["no"].discard(user_id)
            if custom_id.startswith("suggest_yes_"):
                self.votes[suggestion_id]["yes"].add(user_id)
            else:
                self.votes[suggestion_id]["no"].add(user_id)

            # Update embed
            channel = interaction.channel
            message = await channel.fetch_message(interaction.message.id)
            embed = message.embeds[0]
            yes = len(self.votes[suggestion_id]["yes"])
            no = len(self.votes[suggestion_id]["no"])
            embed.set_field_at(2, name="Votes", value=progress_bar(yes, no), inline=False)
            view = SuggestionView(suggestion_id, yes=yes, no=no)
            await message.edit(embed=embed, view=view)
            await interaction.response.defer()

    # ...existing code...

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
        yes = len(self.votes.get(suggestion_id, {}).get("yes", []))
        embed.set_field_at(2, name="Votes", value=progress_bar(yes, 0).replace("🟩", "🟩").replace("🟥", "🟩").replace("%", "100%"), inline=False)
        # Add APPROVED in big letters at the top
        embed.insert_field_at(0, name="✅ **APPROVED**", value="This suggestion has been approved.", inline=False)
        view = SuggestionView(suggestion_id, yes=yes, no=0, disabled=True)
        await msg.edit(embed=embed, view=view)
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
        no = len(self.votes.get(suggestion_id, {}).get("no", []))
        embed.set_field_at(2, name="Votes", value=progress_bar(0, no).replace("🟩", "🟥").replace("%", "100%"), inline=False)
        # Add DENIED in big letters at the top
        embed.insert_field_at(0, name="❌ **DENIED**", value="This suggestion has been denied.", inline=False)
        if reason:
            embed.add_field(name="Denial Reason", value=reason, inline=False)
        view = SuggestionView(suggestion_id, yes=0, no=no, disabled=True)
        await msg.edit(embed=embed, view=view)
        await interaction.response.send_message("Suggestion denied.", ephemeral=True)

# ...existing

async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestion(bot))