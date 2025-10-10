import os
import json
import asyncio
import re
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from datetime import datetime, timezone
import base64

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

# new helper to normalize color values (accept hex string or int)
def _parse_color(val):
    """Return an int color value or None. Accepts hex string like 'fff700' or '#fff700' or integer."""
    if val is None or val == "":
        return None
    try:
        if isinstance(val, str):
            v = val.strip().lstrip("#")
            if v.startswith("0x"):
                v = v[2:]
            return int(v, 16)
        if isinstance(val, (int, float)):
            return int(val)
    except Exception:
        return None
    return None

def _iter_fields(field_list):
    """Yield (name, value, inline) for a variety of stored field shapes."""
    for f in field_list or []:
        if isinstance(f, (list, tuple)):
            # [name, value, inline]
            try:
                name, value, inline = f
            except Exception:
                # try shorter shapes
                try:
                    name, value = f[0], f[1]
                    inline = False
                except Exception:
                    continue
        elif isinstance(f, dict):
            name = f.get("name") or f.get("title") or ""
            value = f.get("value") or f.get("val") or ""
            inline = bool(f.get("inline"))
        else:
            # unknown shape: stringify
            name = "field"
            value = str(f)
            inline = False
        yield (str(name)[:256], str(value)[:1024], bool(inline))

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
    
    def _collect_linked_embeds(self):
        """Collect all embeds referenced in select menus and buttons."""
        linked_embeds = []
        seen_keys = set()
        
        for emb in self.payload.get("embeds", []):
            # Check select menus
            for select in emb.get("selects", []):
                for option in select.get("options", []):
                    value = option.get("value", "")
                    if value.startswith("send:"):
                        # Extract key from send:key format
                        key = value.split(":", 1)[1]
                        if key not in seen_keys:
                            seen_keys.add(key)
                            # Load the referenced embed
                            path = os.path.join(EMBED_DIR, f"{key}.json")
                            if os.path.exists(path):
                                try:
                                    with open(path, "r", encoding="utf-8") as f:
                                        saved = json.load(f)
                                    ref_payload = saved.get("payload") or saved
                                    linked_embeds.extend(ref_payload.get("embeds", []))
                                except Exception:
                                    pass
                    elif value.startswith("send_json:"):
                        # Extract and decode base64 JSON
                        b64 = value.split(":", 1)[1]
                        try:
                            json_text = base64.b64decode(b64).decode("utf-8")
                            obj = json.loads(json_text)
                            if isinstance(obj, list):
                                linked_embeds.extend(obj)
                            elif isinstance(obj, dict) and obj.get("embeds"):
                                linked_embeds.extend(obj["embeds"])
                            else:
                                linked_embeds.append(obj)
                        except Exception:
                            pass
            
            # Check buttons for send_embed type
            for button in emb.get("buttons", []):
                if button.get("type") == "send_embed":
                    key = button.get("target", "")
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        path = os.path.join(EMBED_DIR, f"{key}.json")
                        if os.path.exists(path):
                            try:
                                with open(path, "r", encoding="utf-8") as f:
                                    saved = json.load(f)
                                ref_payload = saved.get("payload") or saved
                                linked_embeds.extend(ref_payload.get("embeds", []))
                            except Exception:
                                pass
        
        return linked_embeds

    # helper to build Select items for a given embed dict and attach callbacks
    def _add_selects_to_view(self, view, emb, ctx_channel=None):
        for si, sel in enumerate(emb.get("selects", []) or []):
            options = []
            for o in sel.get("options", []) or []:
                options.append(discord.SelectOption(label=o.get("label") or o.get("value") or "opt", value=(o.get("value") or ""), description=o.get("description")))
            if not options:
                continue
            sel_obj = discord.ui.Select(placeholder=sel.get("placeholder") or "Choose…", min_values=1, max_values=1, options=options)
            async def sel_callback(interaction: discord.Interaction, select: discord.ui.Select, _sel=sel):
                # restrict if desired (keeps previous behavior)
                if interaction.user.id != self.author.id:
                    await interaction.response.send_message("Only the original invoker can use this.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                val = select.values[0]
                try:
                    if val.startswith("send_json:"):
                        # decode base64 JSON and send that payload
                        b64 = val.split(":",1)[1]
                        try:
                            json_text = base64.b64decode(b64).decode("utf-8")
                            obj = json.loads(json_text)
                        except Exception as ex:
                            await interaction.followup.send(f"Failed to decode JSON option: {ex}", ephemeral=True)
                            return
                        payload = None
                        if isinstance(obj, list):
                            payload = {"embeds": obj}
                        elif isinstance(obj, dict) and obj.get("embeds"):
                            payload = obj
                        else:
                            # assume a single embed object => wrap
                            payload = {"embeds": [obj]}
                        sent = 0
                        target_chan = ctx_channel or interaction.channel
                        for eemb in payload.get("embeds", []):
                            e = discord.Embed(title=eemb.get("title") or None, description=eemb.get("description") or None, color=_parse_color(eemb.get("color")))
                            if eemb.get("thumbnail_url"):
                                e.set_thumbnail(url=eemb.get("thumbnail_url"))
                            if eemb.get("image_url"):
                                e.set_image(url=eemb.get("image_url"))
                            if eemb.get("footer"):
                                e.set_footer(text=eemb.get("footer"), icon_url=eemb.get("footer_icon"))
                            for name, value, inline in _iter_fields(eemb.get("fields")):
                                try:
                                    e.add_field(name=name, value=value, inline=inline)
                                except Exception:
                                    pass
                            if target_chan:
                                await target_chan.send(embed=e)
                            else:
                                await interaction.followup.send(embed=e, ephemeral=True)
                            sent += 1
                        await interaction.followup.send(f"Posted {sent} embed(s).", ephemeral=True)
                        return

                    elif val.startswith("send:"):
                        # existing saved-key behavior (unchanged)
                        parts = val.split(":", 2)
                        key = parts[1] if len(parts) >= 2 else ""
                        eph = False
                        if len(parts) == 3 and parts[2] == "e":
                            eph = True
                        path = os.path.join(EMBED_DIR, f"{key}.json")
                        if not os.path.exists(path):
                            await interaction.followup.send(f"Saved key not found: {key}", ephemeral=True)
                            return
                        with open(path, "r", encoding="utf-8") as f:
                            saved = json.load(f)
                        payload = saved.get("payload") or saved
                        sent = 0
                        target_chan = ctx_channel or interaction.channel
                        for eemb in payload.get("embeds", []):
                            e = discord.Embed(title=eemb.get("title") or None, description=eemb.get("description") or None, color=_parse_color(eemb.get("color")))
                            if eemb.get("thumbnail_url"):
                                e.set_thumbnail(url=eemb.get("thumbnail_url"))
                            if eemb.get("image_url"):
                                e.set_image(url=eemb.get("image_url"))
                            if eemb.get("footer"):
                                e.set_footer(text=eemb.get("footer"), icon_url=eemb.get("footer_icon"))
                            for name, value, inline in _iter_fields(eemb.get("fields")):
                                try:
                                    e.add_field(name=name, value=value, inline=inline)
                                except Exception:
                                    pass
                            if eph:
                                await interaction.followup.send(embed=e, ephemeral=True)
                            else:
                                if target_chan:
                                    await target_chan.send(embed=e)
                                else:
                                    await interaction.followup.send(embed=e, ephemeral=True)
                            sent += 1
                        await interaction.followup.send(f"Posted {sent} embed(s).", ephemeral=True)
                        return

                    elif val.startswith("link:"):
                        url = val.split(":",1)[1]
                        await interaction.followup.send(f"<{url}>", ephemeral=True)
                        return

                    else:
                        await interaction.followup.send(f"Selected: {val}", ephemeral=True)
                        return
                except Exception as ex:
                    await interaction.followup.send(f"Select handling failed: {ex}", ephemeral=True)
                    return
            sel_obj.callback = sel_callback
            view.add_item(sel_obj)

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
            # Collect all linked embeds
            linked_embeds = self._collect_linked_embeds()
            
            # Create complete JSON payload with all embeds
            complete_payload = {
                "embeds": self.payload.get("embeds", []) + linked_embeds,
                "plain_message": self.payload.get("plain_message", ""),
                "linked_embeds": linked_embeds  # Store linked embeds separately for reference
            }
            
            # Send the complete JSON as a code block for reference
            json_str = json.dumps(complete_payload, indent=2, ensure_ascii=False)
            if len(json_str) <= 2000:  # Discord message limit
                await chan.send(f"```json\n{json_str}\n```")
            
            plain = self.payload.get("plain_message", "") or None
            for emb in self.payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=_parse_color(emb.get("color"))
                )
                if emb.get("thumbnail_url"):
                    e.set_thumbnail(url=emb.get("thumbnail_url"))
                if emb.get("image_url"):
                    e.set_image(url=emb.get("image_url"))
                if emb.get("footer"):
                    e.set_footer(text=emb.get("footer"), icon_url=emb.get("footer_icon"))
                for name, value, inline in _iter_fields(emb.get("fields")):
                    try:
                        e.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        pass
                view = None
                # build view with both buttons and selects
                if emb.get("buttons") or emb.get("selects"):
                    view = discord.ui.View()
                    for b in emb.get("buttons", []):
                        if b.get("type") == "link" and b.get("url"):
                            view.add_item(discord.ui.Button(label=b.get("label","link"), style=discord.ButtonStyle.link, url=b.get("url")))
                        elif b.get("type") == "send_embed":
                            btn = discord.ui.Button(label=b.get("label","send"), style=discord.ButtonStyle.secondary, custom_id=f"sendembed:{b.get('target') or ''}:{'e' if b.get('ephemeral') else 'p'}")
                            view.add_item(btn)
                    # add selects and attach callbacks (pass chan so send goes to same channel)
                    self._add_selects_to_view(view, emb, ctx_channel=chan)
                await chan.send(content=plain, embed=e, view=view)
                count += 1
            await interaction.followup.send(f"Posted {count} embed(s) to {chan.mention}. Complete JSON with {len(linked_embeds)} linked embeds included.", ephemeral=True)
            # log
            log(f"SEND: {interaction.user} posted key to channel {chan.id} embeds={count} linked={len(linked_embeds)}")
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
            # Collect all linked embeds
            linked_embeds = self._collect_linked_embeds()
            
            # Create complete JSON payload with all embeds
            complete_payload = {
                "embeds": self.payload.get("embeds", []) + linked_embeds,
                "plain_message": self.payload.get("plain_message", ""),
                "linked_embeds": linked_embeds  # Store linked embeds separately for reference
            }
            
            # Send the complete JSON as a code block for reference
            json_str = json.dumps(complete_payload, indent=2, ensure_ascii=False)
            if len(json_str) <= 2000:  # Discord message limit
                await interaction.followup.send(f"```json\n{json_str}\n```", ephemeral=True)
            
            for emb in self.payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=_parse_color(emb.get("color"))
                )
                if emb.get("thumbnail_url"):
                    e.set_thumbnail(url=emb.get("thumbnail_url"))
                if emb.get("image_url"):
                    e.set_image(url=emb.get("image_url"))
                if emb.get("footer"):
                    e.set_footer(text=emb.get("footer"), icon_url=emb.get("footer_icon"))
                for name, value, inline in _iter_fields(emb.get("fields")):
                    try:
                        e.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        pass
                await interaction.followup.send(embed=e, ephemeral=True)
                count += 1
            await interaction.followup.send(f"Sent {count} ephemeral embed(s) to you. Complete JSON with {len(linked_embeds)} linked embeds included.", ephemeral=True)
            log(f"SEND_EPHEMERAL: {interaction.user} embeds={count} linked={len(linked_embeds)}")
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} sent ephemeral embeds (key)")
            except Exception:
                pass
        except Exception as e:
            await interaction.followup.send(f"Failed to send ephemeral: {e}", ephemeral=True)
            log(f"ERROR ephemeral posting: {e}")

class KeyModal(ui.Modal, title="Paste embed key or JSON"):
    key_or_json = ui.TextInput(label="Key or full JSON", style=discord.TextStyle.long, placeholder="Paste key or the JSON payload here", required=True)

    def __init__(self, cog, author):
        super().__init__()
        self.cog = cog
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        # only allow the invoker
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You cannot submit this form.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await self.cog._handle_modal_payload(interaction, self.key_or_json.value)

class ConfirmView(ui.View):
    def __init__(self, bot, author, payload, target_channel_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.payload = payload
        self.target_channel_id = str(target_channel_id)
    
    def _collect_linked_embeds(self):
        """Collect all embeds referenced in select menus and buttons."""
        linked_embeds = []
        seen_keys = set()
        
        for emb in self.payload.get("embeds", []):
            # Check select menus
            for select in emb.get("selects", []):
                for option in select.get("options", []):
                    value = option.get("value", "")
                    if value.startswith("send:"):
                        # Extract key from send:key format
                        key = value.split(":", 1)[1]
                        if key not in seen_keys:
                            seen_keys.add(key)
                            # Load the referenced embed
                            path = os.path.join(EMBED_DIR, f"{key}.json")
                            if os.path.exists(path):
                                try:
                                    with open(path, "r", encoding="utf-8") as f:
                                        saved = json.load(f)
                                    ref_payload = saved.get("payload") or saved
                                    linked_embeds.extend(ref_payload.get("embeds", []))
                                except Exception:
                                    pass
                    elif value.startswith("send_json:"):
                        # Extract and decode base64 JSON
                        b64 = value.split(":", 1)[1]
                        try:
                            json_text = base64.b64decode(b64).decode("utf-8")
                            obj = json.loads(json_text)
                            if isinstance(obj, list):
                                linked_embeds.extend(obj)
                            elif isinstance(obj, dict) and obj.get("embeds"):
                                linked_embeds.extend(obj["embeds"])
                            else:
                                linked_embeds.append(obj)
                        except Exception:
                            pass
            
            # Check buttons for send_embed type
            for button in emb.get("buttons", []):
                if button.get("type") == "send_embed":
                    key = button.get("target", "")
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        path = os.path.join(EMBED_DIR, f"{key}.json")
                        if os.path.exists(path):
                            try:
                                with open(path, "r", encoding="utf-8") as f:
                                    saved = json.load(f)
                                ref_payload = saved.get("payload") or saved
                                linked_embeds.extend(ref_payload.get("embeds", []))
                            except Exception:
                                pass
        
        return linked_embeds

    async def _do_send(self, interaction: discord.Interaction, ephemeral: bool):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the invoker can confirm.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=ephemeral)
        chan = interaction.guild.get_channel(int(self.target_channel_id))
        if not chan:
            await interaction.followup.send("Target channel not found.", ephemeral=True)
            return

        count = 0
        try:
            # Collect all linked embeds
            linked_embeds = self._collect_linked_embeds()
            
            # Create complete JSON payload with all embeds
            complete_payload = {
                "embeds": self.payload.get("embeds", []) + linked_embeds,
                "plain_message": self.payload.get("plain_message", ""),
                "linked_embeds": linked_embeds  # Store linked embeds separately for reference
            }
            
            # Send the complete JSON as a code block for reference
            json_str = json.dumps(complete_payload, indent=2, ensure_ascii=False)
            if len(json_str) <= 2000:  # Discord message limit
                if ephemeral:
                    await interaction.followup.send(f"```json\n{json_str}\n```", ephemeral=True)
                else:
                    await chan.send(f"```json\n{json_str}\n```")

            plain = self.payload.get("plain_message", "") or None
            for emb in self.payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=_parse_color(emb.get("color"))
                )
                if emb.get("thumbnail_url"):
                    e.set_thumbnail(url=emb.get("thumbnail_url"))
                if emb.get("image_url"):
                    e.set_image(url=emb.get("image_url"))
                if emb.get("footer"):
                    e.set_footer(text=emb.get("footer"), icon_url=emb.get("footer_icon"))
                for name, value, inline in _iter_fields(emb.get("fields")):
                    try:
                        e.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        pass
                view = None
                if emb.get("buttons"):
                    view = ui.View()
                    for b in emb.get("buttons", []):
                        if b.get("type") == "link" and b.get("url"):
                            view.add_item(ui.Button(label=b.get("label","link"), style=discord.ButtonStyle.link, url=b.get("url")))
                        elif b.get("type") == "send_embed":
                            btn = ui.Button(label=b.get("label","send"), style=discord.ButtonStyle.secondary, custom_id=f"sendembed:{b.get('target') or ''}:{'e' if b.get('ephemeral') else 'p'}")
                            view.add_item(btn)
                if ephemeral:
                    # ephemeral messages can't be posted to other channels, so send ephemeral to invoker
                    await interaction.followup.send(embed=e, ephemeral=True)
                else:
                    await chan.send(content=plain, embed=e, view=view)
                count += 1

            if ephemeral:
                await interaction.followup.send(f"Sent {count} ephemeral embed(s). Complete JSON with {len(linked_embeds)} linked embeds included.", ephemeral=True)
            else:
                await interaction.followup.send(f"Posted {count} embed(s) to {chan.mention}. Complete JSON with {len(linked_embeds)} linked embeds included.", ephemeral=True)

            log(f"SEND_CONFIRM: {interaction.user} posted key to channel {self.target_channel_id} embeds={count} linked={len(linked_embeds)}")
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} posted embeds to <#{self.target_channel_id}>")
            except Exception:
                pass
        except Exception as e:
            await interaction.followup.send(f"Failed to post: {e}", ephemeral=True)
            log(f"ERROR posting in confirm: {e}")

    @ui.button(label="Confirm (Public)", style=discord.ButtonStyle.success)
    async def confirm_public(self, interaction: discord.Interaction, button: ui.Button):
        await self._do_send(interaction, ephemeral=False)

    @ui.button(label="Confirm (Ephemeral to you)", style=discord.ButtonStyle.secondary)
    async def confirm_ephemeral(self, interaction: discord.Interaction, button: ui.Button):
        await self._do_send(interaction, ephemeral=True)

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the invoker can cancel.", ephemeral=True)
            return
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()

class EmbedNewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # existing helper kept
    def _load_payload_from_key_or_json(self, key_or_json: str, guild=None):
        # same as before (no change)
        key_or_json = key_or_json.strip()
        if key_or_json.startswith("{") or key_or_json.startswith("["):
            try:
                data = json.loads(key_or_json)
                payload = data if isinstance(data, dict) else {"embeds": data}
                return payload, None
            except Exception as e:
                return None, f"Invalid JSON: {e}"
        path = os.path.join(EMBED_DIR, f"{key_or_json}.json")
        if not os.path.exists(path):
            return None, "Key not found in embed storage."
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            payload = saved.get("payload") or saved
            return payload, None
        except Exception as e:
            return None, f"Failed to read key file: {e}"

    async def _handle_modal_payload(self, interaction: discord.Interaction, key_or_json: str):
        # run role check
        if not any(r.id == ALLOWED_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.followup.send("You do not have permission to run this.", ephemeral=True)
            return

        payload, err = self._load_payload_from_key_or_json(key_or_json, guild=interaction.guild)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        # Ask user to paste channel in chat (non-ephemeral) - instruct and wait for message
        prompt = await interaction.followup.send(f"{interaction.user.mention} — please paste the target channel mention (e.g. #channel) or channel ID in this channel within 60s.", ephemeral=False)
        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == prompt.channel.id

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            # parse channel mention or id
            match = re.search(r"<#(\d+)>", msg.content)
            if match:
                chan_id = match.group(1)
            else:
                # maybe raw ID
                content = msg.content.strip()
                if content.isdigit():
                    chan_id = content
                else:
                    await interaction.followup.send("Couldn't parse channel. Please send a channel mention or channel ID.", ephemeral=True)
                    return
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for channel. Cancelled.", ephemeral=True)
            return

        # show confirmation view
        conf_view = ConfirmView(self.bot, interaction.user, payload, chan_id)
        await interaction.followup.send(f"Selected channel: <#{chan_id}> — confirm send below (public or ephemeral to you).", view=conf_view, ephemeral=True)
        log(f"INTERACTIVE_SEND_STARTED by {interaction.user} key_or_json={key_or_json} target_channel={chan_id}")

    @commands.command(name="embed_send")
    async def embed_send(self, ctx, *, key_or_json: str = None):
        """Run interactive flow: show paste form, then ask for channel, then confirm."""
        # If user passed key/json directly, reuse flow without modal
        if key_or_json:
            # run role check
            if not any(r.id == ALLOWED_ROLE_ID for r in getattr(ctx.author, "roles", [])):
                await ctx.send("You do not have permission to run this command.")
                return
            payload, err = self._load_payload_from_key_or_json(key_or_json, guild=ctx.guild)
            if err:
                await ctx.send(err)
                return
            await ctx.send("Paste the target channel (mention or ID) in chat within 60s.")
            def check(m: discord.Message):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                match = re.search(r"<#(\d+)>", msg.content)
                if match:
                    chan_id = match.group(1)
                else:
                    content = msg.content.strip()
                    if content.isdigit():
                        chan_id = content
                    else:
                        await ctx.send("Couldn't parse channel. Cancelled.")
                        return
            except asyncio.TimeoutError:
                await ctx.send("Timed out waiting for channel. Cancelled.")
                return

            conf_view = ConfirmView(self.bot, ctx.author, payload, chan_id)
            await ctx.send(f"Selected channel: <#{chan_id}> — confirm send below.", view=conf_view)
            log(f"INTERACTIVE_SEND_STARTED by {ctx.author} key_or_json={key_or_json} target_channel={chan_id}")
            return

        # show modal to paste key or JSON
        modal = KeyModal(self, ctx.author)
        await ctx.send_modal(modal)

    @app_commands.command(name="embed_send", description="Interactive send of saved embed(s) by key or JSON (modal)")
    async def slash_embed_send(self, interaction: discord.Interaction, key_or_json: str = None):
        # Slash wrapper: if key provided, behave like text; otherwise show modal
        if key_or_json:
            # once used in slash, behave the same as above but using interaction
            if not any(r.id == ALLOWED_ROLE_ID for r in getattr(interaction.user, "roles", [])):
                await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
                return
            payload, err = self._load_payload_from_key_or_json(key_or_json, guild=interaction.guild)
            if err:
                await interaction.response.send_message(err, ephemeral=True)
                return
            await interaction.response.send_message("Please paste the target channel mention or ID in the channel where you invoked the command within 60s.", ephemeral=False)
            def check(m: discord.Message):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                match = re.search(r"<#(\d+)>", msg.content)
                if match:
                    chan_id = match.group(1)
                else:
                    content = msg.content.strip()
                    if content.isdigit():
                        chan_id = content
                    else:
                        await interaction.edit_original_response(content="Couldn't parse channel. Cancelled.")
                        return
            except asyncio.TimeoutError:
                await interaction.edit_original_response(content="Timed out waiting for channel. Cancelled.")
                return

            conf_view = ConfirmView(self.bot, interaction.user, payload, chan_id)
            await interaction.followup.send(f"Selected channel: <#{chan_id}> — confirm send below.", view=conf_view, ephemeral=True)
            log(f"INTERACTIVE_SEND_STARTED by {interaction.user} key_or_json={key_or_json} target_channel={chan_id}")
            return

        # no key — show modal
        modal = KeyModal(self, interaction.user)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(EmbedNewCog(bot))