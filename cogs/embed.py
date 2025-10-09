import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import uuid
from datetime import datetime

EMBED_CREATOR_ROLE = 1329910230066401361
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/embed_builder.db")
LOG_PATH = os.path.join(os.path.dirname(__file__), "../logs/embed_builder.txt")

def log_action(user, action, extra=""):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}] {user} ({user.id}) {action} {extra}\n")

class EmbedSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.embeds = [self._new_embed()]
        self.current = 0

    def _new_embed(self):
        return {
            "title": "",
            "description": " ",  # <-- fallback to space if empty
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
    def __init__(self, session, cog, parent_interaction):
        super().__init__(timeout=900)
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction

        # Row 0: Navigation
        self.add_item(PrevEmbedButton(session, parent_interaction, row=0))
        self.add_item(NextEmbedButton(session, parent_interaction, row=0))
        self.add_item(AddEmbedButton(session, parent_interaction, row=0))
        self.add_item(RemoveEmbedButton(session, parent_interaction, row=0))

        # Row 1: Main properties
        self.add_item(EditTitleButton(session, parent_interaction, row=1))
        self.add_item(EditDescriptionButton(session, parent_interaction, row=1))
        self.add_item(EditColorButton(session, parent_interaction, row=1))

        # Row 2: Images & Footer
        self.add_item(EditImageButton(session, parent_interaction, row=2))
        self.add_item(EditThumbnailButton(session, parent_interaction, row=2))
        self.add_item(EditFooterButton(session, parent_interaction, row=2))
        self.add_item(EditFooterIconButton(session, parent_interaction, row=2))

        # Row 3: Fields
        self.add_item(AddFieldButton(session, parent_interaction, row=3))
        # allow editing a specific field by selecting its name
        self.add_item(EditFieldByNameButton(session, parent_interaction, row=3))
        self.add_item(RemoveFieldButton(session, parent_interaction, row=3))

        # Row 4: Link buttons & Actions
        self.add_item(AddLinkButtonButton(session, parent_interaction, row=4))
        self.add_item(RemoveLinkButtonButton(session, parent_interaction, row=4))
        # list sessions button (new)
        self.add_item(ListSessionsButton(session, parent_interaction, row=4))
        self.add_item(DoneButton(session, cog, parent_interaction, row=4))
        # place Save/Load on row 3 so no row exceeds 5 components (rows must be 0-4)
        self.add_item(SaveButton(session, cog, parent_interaction, row=3))
        self.add_item(LoadButton(session, cog, parent_interaction, row=3))

# Navigation
class PrevEmbedButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=0):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        if self.session.current > 0:
            self.session.current -= 1
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Switched embed!", ephemeral=True, delete_after=2)

class NextEmbedButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=0):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        if self.session.current < len(self.session.embeds) - 1:
            self.session.current += 1
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Switched embed!", ephemeral=True, delete_after=2)

class AddEmbedButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=0):
        super().__init__(label="➕ Add Embed", style=discord.ButtonStyle.success, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        self.session.add_embed()
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Embed added!", ephemeral=True, delete_after=2)

class RemoveEmbedButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=0):
        super().__init__(label="🗑 Remove Embed", style=discord.ButtonStyle.danger, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        self.session.remove_embed(self.session.current)
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Embed removed!", ephemeral=True, delete_after=2)

# Main properties (blue buttons)
class EditTitleButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=1):
        super().__init__(label="Title", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TitleModal(self.session, self.parent_interaction))

class TitleModal(discord.ui.Modal, title="Set Embed Title"):
    title_input = discord.ui.TextInput(label="Title", required=False)

    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction

    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["title"] = self.title_input.value if self.title_input.value.strip() else "(NO CONTENT)"
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Title updated!", ephemeral=True, delete_after=2)

class EditDescriptionButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=1):
        super().__init__(label="Description", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DescriptionModal(self.session, self.parent_interaction))

class DescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    description = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction

    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["description"] = self.description.value if self.description.value.strip() else "(NO CONTENT)"
        await update_embed_preview(self.parent_interaction, self.session)
        await interaction.response.send_message("Description updated!", ephemeral=True, delete_after=2)

class EditColorButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=1):
        super().__init__(label="Color", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ColorModal(self.session, self.parent_interaction))

class ColorModal(discord.ui.Modal, title="Set Embed Color"):
    color = discord.ui.TextInput(label="Color (hex, e.g. 0x2f3136)", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.session.get()["color"] = int(self.color.value, 16)
            await update_embed_preview(self.parent_interaction, self.session)
            await interaction.response.send_message("Color updated!", ephemeral=True, delete_after=2)
        except Exception:
            await interaction.response.send_message("Invalid color format.", ephemeral=True, delete_after=2)

# Images & Footer
class EditImageButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=2):
        super().__init__(label="Image", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ImageModal(self.session, self.parent_interaction))

class ImageModal(discord.ui.Modal, title="Set Embed Image"):
    image_url = discord.ui.TextInput(label="Image URL", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["image_url"] = self.image_url.value
        await update_embed_preview(self.parent_interaction, self.session)

class EditThumbnailButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=2):
        super().__init__(label="Thumbnail", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThumbnailModal(self.session, self.parent_interaction))

class ThumbnailModal(discord.ui.Modal, title="Set Embed Thumbnail"):
    thumbnail_url = discord.ui.TextInput(label="Thumbnail URL", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["thumbnail_url"] = self.thumbnail_url.value
        await update_embed_preview(self.parent_interaction, self.session)

class EditFooterButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=2):
        super().__init__(label="Footer", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterModal(self.session, self.parent_interaction))

class FooterModal(discord.ui.Modal, title="Set Embed Footer"):
    footer = discord.ui.TextInput(label="Footer Text", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["footer"] = self.footer.value
        await update_embed_preview(self.parent_interaction, self.session)

class EditFooterIconButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=2):
        super().__init__(label="Footer Icon", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterIconModal(self.session, self.parent_interaction))

class FooterIconModal(discord.ui.Modal, title="Set Footer Icon URL"):
    footer_icon = discord.ui.TextInput(label="Footer Icon URL", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["footer_icon"] = self.footer_icon.value
        await update_embed_preview(self.parent_interaction, self.session)

# Fields
class AddFieldButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=3):
        super().__init__(label="Add Field", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FieldModal(self.session, self.parent_interaction))

class FieldModal(discord.ui.Modal, title="Add Field"):
    name = discord.ui.TextInput(label="Field Name", required=True)
    value = discord.ui.TextInput(label="Field Value", required=True, style=discord.TextStyle.paragraph)
    inline = discord.ui.TextInput(label="Inline? (true/false)", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        inline_bool = self.inline.value.lower() == "true"
        self.session.get()["fields"].append((self.name.value, self.value.value, inline_bool))
        await update_embed_preview(self.parent_interaction, self.session)

class RemoveFieldButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=3):
        super().__init__(label="Remove Field", style=discord.ButtonStyle.danger, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        fields = self.session.get()["fields"]
        if fields:
            fields.pop()
        await update_embed_preview(self.parent_interaction, self.session)

# new: edit a specific field by selecting name
class EditFieldByNameButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=3):
        super().__init__(label="Edit Field (by name)", style=discord.ButtonStyle.primary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction

    async def callback(self, interaction: discord.Interaction):
        fields = self.session.get()["fields"]
        if not fields:
            await interaction.response.send_message("No fields to edit.", ephemeral=True)
            return

        # build a select with each field name (show index to disambiguate)
        view = FieldSelectView(self.session, self.parent_interaction)
        await interaction.response.send_message("Select a field to edit:", view=view, ephemeral=True)

class FieldSelect(discord.ui.Select):
    def __init__(self, session, parent_interaction):
        self.session = session
        self.parent_interaction = parent_interaction
        options = []
        for idx, (name, value, inline) in enumerate(self.session.get()["fields"]):
            display_name = name if name.strip() else "(NO NAME)"
            # truncate label/description to safe lengths for Discord
            label = display_name[:100]
            description = f"Field #{idx+1}"[:100]
            options.append(discord.SelectOption(label=label, value=str(idx), description=description))
        super().__init__(placeholder="Choose a field...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            idx = int(self.values[0])
            name, value, inline = self.session.get()["fields"][idx]
            inline_str = "true" if inline else "false"
            # open modal prefilled with current values
            modal = FieldEditModal(self.session, self.parent_interaction, idx, name, value, inline_str)
            await interaction.response.send_modal(modal)
            # stop the view so the ephemeral select can be cleaned up
            if self.view:
                self.view.stop()
        except Exception as e:
            # surface error to user instead of generic "This interaction failed"
            await interaction.response.send_message("Failed to open field editor.", ephemeral=True)
            # optional: log for debugging
            print(f"FieldSelect callback error: {e}")

class FieldSelectView(discord.ui.View):
    def __init__(self, session, parent_interaction, timeout=60):
        super().__init__(timeout=timeout)
        self.session = session
        self.parent_interaction = parent_interaction
        self.add_item(FieldSelect(session, parent_interaction))

# modal to edit a specific field; prefill values
class FieldEditModal(discord.ui.Modal, title="Edit Field"):
    name = discord.ui.TextInput(label="Field Name", required=True)
    value = discord.ui.TextInput(label="Field Value", required=True, style=discord.TextStyle.paragraph)
    inline = discord.ui.TextInput(label="Inline? (true/false)", required=True)

    def __init__(self, session, parent_interaction, index, initial_name, initial_value, initial_inline):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
        self.index = index
        # prefill defaults
        self.name.default = initial_name
        self.value.default = initial_value
        self.inline.default = initial_inline

    async def on_submit(self, interaction: discord.Interaction):
        inline_bool = self.inline.value.lower() == "true"
        fields = self.session.get()["fields"]
        # guard index validity
        if 0 <= self.index < len(fields):
            fields[self.index] = (self.name.value, self.value.value, inline_bool)
            await update_embed_preview(self.parent_interaction, self.session)
            await interaction.response.send_message("Field updated!", ephemeral=True, delete_after=3)
        else:
            await interaction.response.send_message("Field no longer exists.", ephemeral=True)

# Link buttons & Actions (row 4)
class AddLinkButtonButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=4):
        super().__init__(label="Add Link Button", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LinkButtonModal(self.session, self.parent_interaction))

class LinkButtonModal(discord.ui.Modal, title="Add Link Button"):
    label = discord.ui.TextInput(label="Button Label", required=True)
    url = discord.ui.TextInput(label="Button URL", required=True)
    def __init__(self, session, parent_interaction):
        super().__init__()
        self.session = session
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        self.session.get()["buttons"].append((self.label.value, self.url.value))
        await update_embed_preview(self.parent_interaction, self.session)

class RemoveLinkButtonButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=4):
        super().__init__(label="Remove Link Button", style=discord.ButtonStyle.danger, row=row)
        self.session = session
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        buttons = self.session.get()["buttons"]
        if buttons:
            buttons.pop()
        await update_embed_preview(self.parent_interaction, self.session)

# new: list saved sessions (non-destructive)
class ListSessionsButton(discord.ui.Button):
    def __init__(self, session, parent_interaction, row=4):
        super().__init__(label="List Saved Sessions", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.parent_interaction = parent_interaction

    async def callback(self, interaction: discord.Interaction):
        # Ensure DB/table exists and (if needed) has 'name' column
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS embed_sessions (key TEXT PRIMARY KEY, user_id INTEGER, embeds TEXT, created_at TEXT, name TEXT)"
            )
            try:
                await db.execute("ALTER TABLE embed_sessions ADD COLUMN name TEXT")
                await db.commit()
            except Exception:
                # column probably already exists; ignore
                pass

            # list sessions for this user (non-destructive)
            async with db.execute(
                "SELECT key, name, created_at FROM embed_sessions WHERE user_id = ? ORDER BY created_at DESC",
                (self.session.user_id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("No saved sessions found.", ephemeral=True)
            return

        lines = []
        for key, name, created_at in rows:
            display_name = (name.strip() if name and name.strip() else "NO NAME")
            lines.append(f"`{key}` - {display_name} - {created_at}")

        # send ephemeral list
        chunk = "\n".join(lines)
        # If too long, truncate
        if len(chunk) > 1900:
            chunk = chunk[:1900] + "\n...(truncated)"
        await interaction.response.send_message(f"Saved sessions:\n{chunk}", ephemeral=True)

class DoneButton(discord.ui.Button):
    def __init__(self, session, cog, parent_interaction, row=4):
        super().__init__(label="Send Embeds", style=discord.ButtonStyle.success, row=row)
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChannelModal(self.session, self.cog, self.parent_interaction))

class ChannelModal(discord.ui.Modal, title="Send Embeds"):
    channel_id = discord.ui.TextInput(label="Channel ID", required=True)
    def __init__(self, session, cog, parent_interaction):
        super().__init__()
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(int(self.channel_id.value))
        if not channel:
            await interaction.response.send_message("Invalid channel ID.", ephemeral=True)
            return
        for embed_data in self.session.embeds:
            embed = session_to_embed(embed_data, for_preview=False)
            view = session_to_view(embed_data)
            await channel.send(embed=embed, view=view)
        log_action(interaction.user, "sent_embeds")
        await interaction.response.send_message("Embeds sent!", ephemeral=True)

class SaveButton(discord.ui.Button):
    def __init__(self, session, cog, parent_interaction, row=4):
        super().__init__(label="Save Session", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        # Open modal to ask for a name (non-destructive save)
        await interaction.response.send_modal(SaveSessionModal(self.session, self.cog, self.parent_interaction))

# new modal to provide a name for the session (if empty -> NO NAME)
class SaveSessionModal(discord.ui.Modal, title="Save Session"):
    name = discord.ui.TextInput(label="Session Name (optional)", required=False)

    def __init__(self, session, cog, parent_interaction):
        super().__init__()
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction

    async def on_submit(self, interaction: discord.Interaction):
        key = str(uuid.uuid4())[:8]
        name_val = self.name.value.strip() if self.name.value and self.name.value.strip() else "NO NAME"
        async with aiosqlite.connect(DB_PATH) as db:
            # ensure table exists with 'name' column
            await db.execute(
                "CREATE TABLE IF NOT EXISTS embed_sessions (key TEXT PRIMARY KEY, user_id INTEGER, embeds TEXT, created_at TEXT, name TEXT)"
            )
            try:
                await db.execute("ALTER TABLE embed_sessions ADD COLUMN name TEXT")
                await db.commit()
            except Exception:
                # column probably already exists; ignore
                pass

            await db.execute(
                "INSERT INTO embed_sessions (key, user_id, embeds, created_at, name) VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    self.session.user_id,
                    repr(self.session.embeds),
                    datetime.utcnow().isoformat(),
                    name_val
                )
            )
            await db.commit()
        log_action(interaction.user, "saved_session", key)
        await interaction.response.send_message(f"Session saved! Your key: `{key}` (name: {name_val})", ephemeral=True)

class LoadButton(discord.ui.Button):
    def __init__(self, session, cog, parent_interaction, row=4):
        super().__init__(label="Load Session", style=discord.ButtonStyle.secondary, row=row)
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LoadSessionModal(self.session, self.cog, self.parent_interaction))

class LoadSessionModal(discord.ui.Modal, title="Load Session"):
    key = discord.ui.TextInput(label="Session Key", required=True)
    def __init__(self, session, cog, parent_interaction):
        super().__init__()
        self.session = session
        self.cog = cog
        self.parent_interaction = parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM embed_sessions WHERE key = ?", (self.key.value,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    self.session.embeds = eval(row[2])
                    self.session.current = 0
                    await update_embed_preview(self.parent_interaction, self.session)
                else:
                    await interaction.response.send_message("No session found with that key.", ephemeral=True)

def session_to_embed(embed_data, for_preview=True):
    # For preview: use "(NO CONTENT)" if the field is truly empty
    # For sending: leave blank if empty
    if for_preview:
        title = embed_data["title"] if embed_data["title"].strip() else "(NO CONTENT)"
        description = embed_data["description"] if embed_data["description"].strip() else "(NO CONTENT)"
        footer = embed_data["footer"] if embed_data["footer"].strip() else "(NO CONTENT)"
    else:
        title = embed_data["title"] if embed_data["title"].strip() else None
        description = embed_data["description"] if embed_data["description"].strip() else None
        footer = embed_data["footer"] if embed_data["footer"].strip() else None
    
    embed = discord.Embed(
        title=title[:256] if title else None,
        description=description[:4096] if description else None,
        color=embed_data["color"]
    )
    if embed_data["image_url"]:
        embed.set_image(url=embed_data["image_url"])
    if embed_data["thumbnail_url"]:
        embed.set_thumbnail(url=embed_data["thumbnail_url"])
    if footer:
        embed.set_footer(
            text=footer[:2048],
            icon_url=embed_data["footer_icon"] if embed_data["footer_icon"] else None
        )
    # Only add up to 25 fields, truncate name/value
    for name, value, inline in embed_data["fields"][:25]:
        if for_preview:
            field_name = name if name.strip() else "(NO CONTENT)"
            field_value = value if value.strip() else "(NO CONTENT)"
        else:
            field_name = name if name.strip() else None
            field_value = value if value.strip() else None
        
        if field_name and field_value:
            embed.add_field(
                name=field_name[:256],
                value=field_value[:1024],
                inline=inline
            )
    return embed

def session_to_view(embed_data):
    view = discord.ui.View()
    for label, url in embed_data["buttons"]:
        view.add_item(EmbedButton(label, url))
    return view

async def update_embed_preview(parent_interaction, session):
    embed = session_to_embed(session.get(), for_preview=True)
    view = EmbedBuilderView(session, parent_interaction.client.get_cog("EmbedCreator"), parent_interaction)
    try:
        await parent_interaction.edit_original_response(
            content=f"Embed builder (Embed {session.current+1}/{len(session.embeds)})",
            embed=embed,
            view=view
        )
    except discord.errors.InteractionResponded:
        await parent_interaction.message.edit(
            content=f"Embed builder (Embed {session.current+1}/{len(session.embeds)})",
            embed=embed,
            view=view
        )

class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Start the interactive embed builder")
    async def embed(self, interaction: discord.Interaction):
        print("DEBUG: /embed command called")
        try:
            member = interaction.guild.get_member(interaction.user.id)
            print(f"DEBUG: member={member}")
            if not member or EMBED_CREATOR_ROLE not in [role.id for role in member.roles]:
                print("DEBUG: Permission denied")
                await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
                return
            session = EmbedSession(interaction.user.id)
            embed = session_to_embed(session.get(), for_preview=True)
            view = EmbedBuilderView(session, self, interaction)
            print("DEBUG: Sending builder message")
            await interaction.response.send_message(
                content=f"Embed builder (Embed 1/1)",
                embed=embed,
                view=view,
                ephemeral=False
            )
            log_action(interaction.user, "started_builder")
        except Exception as e:
            print(f"ERROR in /embed: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))