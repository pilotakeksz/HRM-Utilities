import os
import json
import discord
from discord.ext import commands
from datetime import datetime, timezone

EMBED_DIR = os.path.join(os.path.dirname(__file__), "../embed-builder-web/data/embeds")
LOG_CHANNEL_ID = 1343686645815181382
ALLOWED_ROLE_ID = 1355842403134603275
LOCAL_LOG = os.path.join(os.path.dirname(__file__), "../logs/embed_new.log")

os.makedirs(os.path.dirname(LOCAL_LOG), exist_ok=True)
os.makedirs(EMBED_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOCAL_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

class ChannelSelect(discord.ui.Select):
    def __init__(self, channels):
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Choose target channel", min_values=1, max_values=1, options=options)

class SendView(discord.ui.View):
    def __init__(self, bot, author, payload):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.payload = payload
        self.target_channel = None
        self.add_item(discord.ui.Button(label="Send Public", style=discord.ButtonStyle.primary, custom_id="send_public"))
        self.add_item(discord.ui.Button(label="Send Ephemeral", style=discord.ButtonStyle.secondary, custom_id="send_ephemeral"))

    @discord.ui.select(placeholder="Select channel to send to", min_values=1, max_values=1, options=[])
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        # this method will be replaced on run
        pass

    @discord.ui.button(label="Send Public", style=discord.ButtonStyle.primary, custom_id="send_public")
    async def send_public(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
            return
        if not self.target_channel:
            await interaction.response.send_message("Select a channel first.", ephemeral=True)
            return
        chan = interaction.guild.get_channel(int(self.target_channel))
        if not chan:
            await interaction.response.send_message("Invalid channel selected.", ephemeral=True)
            return
        await interaction.response.defer()
        count = 0
        try:
            plain = self.payload.get("plain_message", "") or None
            for emb in self.payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=emb.get("color", 0)
                )
                if emb.get("thumbnail_url"):
                    e.set_thumbnail(url=emb.get("thumbnail_url"))
                if emb.get("image_url"):
                    e.set_image(url=emb.get("image_url"))
                if emb.get("footer"):
                    e.set_footer(text=emb.get("footer"), icon_url=emb.get("footer_icon"))
                for f in emb.get("fields", []):
                    try:
                        name, value, inline = f
                        e.add_field(name=name[:256], value=value[:1024], inline=bool(inline))
                    except Exception:
                        pass
                view = None
                if emb.get("buttons"):
                    view = discord.ui.View()
                    for b in emb.get("buttons", []):
                        # b = dict with type,label,url,target,icon,ephemeral in our frontend
                        if b.get("type") == "link" and b.get("url"):
                            view.add_item(discord.ui.Button(label=b.get("label","link"), style=discord.ButtonStyle.link, url=b.get("url")))
                        elif b.get("type") == "send_embed":
                            # create a button that triggers a custom_id handled elsewhere (not implemented here)
                            btn = discord.ui.Button(label=b.get("label","send"), style=discord.ButtonStyle.secondary, custom_id=f"sendembed:{b.get('target') or ''}:{'e' if b.get('ephemeral') else 'p'}")
                            view.add_item(btn)
                await chan.send(content=plain, embed=e, view=view)
                count += 1
            await interaction.followup.send(f"Posted {count} embed(s) to {chan.mention}.", ephemeral=True)
            # log
            log(f"SEND: {interaction.user} posted key to channel {chan.id} embeds={count}")
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} posted embeds to {chan.mention} (key)")
            except Exception:
                pass
        except Exception as e:
            await interaction.followup.send(f"Failed to post: {e}", ephemeral=True)
            log(f"ERROR posting: {e}")

    @discord.ui.button(label="Send Ephemeral", style=discord.ButtonStyle.secondary, custom_id="send_ephemeral")
    async def send_ephemeral(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        count = 0
        try:
            for emb in self.payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=emb.get("color", 0)
                )
                if emb.get("thumbnail_url"):
                    e.set_thumbnail(url=emb.get("thumbnail_url"))
                if emb.get("image_url"):
                    e.set_image(url=emb.get("image_url"))
                if emb.get("footer"):
                    e.set_footer(text=emb.get("footer"), icon_url=emb.get("footer_icon"))
                for f in emb.get("fields", []):
                    try:
                        name, value, inline = f
                        e.add_field(name=name[:256], value=value[:1024], inline=bool(inline))
                    except Exception:
                        pass
                await interaction.followup.send(embed=e, ephemeral=True)
                count += 1
            await interaction.followup.send(f"Sent {count} ephemeral embed(s) to you.", ephemeral=True)
            log(f"SEND_EPHEMERAL: {interaction.user} embeds={count}")
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} sent ephemeral embeds (key)")
            except Exception:
                pass
        except Exception as e:
            await interaction.followup.send(f"Failed to send ephemeral: {e}", ephemeral=True)
            log(f"ERROR ephemeral posting: {e}")

class EmbedNewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="embed_send")
    async def embed_send(self, ctx, key_or_json: str):
        """Interactive send of saved embed(s). Usage: !embed_send <key> or paste JSON string"""
        # role check
        if not any(r.id == ALLOWED_ROLE_ID for r in getattr(ctx.author, "roles", [])):
            await ctx.send("You do not have permission to run this command.", ephemeral=True)
            return

        # load payload
        payload = None
        # detect JSON
        if key_or_json.strip().startswith("{") or key_or_json.strip().startswith("["):
            try:
                data = json.loads(key_or_json)
                payload = data if isinstance(data, dict) else {"embeds": data}
            except Exception as e:
                await ctx.send(f"Invalid JSON: {e}")
                return
        else:
            path = os.path.join(EMBED_DIR, f"{key_or_json}.json")
            if not os.path.exists(path):
                await ctx.send("Key not found in embed storage.")
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                payload = saved.get("payload") or saved
            except Exception as e:
                await ctx.send(f"Failed to read key file: {e}")
                return

        # present interactive view to choose channel and confirm
        channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
        view = SendView(self.bot, ctx.author, payload)
        # replace the placeholder select with a concrete one
        sel = ChannelSelect(channels)
        async def sel_callback(interaction, select):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Only the invoker can use this.", ephemeral=True)
                return
            view.target_channel = select.values[0]
            await interaction.response.edit_message(content=f"Selected channel: <#{view.target_channel}>. Use Send Public or Send Ephemeral.", view=view)
        sel.callback = sel_callback
        # add to view (insert at top)
        view.add_item(sel)
        await ctx.send("Choose a target channel then press Send Public (posts to channel) or Send Ephemeral (sends only to you).", view=view)
        log(f"INTERACTIVE_SEND_STARTED by {ctx.author} key_or_json={key_or_json}")

async def setup(bot):
    await bot.add_cog(EmbedNewCog(bot))