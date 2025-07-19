import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import uuid
from datetime import datetime

EMBED_CREATOR_ROLE = 1329910230066401361
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/embed_data.db")
LOG_PATH = os.path.join(os.path.dirname(__file__), "../logs/embed_usage.txt")

def log_usage(user, action, key=None):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as logf:
        logf.write(f"[{datetime.utcnow().isoformat()}] {user} ({user.id}) {action} {key or ''}\n")

class EmbedSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.embeds = [self._new_embed()]
        self.current = 0

    def _new_embed(self):
        return {
            "title": "",
            "description": "",
            "color": 0x2f3136,
            "image_url": "",
            "thumbnail_url": "",
            "footer": "",
            "footer_icon": "",
            "fields": [],
            "buttons": []
        }

    def add_embed(self):
        self.embeds.append(self._new_embed())
        self.current = len(self.embeds) - 1

    def remove_embed(self, idx):
        if len(self.embeds) > 1:
            self.embeds.pop(idx)
            self.current = max(0, self.current - 1)

    def switch_embed(self, idx):
        if 0 <= idx < len(self.embeds):
            self.current = idx

    def get(self):
        return self.embeds[self.current]

class EmbedButton(discord.ui.Button):
    def __init__(self, label, url):
        super().__init__(label=label, style=discord.ButtonStyle.link, url=url)

class EmbedBuilderView(discord.ui.View):
    def __init__(self, session, cog):
        super().__init__(timeout=600)
        self.session = session
        self.cog = cog

        # Row 0: Embed navigation
        self.add_item(PrevEmbedButton(session, row=0))
        self.add_item(NextEmbedButton(session, row=0))
        self.add_item(AddEmbedButton(session, row=0))
        self.add_item(RemoveEmbedButton(session, row=0))

        # Row 1: Main properties
        self.add_item(AddTitleButton(session, row=1))
        self.add_item(AddDescriptionButton(session, row=1))
        self.add_item(AddColorButton(session, row=1))

        # Row 2: Images
        self.add_item(AddImageButton(session, row=2))
        self.add_item(AddThumbnailButton(session, row=2))

        # Row 3: Footer
        self.add_item(AddFooterButton(session, row=3))
        self.add_item(AddFooterIconButton(session, row=3))

        # Row 4: Fields
        self.add_item(AddFieldButton(session, row=4))
        self.add_item(RemoveFieldButton(session, row=4))

        # Row 5: Buttons
        self.add_item(AddButtonButton(session, row=5))
        self.add_item(RemoveButtonButton(session, row=5))

        # Row 6: Actions
        self.add_item(DoneButton(session, cog, row=6))
        self.add_item(SaveButton(session, cog, row=6))
        self.add_item(LoadButton(session, cog, row=6))

class PrevEmbedButton(discord.ui.Button):
    def __init__(self, session, row=0):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        if self.session.current > 0:
            self.session.current -= 1
        await update_embed_preview(interaction, self.session)

class NextEmbedButton(discord.ui.Button):
    def __init__(self, session, row=0):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        if self.session.current < len(self.session.embeds) - 1:
            self.session.current += 1
        await update_embed_preview(interaction, self.session)

class AddEmbedButton(discord.ui.Button):
    def __init__(self, session, row=0):
        super().__init__(label="➕ Add Embed", style=discord.ButtonStyle.success, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        self.session.add_embed()
        await update_embed_preview(interaction, self.session)

class RemoveEmbedButton(discord.ui.Button):
    def __init__(self, session, row=0):
        super().__init__(label="🗑 Remove Embed", style=discord.ButtonStyle.danger, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        self.session.remove_embed(self.session.current)
        await update_embed_preview(interaction, self.session)

class AddTitleButton(discord.ui.Button):
    def __init__(self, session, row=1):
        super().__init__(label="Title", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TitleModal(self.session))

class TitleModal(discord.ui.Modal, title="Set Embed Title"):
    title = discord.ui.TextInput(label="Title", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["title"] = self.title.value
        await update_embed_preview(interaction, self.session)

class AddDescriptionButton(discord.ui.Button):
    def __init__(self, session, row=1):
        super().__init__(label="Description", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DescriptionModal(self.session))

class DescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    description = discord.ui.TextInput(label="Description", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["description"] = self.description.value
        await update_embed_preview(interaction, self.session)

class AddColorButton(discord.ui.Button):
    def __init__(self, session, row=1):
        super().__init__(label="Color", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ColorModal(self.session))

class ColorModal(discord.ui.Modal, title="Set Embed Color"):
    color = discord.ui.TextInput(label="Color (hex, e.g. 0x2f3136)", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.session.get()["color"] = int(self.color.value, 16)
        except Exception:
            pass
        await update_embed_preview(interaction, self.session)

class AddImageButton(discord.ui.Button):
    def __init__(self, session, row=2):
        super().__init__(label="Image", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ImageModal(self.session))

class ImageModal(discord.ui.Modal, title="Set Embed Image"):
    image_url = discord.ui.TextInput(label="Image URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["image_url"] = self.image_url.value
        await update_embed_preview(interaction, self.session)

class AddThumbnailButton(discord.ui.Button):
    def __init__(self, session, row=2):
        super().__init__(label="Thumbnail", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThumbnailModal(self.session))

class ThumbnailModal(discord.ui.Modal, title="Set Embed Thumbnail"):
    thumbnail_url = discord.ui.TextInput(label="Thumbnail URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["thumbnail_url"] = self.thumbnail_url.value
        await update_embed_preview(interaction, self.session)

class AddFooterButton(discord.ui.Button):
    def __init__(self, session, row=3):
        super().__init__(label="Footer", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterModal(self.session))

class FooterModal(discord.ui.Modal, title="Set Embed Footer"):
    footer = discord.ui.TextInput(label="Footer Text", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["footer"] = self.footer.value
        await update_embed_preview(interaction, self.session)

class AddFooterIconButton(discord.ui.Button):
    def __init__(self, session, row=3):
        super().__init__(label="Footer Icon", style=discord.ButtonStyle.primary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterIconModal(self.session))

class FooterIconModal(discord.ui.Modal, title="Set Footer Icon URL"):
    footer_icon = discord.ui.TextInput(label="Footer Icon URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["footer_icon"] = self.footer_icon.value
        await update_embed_preview(interaction, self.session)

class AddFieldButton(discord.ui.Button):
    def __init__(self, session, row=4):
        super().__init__(label="Add Field", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FieldModal(self.session))

class FieldModal(discord.ui.Modal, title="Add Field"):
    name = discord.ui.TextInput(label="Field Name", required=True)
    value = discord.ui.TextInput(label="Field Value", required=True)
    inline = discord.ui.TextInput(label="Inline? (true/false)", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        inline_bool = self.inline.value.lower() == "true"
        self.session.get()["fields"].append((self.name.value, self.value.value, inline_bool))
        await update_embed_preview(interaction, self.session)

class RemoveFieldButton(discord.ui.Button):
    def __init__(self, session, row=4):
        super().__init__(label="Remove Field", style=discord.ButtonStyle.danger, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        fields = self.session.get()["fields"]
        if fields:
            fields.pop()
        await update_embed_preview(interaction, self.session)

class AddButtonButton(discord.ui.Button):
    def __init__(self, session, row=5):
        super().__init__(label="Add Link Button", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LinkButtonModal(self.session))

class LinkButtonModal(discord.ui.Modal, title="Add Link Button"):
    label = discord.ui.TextInput(label="Button Label", required=True)
    url = discord.ui.TextInput(label="Button URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["buttons"].append((self.label.value, self.url.value))
        await update_embed_preview(interaction, self.session)

class RemoveButtonButton(discord.ui.Button):
    def __init__(self, session, row=5):
        super().__init__(label="Remove Button", style=discord.ButtonStyle.danger, row=row)
        self.session = session
    async def callback(self, interaction: discord.Interaction):
        buttons = self.session.get()["buttons"]
        if buttons:
            buttons.pop()
        await update_embed_preview(interaction, self.session)

class DoneButton(discord.ui.Button):
    def __init__(self, session, cog, row=6):
        super().__init__(label="Done/Send", style=discord.ButtonStyle.success, row=row)
        self.session = session
        self.cog = cog
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChannelModal(self.session, self.cog))

class ChannelModal(discord.ui.Modal, title="Send Embeds"):
    channel_id = discord.ui.TextInput(label="Channel ID", required=True)
    def __init__(self, session, cog):
        super().__init__()
        self.session = session
        self.cog = cog
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(int(self.channel_id.value))
        if not channel:
            await interaction.response.send_message("Invalid channel ID.", ephemeral=True)
            return
        for embed_data in self.session.embeds:
            embed = self.cog.session_to_embed(embed_data)
            view = self.cog.session_to_view(embed_data)
            await channel.send(embed=embed, view=view)
        log_usage(interaction.user, "sent_embeds")
        await interaction.response.send_message("Embeds sent!", ephemeral=True)

class SaveButton(discord.ui.Button):
    def __init__(self, session, cog, row=6):
        super().__init__(label="Save for Later", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.cog = cog
    async def callback(self, interaction: discord.Interaction):
        key = str(uuid.uuid4())[:8]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS embeds (key TEXT PRIMARY KEY, user_id INTEGER, embeds TEXT, created_at TEXT)"
            )
            await db.execute(
                "INSERT INTO embeds (key, user_id, embeds, created_at) VALUES (?, ?, ?, ?)",
                (
                    key,
                    self.session.user_id,
                    repr(self.session.embeds),
                    datetime.utcnow().isoformat()
                )
            )
            await db.commit()
        log_usage(interaction.user, "saved_embeds", key)
        await interaction.response.send_message(f"Embeds saved! Your key: `{key}`", ephemeral=True)

class LoadButton(discord.ui.Button):
    def __init__(self, session, cog, row=6):
        super().__init__(label="Load Saved", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.cog = cog
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LoadEmbedModal(self.session, self.cog))

class LoadEmbedModal(discord.ui.Modal, title="Load Saved Embeds"):
    key = discord.ui.TextInput(label="Embed Key", required=True)
    def __init__(self, session, cog):
        super().__init__()
        self.session = session
        self.cog = cog
    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM embeds WHERE key = ?", (self.key.value,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    self.session.embeds = eval(row[2])
                    self.session.current = 0
                    await update_embed_preview(interaction, self.session)
                    await interaction.response.send_message("Embeds loaded!", ephemeral=True)
                else:
                    await interaction.response.send_message("No embeds found with that key.", ephemeral=True)

def session_to_embed(embed_data):
    embed = discord.Embed(
        title=embed_data["title"],
        description=embed_data["description"],
        color=embed_data["color"]
    )
    if embed_data["image_url"]:
        embed.set_image(url=embed_data["image_url"])
    if embed_data["thumbnail_url"]:
        embed.set_thumbnail(url=embed_data["thumbnail_url"])
    if embed_data["footer"]:
        embed.set_footer(text=embed_data["footer"], icon_url=embed_data["footer_icon"] if embed_data["footer_icon"] else discord.Embed.Empty)
    for name, value, inline in embed_data["fields"]:
        embed.add_field(name=name, value=value, inline=inline)
    return embed

def session_to_view(embed_data):
    view = discord.ui.View()
    for label, url in embed_data["buttons"]:
        view.add_item(EmbedButton(label, url))
    return view

async def update_embed_preview(interaction, session):
    embed = session_to_embed(session.get())
    view = EmbedBuilderView(session, interaction.client.get_cog("EmbedCreator"))
    await interaction.response.edit_message(
        content=f"Embed builder (Embed {session.current+1}/{len(session.embeds)})",
        embed=embed,
        view=view
    )

class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Start the interactive embed builder")
    async def embed(self, interaction: discord.Interaction):
        if EMBED_CREATOR_ROLE not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        session = EmbedSession(interaction.user.id)
        embed = session_to_embed(session.get())
        view = EmbedBuilderView(session, self)
        await interaction.response.send_message(
            content=f"Embed builder (Embed 1/1)",
            embed=embed,
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))