import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random
import pickle
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

SUGGESTION_CHANNEL_ID = 1329910476171378769
SUGGESTION_MANAGER_ROLE = 1355842403134603275
EMBED_COLOR = 0xd0b47b
APPROVED_COLOR = 0x43b581  # green
DENIED_COLOR = 0xed4245    # red
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=685cffa1&is=685bae21&hm=db6b95d431e55f76eca4e55ca48b7709d7f8bdf1ec1ef77e949b1d0beaa50f42&"
YES_EMOJI = "<:utils_tick:1426625947729137754>"
NO_EMOJI = "<:utils_cross:1426625759291904061>"

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

def progress_bar_image(yes, no):
    width, height = 300, 48
    bar_height = 40
    total = yes + no
    percent = int((yes / total) * 100) if total > 0 else 0

    img = Image.new("RGB", (width, height), color=(32, 34, 37))
    draw = ImageDraw.Draw(img)

    if total == 0:
        draw.rectangle([0, 0, width, bar_height], fill=(54, 57, 63))
    else:
        green_width = int(width * (percent / 100))
        # Draw green part
        if green_width > 0:
            draw.rectangle([0, 0, green_width, bar_height], fill=(67, 181, 129))
        # Draw red part
        if green_width < width:
            draw.rectangle([green_width, 0, width, bar_height], fill=(237, 66, 69))
        # Blend at the border between green and red
        if 0 < green_width < width:
            blend_width = 12  # pixels for blending
            for x in range(blend_width):
                alpha = x / blend_width
                # Blend green and red
                r = int((1 - alpha) * 67 + alpha * 237)
                g = int((1 - alpha) * 181 + alpha * 66)
                b = int((1 - alpha) * 129 + alpha * 69)
                xpos = green_width - blend_width // 2 + x
                if 0 <= xpos < width:
                    draw.line([(xpos, 0), (xpos, bar_height)], fill=(r, g, b))

    percent_text = f"{percent}%"
    try:
        font = ImageFont.truetype("arialbd.ttf", 44)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 44)
        except Exception:
            font = ImageFont.load_default()
    bbox = font.getbbox(percent_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (width - text_width) // 2
    text_y = (bar_height - text_height) // 2

    pad_x, pad_y = 10, 6
    rect_x0 = text_x - pad_x
    rect_y0 = text_y - pad_y
    rect_x1 = text_x + text_width + pad_x
    rect_y1 = text_y + text_height + pad_y
    draw.rounded_rectangle(
        [rect_x0, rect_y0, rect_x1, rect_y1],
        radius=12,
        fill=(22, 34, 56)
    )

    draw.text(
        (text_x, text_y),
        percent_text,
        font=font,
        fill=(255, 255, 255)
    )

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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

    async def handle_vote(self, interaction: discord.Interaction, vote_type: str):
        cog: Suggestion = interaction.client.get_cog("Suggestion")
        suggestion_id = self.suggestion_id
        user_id = interaction.user.id
        if suggestion_id not in cog.votes:
            cog.votes[suggestion_id] = {"yes": set(), "no": set()}
        cog.votes[suggestion_id]["yes"].discard(user_id)
        cog.votes[suggestion_id]["no"].discard(user_id)
        cog.votes[suggestion_id][vote_type].add(user_id)
        yes = len(cog.votes[suggestion_id]["yes"])
        no = len(cog.votes[suggestion_id]["no"])
        channel = interaction.channel
        message = await channel.fetch_message(interaction.message.id)
        embed = message.embeds[0]
        embed.set_image(url=None)
        votes_img = progress_bar_image(yes, no)
        file = discord.File(votes_img, filename="votes.png")
        embed.set_image(url="attachment://votes.png")
        new_view = SuggestionView(self.suggestion_id, yes=yes, no=no)
        await message.edit(embed=embed, view=new_view, attachments=[file])
        cog.save_votes()
        await interaction.response.defer()

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
        await interaction.response.defer()  # <-- Move this to the top
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
        await interaction.response.defer()  # <-- Move this to the top
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

    @classmethod
    def from_votes(cls, suggestion_id, votes, disabled=False):
        yes = len(votes.get("yes", set()))
        no = len(votes.get("no", set()))
        return cls(suggestion_id, yes=yes, no=no, disabled=disabled)

    async def handle_vote(self, interaction: discord.Interaction, vote_type: str):
        cog: Suggestion = interaction.client.get_cog("Suggestion")
        suggestion_id = self.suggestion_id
        user_id = interaction.user.id
        if suggestion_id not in cog.votes:
            cog.votes[suggestion_id] = {"yes": set(), "no": set()}
        cog.votes[suggestion_id]["yes"].discard(user_id)
        cog.votes[suggestion_id]["no"].discard(user_id)
        cog.votes[suggestion_id][vote_type].add(user_id)
        yes = len(cog.votes[suggestion_id]["yes"])
        no = len(cog.votes[suggestion_id]["no"])
        channel = interaction.channel
        message = await channel.fetch_message(interaction.message.id)
        embed = message.embeds[0]
        embed.set_image(url=None)
        votes_img = progress_bar_image(yes, no)
        file = discord.File(votes_img, filename="votes.png")
        embed.set_image(url="attachment://votes.png")
        new_view = SuggestionView(self.suggestion_id, yes=yes, no=no)
        await message.edit(embed=embed, view=new_view, attachments=[file])
        cog.save_votes()
        await interaction.response.defer() #test

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
        await interaction.response.defer(ephemeral=True)  # Respond immediately to avoid timeout

        suggestion_id = random.randint(100000, 999999)
        embed = discord.Embed(
            title=title,
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=THUMBNAIL_URL)
        embed.add_field(name="**Suggestor:**", value=interaction.user.mention, inline=False)
        embed.add_field(name="**Suggestion:**", value=suggestion, inline=False)
        # REMOVE the emoji bar field entirely
        embed.set_footer(text=f"Suggestion ID: {suggestion_id}")

        channel = interaction.guild.get_channel(SUGGESTION_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Suggestion channel not found or bot lacks permissions.", ephemeral=True)
            return

        view = SuggestionView(suggestion_id)
        try:
            votes_img = progress_bar_image(0, 0)
            file = discord.File(votes_img, filename="votes.png")
            embed.set_image(url="attachment://votes.png")
            msg = await channel.send(embed=embed, view=view, file=file)
        except Exception as e:
            await interaction.followup.send(f"Failed to send suggestion: {e}", ephemeral=True)
            return

        self.votes[suggestion_id] = {"yes": set(), "no": set()}
        self.message_map[suggestion_id] = msg.id
        self.save_votes()

        self.bot.add_view(SuggestionView.from_votes(suggestion_id, self.votes[suggestion_id]))

        await interaction.followup.send(f"Suggestion submitted to {channel.mention}!", ephemeral=True)

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