import discord
from discord.ext import commands
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
        self.title = ""
        self.description = ""
        self.color = 0x2f3136
        self.image_url = ""
        self.thumbnail_url = ""
        self.footer = ""
        self.footer_icon = ""
        self.fields = []  # List of tuples: (name, value, inline)
        self.buttons = [] # List of tuples: (label, url)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "color": str(self.color),
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "footer": self.footer,
            "footer_icon": self.footer_icon,
            "fields": repr(self.fields),
            "buttons": repr(self.buttons),
            "created_at": datetime.utcnow().isoformat()
        }

class EmbedButton(discord.ui.Button):
    def __init__(self, label, url):
        super().__init__(label=label, style=discord.ButtonStyle.link, url=url)

class EmbedBuilderView(discord.ui.View):
    def __init__(self, session, cog):
        super().__init__(timeout=600)
        self.session = session
        self.cog = cog
        self.add_item(AddTitleButton(session))
        self.add_item(AddDescriptionButton(session))
        self.add_item(AddColorButton(session))
        self.add_item(AddImageButton(session))
        self.add_item(AddThumbnailButton(session))
        self.add_item(AddFooterButton(session))
        self.add_item(AddFooterIconButton(session))
        self.add_item(AddFieldButton(session))
        self.add_item(AddButtonButton(session))
        self.add_item(RemoveFieldButton(session))
        self.add_item(RemoveButtonButton(session))
        self.add_item(DoneButton(session, cog))
        self.add_item(SaveButton(session, cog))
        self.add_item(LoadButton(session, cog))
        
        class LoadButton(discord.ui.Button):
            def __init__(self, session, cog):
                super().__init__(label="Load Saved Embed", style=discord.ButtonStyle.secondary)
                self.session = session
                self.cog = cog
        
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_modal(LoadEmbedModal(self.session, self.cog))
        
        class LoadEmbedModal(discord.ui.Modal, title="Load Saved Embed"):
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
                            # Unpack fields and buttons from string representation
                            self.session.title = row[2]
                            self.session.description = row[3]
                            self.session.color = int(row[4])
                            self.session.image_url = row[5]
                            self.session.thumbnail_url = row[6]
                            self.session.footer = row[7]
                            self.session.footer_icon = row[8]
                            self.session.fields = eval(row[9])
                            self.session.buttons = eval(row[10])
                            await interaction.response.send_message("Embed loaded!", ephemeral=True)
                        else:
                            await interaction.response.send_message("No embed found with that key.", ephemeral=True)

class AddTitleButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Title", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TitleModal(self.session))

class TitleModal(discord.ui.Modal, title="Set Embed Title"):
    title = discord.ui.TextInput(label="Title", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.title = self.title.value
        await interaction.response.send_message("Title set!", ephemeral=True)

class AddDescriptionButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Description", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DescriptionModal(self.session))

class DescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    description = discord.ui.TextInput(label="Description", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.description = self.description.value
        await interaction.response.send_message("Description set!", ephemeral=True)

class AddColorButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Set Color", style=discord.ButtonStyle.primary)
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
            self.session.color = int(self.color.value, 16)
            await interaction.response.send_message("Color set!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Invalid color format.", ephemeral=True)

class AddImageButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Image", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ImageModal(self.session))

class ImageModal(discord.ui.Modal, title="Set Embed Image"):
    image_url = discord.ui.TextInput(label="Image URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.image_url = self.image_url.value
        await interaction.response.send_message("Image URL set!", ephemeral=True)

class AddThumbnailButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Thumbnail", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThumbnailModal(self.session))

class ThumbnailModal(discord.ui.Modal, title="Set Embed Thumbnail"):
    thumbnail_url = discord.ui.TextInput(label="Thumbnail URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.thumbnail_url = self.thumbnail_url.value
        await interaction.response.send_message("Thumbnail URL set!", ephemeral=True)

class AddFooterButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Footer", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterModal(self.session))

class FooterModal(discord.ui.Modal, title="Set Embed Footer"):
    footer = discord.ui.TextInput(label="Footer Text", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.footer = self.footer.value
        await interaction.response.send_message("Footer set!", ephemeral=True)

class AddFooterIconButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add/Edit Footer Icon", style=discord.ButtonStyle.primary)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterIconModal(self.session))

class FooterIconModal(discord.ui.Modal, title="Set Footer Icon URL"):
    footer_icon = discord.ui.TextInput(label="Footer Icon URL", required=True)
    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        self.session.footer_icon = self.footer_icon.value
        await interaction.response.send_message("Footer icon set!", ephemeral=True)

class AddFieldButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add Field", style=discord.ButtonStyle.secondary)
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
        self.session.fields.append((self.name.value, self.value.value, inline_bool))
        await interaction.response.send_message("Field added!", ephemeral=True)

class RemoveFieldButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Remove Last Field", style=discord.ButtonStyle.danger)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        if self.session.fields:
            self.session.fields.pop()
            await interaction.response.send_message("Last field removed.", ephemeral=True)
        else:
            await interaction.response.send_message("No fields to remove.", ephemeral=True)

class AddButtonButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Add Link Button", style=discord.ButtonStyle.secondary)
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
        self.session.buttons.append((self.label.value, self.url.value))
        await interaction.response.send_message("Button added!", ephemeral=True)

class RemoveButtonButton(discord.ui.Button):
    def __init__(self, session):
        super().__init__(label="Remove Last Button", style=discord.ButtonStyle.danger)
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        if self.session.buttons:
            self.session.buttons.pop()
            await interaction.response.send_message("Last button removed.", ephemeral=True)
        else:
            await interaction.response.send_message("No buttons to remove.", ephemeral=True)

class DoneButton(discord.ui.Button):
    def __init__(self, session, cog):
        super().__init__(label="Done/Send", style=discord.ButtonStyle.success)
        self.session = session
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChannelModal(self.session, self.cog))

class ChannelModal(discord.ui.Modal, title="Send Embed"):
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
        embed = self.cog.session_to_embed(self.session)
        view = self.cog.session_to_view(self.session)
        await channel.send(embed=embed, view=view)
        log_usage(interaction.user, "sent_embed")
        await interaction.response.send_message("Embed sent!", ephemeral=True)

class SaveButton(discord.ui.Button):
    def __init__(self, session, cog):
        super().__init__(label="Save for Later", style=discord.ButtonStyle.secondary)
        self.session = session
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        key = str(uuid.uuid4())[:8]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS embeds (key TEXT PRIMARY KEY, user_id INTEGER, title TEXT, description TEXT, color TEXT, image_url TEXT, thumbnail_url TEXT, footer TEXT, footer_icon TEXT, fields TEXT, buttons TEXT, created_at TEXT)"
            )
            await db.execute(
                "INSERT INTO embeds (key, user_id, title, description, color, image_url, thumbnail_url, footer, footer_icon, fields, buttons, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    self.session.user_id,
                    self.session.title,
                    self.session.description,
                    str(self.session.color),
                    self.session.image_url,
                    self.session.thumbnail_url,
                    self.session.footer,
                    self.session.footer_icon,
                    repr(self.session.fields),
                    repr(self.session.buttons),
                    datetime.utcnow().isoformat()
                )
            )

class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def session_to_embed(self, session):
        embed = discord.Embed(
            title=session.title,
            description=session.description,
            color=session.color
        )
        if session.image_url:
            embed.set_image(url=session.image_url)
        if session.thumbnail_url:
            embed.set_thumbnail(url=session.thumbnail_url)
        if session.footer:
            embed.set_footer(text=session.footer, icon_url=session.footer_icon if session.footer_icon else discord.Embed.Empty)
        for name, value, inline in session.fields:
            embed.add_field(name=name, value=value, inline=inline)
        return embed

    def session_to_view(self, session):
        view = discord.ui.View()
        for label, url in session.buttons:
            view.add_item(EmbedButton(label, url))
        return view

    @commands.command(name="embed")
    async def embed_command(self, ctx):
        if EMBED_CREATOR_ROLE not in [role.id for role in ctx.author.roles]:
            await ctx.send("You do not have permission to use this command.")
            return
        session = EmbedSession(ctx.author.id)
        view = EmbedBuilderView(session, self)
        await ctx.send("Embed builder started!", view=view)

async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))