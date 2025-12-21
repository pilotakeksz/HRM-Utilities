import os
import json
import base64
import uuid
import threading
import asyncio
from typing import Optional, List, Dict, Any

import discord
from discord import app_commands, ui
from discord.ext import commands

EMBED_DIR = os.path.join(os.path.dirname(__file__), "data", "embeds")
os.makedirs(EMBED_DIR, exist_ok=True)
SEND_MAP_FILE = os.path.join(EMBED_DIR, "send_map.json")
_SEND_MAP_LOCK = threading.Lock()

LOG_CHANNEL_ID = None  # optional


def _load_send_map() -> Dict[str, Any]:
    with _SEND_MAP_LOCK:
        try:
            if os.path.exists(SEND_MAP_FILE):
                with open(SEND_MAP_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}


def _save_send_map(m: Dict[str, Any]):
    with _SEND_MAP_LOCK:
        tmp = SEND_MAP_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(tmp, SEND_MAP_FILE)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass


def _put_send_map_entry(entry: Dict[str, Any]) -> str:
    m = _load_send_map()
    key = uuid.uuid4().hex
    m[key] = entry
    _save_send_map(m)
    return key


def _get_send_map_entry(key: str) -> Optional[Dict[str, Any]]:
    m = _load_send_map()
    return m.get(key)


def _parse_color(val):
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
    for f in field_list or []:
        if isinstance(f, (list, tuple)):
            try:
                name, value, inline = f
            except Exception:
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
            name = "field"
            value = str(f)
            inline = False
        yield (str(name)[:256], str(value)[:1024], bool(inline))


def _get_url(obj: Dict[str, Any], *keys) -> Optional[str]:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, dict):
            if v.get("url"):
                return v.get("url")
        elif v:
            return v
    return None


def _decode_base64_json_token(token: str):
    s = token.strip()
    if not s:
        raise ValueError("Empty base64 payload")
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    last_err = None
    raw = None
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            raw = decoder(s)
            break
        except Exception as ex:
            last_err = ex
            raw = None
    if raw is None:
        raise ValueError(f"Base64 decode failed: {last_err}")
    try:
        text = raw.decode("utf-8").strip()
    except Exception as ex:
        raise ValueError(f"UTF-8 decode failed: {ex}")
    if not text:
        raise ValueError("Decoded JSON payload is empty")
    return json.loads(text)


def _build_discord_embed(eobj: Dict[str, Any]) -> discord.Embed:
    emb = discord.Embed(
        title=eobj.get("title") or None,
        description=eobj.get("description") or None,
        color=_parse_color(eobj.get("color"))
    )
    if (thumb := _get_url(eobj, "thumbnail", "thumbnail_url")):
        try: emb.set_thumbnail(url=thumb)
        except Exception: pass
    if (img := _get_url(eobj, "image", "image_url")):
        try: emb.set_image(url=img)
        except Exception: pass
    if (author := eobj.get("author")) and isinstance(author, dict) and author.get("name"):
        try:
            emb.set_author(name=author.get("name"), url=author.get("url"), icon_url=author.get("icon_url"))
        except Exception:
            pass
    footer = eobj.get("footer") or {}
    if isinstance(footer, dict) and footer.get("text"):
        try:
            emb.set_footer(text=footer.get("text"), icon_url=footer.get("icon_url"))
        except Exception:
            pass
    for name, value, inline in _iter_fields(eobj.get("fields", [])):
        try:
            emb.add_field(name=name, value=value, inline=inline)
        except Exception:
            pass
    return emb


class PayloadView(ui.View):
    """View which stores long targets persistently and ensures select sends only the referenced embed ephemerally."""
    def __init__(self, payload: Dict[str, Any], bot: commands.Bot, *, timeout: Optional[float] = None, persistent: bool = False):
        # If persistent, set timeout to None to prevent expiration
        super().__init__(timeout=timeout if not persistent else None)
        self.payload = payload
        self.bot = bot
        self.persistent = persistent
        # local map of keys created for this view (not required but useful)
        self._local_keys: List[str] = []

        # Handle both new message format and legacy embed format
        first = None
        if payload.get("messages"):
            # New message format - get first embed from first message
            first_message = payload.get("messages", [None])[0]
            if first_message and first_message.get("embeds"):
                first = first_message.get("embeds", [None])[0]
        elif payload.get("embeds"):
            # Legacy embed format
            first = (payload.get("embeds") or [None])[0]
        
        if not first:
            return

        # Buttons
        for b in first.get("buttons", []) or []:
            if b.get("type") == "link" and b.get("url"):
                btn = ui.Button(label=b.get("label") or "Link", style=discord.ButtonStyle.link, url=b.get("url"))
                self.add_item(btn)
            elif b.get("type") == "send_embed":
                label = b.get("label") or "Send"
                target = b.get("target") or ""
                ephemeral = bool(b.get("ephemeral"))
                btn = ui.Button(label=label, style=discord.ButtonStyle.secondary)

                async def make_btn_cb(interaction: discord.Interaction, target=target, ephemeral=ephemeral):
                    await interaction.response.defer(ephemeral=ephemeral)
                    await self._handle_target_send(interaction, target, ephemeral)

                btn.callback = make_btn_cb
                self.add_item(btn)

        # Selects: convert long targets to send_map:<key> and persist them
        for s in first.get("selects", []) or []:
            options = []
            for o in s.get("options", []) or []:
                orig_val = o.get("value") or ""
                use_val = orig_val

                # handle send_json: large base64 JSON embedded in option -> persist
                if orig_val.startswith("send_json:"):
                    b64 = orig_val.split(":", 1)[1]
                    entry = {"type": "send_json", "b64": b64}
                    key = _put_send_map_entry(entry)
                    use_val = f"send_map:{key}"
                    self._local_keys.append(key)

                # handle send:KEY where KEY is present in payload.referenced_messages -> persist the referenced message dict
                elif orig_val.startswith("send:"):
                    keyname = orig_val.split(":", 1)[1]
                    ref = (payload.get("referenced_messages") or {}).get(keyname)
                    if ref:
                        entry = {"type": "ref_message", "message": ref}
                        key = _put_send_map_entry(entry)
                        use_val = f"send_map:{key}"
                        self._local_keys.append(key)
                    else:
                        # leave as send:KEY (will load from EMBED_DIR on demand)
                        use_val = orig_val

                # link: and other short values are left as-is
                else:
                    use_val = orig_val

                # create SelectOption (value will be short)
                option_kwargs = {
                    "label": o.get("label") or o.get("value") or "Option",
                    "value": use_val,
                    "description": o.get("description")
                }
                
                # Add emoji if provided
                if o.get("emoji"):
                    option_kwargs["emoji"] = o.get("emoji")
                
                options.append(discord.SelectOption(**option_kwargs))

            if not options:
                continue

            sel = ui.Select(placeholder=s.get("placeholder") or "Choose…", min_values=1, max_values=1, options=options)

            async def make_sel_cb(interaction: discord.Interaction, select: ui.Select = sel):
                # selection sends only the referenced embed ephemerally
                await interaction.response.defer(ephemeral=True)
                val = (select.values or [None])[0]
                if not val:
                    await interaction.followup.send("No value selected.", ephemeral=True)
                    return

                # if send_map: lookup persisted entry
                if isinstance(val, str) and val.startswith("send_map:"):
                    key = val.split(":", 1)[1]
                    entry = _get_send_map_entry(key)
                    if not entry:
                        await interaction.followup.send("Referenced embed not found (maybe expired or deleted).", ephemeral=True)
                        return
                    # handle entry types
                    if entry.get("type") == "send_json":
                        try:
                            obj = _decode_base64_json_token(entry.get("b64", ""))
                        except Exception as ex:
                            await interaction.followup.send(f"Invalid embedded JSON: {ex}", ephemeral=True)
                            return
                        if isinstance(obj, dict) and obj.get("embeds"):
                            embeds_list = obj.get("embeds", [])
                        elif isinstance(obj, dict) and obj.get("messages"):
                            # Handle new message format - flatten all embeds from all messages
                            embeds_list = []
                            for message in obj.get("messages", []):
                                embeds_list.extend(message.get("embeds", []))
                        elif isinstance(obj, list):
                            embeds_list = obj
                        else:
                            embeds_list = [obj]
                    elif entry.get("type") == "ref_message":
                        message_obj = entry.get("message")
                        if isinstance(message_obj, dict) and message_obj.get("embeds"):
                            embeds_list = message_obj.get("embeds", [])
                        else:
                            embeds_list = [message_obj] if isinstance(message_obj, dict) else (message_obj or [])
                    elif entry.get("type") == "ref_embed":
                        embed_obj = entry.get("embed")
                        embeds_list = [embed_obj] if isinstance(embed_obj, dict) else (embed_obj or [])
                    else:
                        await interaction.followup.send("Unknown mapped entry type.", ephemeral=True)
                        return

                    # send all embeds as a single message ephemerally
                    if embeds_list:
                        try:
                            # Build all embeds
                            discord_embeds = []
                            for eobj in embeds_list:
                                try:
                                    em = _build_discord_embed(eobj)
                                    discord_embeds.append(em)
                                except Exception:
                                    continue
                            
                            if discord_embeds:
                                await interaction.followup.send(embeds=discord_embeds, ephemeral=True)
                            else:
                                await interaction.followup.send("No valid embeds were found.", ephemeral=True)
                        except Exception as e:
                            await interaction.followup.send(f"Error sending embeds: {e}", ephemeral=True)
                    else:
                        await interaction.followup.send("No embeds were found.", ephemeral=True)
                    # NOTE: do NOT send a success confirmation message for ephemeral sends
                    return

                # non-mapped targets handled normally (send:KEY loads saved file; link: posts URL)
                await self._handle_target_send(interaction, val, True)

            sel.callback = make_sel_cb
            self.add_item(sel)

    async def _handle_target_send(self, interaction: discord.Interaction, target: str, ephemeral: bool):
        # target may be: send:KEY, send_json:<b64> (rare), link:<url>, or send_map:<key>
        try:
            if not target:
                await interaction.followup.send("No target specified.", ephemeral=True)
                return

            # direct send_json (if present) -> decode and send only those embeds
            if target.startswith("send_json:"):
                b64 = target.split(":", 1)[1]
                try:
                    obj = _decode_base64_json_token(b64)
                except Exception as ex:
                    await interaction.followup.send(f"Invalid embedded JSON: {ex}", ephemeral=True)
                    return
                if isinstance(obj, dict) and obj.get("embeds"):
                    embeds_list = obj.get("embeds", [])
                elif isinstance(obj, dict) and obj.get("messages"):
                    # Handle new message format - flatten all embeds from all messages
                    embeds_list = []
                    for message in obj.get("messages", []):
                        embeds_list.extend(message.get("embeds", []))
                elif isinstance(obj, list):
                    embeds_list = obj
                else:
                    embeds_list = [obj]

            elif target.startswith("send_map:"):
                key = target.split(":", 1)[1]
                entry = _get_send_map_entry(key)
                if not entry:
                    await interaction.followup.send("Referenced embed not found.", ephemeral=True)
                    return
                if entry.get("type") == "send_json":
                    try:
                        obj = _decode_base64_json_token(entry.get("b64", ""))
                    except Exception as ex:
                        await interaction.followup.send(f"Invalid embedded JSON: {ex}", ephemeral=True)
                        return
                    if isinstance(obj, dict) and obj.get("embeds"):
                        embeds_list = obj.get("embeds", [])
                    elif isinstance(obj, dict) and obj.get("messages"):
                        # Handle new message format - flatten all embeds from all messages
                        embeds_list = []
                        for message in obj.get("messages", []):
                            embeds_list.extend(message.get("embeds", []))
                    elif isinstance(obj, list):
                        embeds_list = obj
                    else:
                        embeds_list = [obj]
                elif entry.get("type") == "ref_message":
                    message_obj = entry.get("message")
                    if isinstance(message_obj, dict) and message_obj.get("embeds"):
                        embeds_list = message_obj.get("embeds", [])
                    else:
                        embeds_list = [message_obj] if isinstance(message_obj, dict) else (message_obj or [])
                elif entry.get("type") == "ref_embed":
                    embed_obj = entry.get("embed")
                    embeds_list = [embed_obj] if isinstance(embed_obj, dict) else (embed_obj or [])
                else:
                    await interaction.followup.send("Unknown mapped entry type.", ephemeral=True)
                    return

            elif target.startswith("send:"):
                key = target.split(":", 1)[1]
                # prefer referenced_messages inside original payload if provided (not persisted)
                ref = (self.payload.get("referenced_messages") or {}).get(key)
                if ref:
                    if isinstance(ref, dict) and ref.get("embeds"):
                        embeds_list = ref.get("embeds", [])
                    else:
                        embeds_list = [ref]
                else:
                    path = os.path.join(EMBED_DIR, f"{key}.json")
                    if not os.path.exists(path):
                        await interaction.followup.send(f"Referenced message '{key}' not found.", ephemeral=True)
                        return
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            saved = json.load(f)
                        payload = saved.get("payload") or saved
                        # Handle both old embed format and new message format
                        if payload.get("embeds"):
                            embeds_list = payload.get("embeds", [])
                        elif payload.get("messages"):
                            embeds_list = []
                            for message in payload.get("messages", []):
                                embeds_list.extend(message.get("embeds", []))
                        else:
                            embeds_list = []
                    except Exception as ex:
                        await interaction.followup.send(f"Failed to load saved message: {ex}", ephemeral=True)
                        return

            elif target.startswith("link:"):
                url = target.split(":", 1)[1]
                await interaction.followup.send(f"<{url}>", ephemeral=ephemeral)
                return

            else:
                await interaction.followup.send(f"Unknown target: {target}", ephemeral=True)
                return

            # send all resolved embeds as a single message
            if embeds_list:
                try:
                    # Build all embeds
                    discord_embeds = []
                    for eobj in embeds_list:
                        try:
                            em = _build_discord_embed(eobj)
                            discord_embeds.append(em)
                        except Exception:
                            continue
                    
                    if discord_embeds:
                        if ephemeral:
                            await interaction.followup.send(embeds=discord_embeds, ephemeral=True)
                        else:
                            if interaction.channel:
                                await interaction.channel.send(embeds=discord_embeds)
                            else:
                                await interaction.followup.send(embeds=discord_embeds, ephemeral=True)
                    else:
                        await interaction.followup.send("No valid embeds were found.", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"Error sending embeds: {e}", ephemeral=True)
            else:
                await interaction.followup.send("No embeds were found.", ephemeral=True)

        except Exception as ex:
            try:
                await interaction.followup.send(f"Error sending embeds: {ex}", ephemeral=True)
            except Exception:
                pass


class JSONCollectorView(ui.View):
    def __init__(self, cog, channel=None, persistent=False):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.channel = channel
        self.persistent = persistent
        self.waiting_for_json = True

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.waiting_for_json = False
        await interaction.response.edit_message(content="JSON collection cancelled.", view=None)

    async def on_timeout(self):
        self.waiting_for_json = False


class EmbedNewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent views on startup
        self._register_persistent_views()

    def _register_persistent_views(self):
        """Register persistent views to survive bot restarts."""
        # Create a generic persistent view that can handle any payload
        class PersistentPayloadView(PayloadView):
            def __init__(self, bot: commands.Bot):
                # Create a minimal payload for the persistent view
                super().__init__({}, bot, persistent=True)
                self.bot = bot
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                # This will be overridden by the actual payload when the view is used
                return True
        
        # Register the persistent view
        self.bot.add_view(PersistentPayloadView(self.bot))

    @app_commands.command(name="send_json", description="Send a complete message JSON (messages with embeds + referenced_messages + actions)")
    @app_commands.describe(channel="Optional target channel", persistent="Make buttons/selects persistent across bot restarts")
    async def send_json(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, persistent: bool = False):
        # Create a view to collect JSON from chat
        view = JSONCollectorView(self, channel, persistent)
        
        embed = discord.Embed(
            title="JSON Collection",
            description="Please send your JSON data in this chat. You can either:\n"
                       "• Send the JSON as a message (if short enough)\n"
                       "• Upload a `.txt` file with the JSON content (for large data)\n\n"
                       "I'll wait for 5 minutes for your response.",
            color=0x7289da
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Start waiting for the user's JSON
        await self._wait_for_json(interaction, view, channel)

    async def _wait_for_json(self, interaction: discord.Interaction, view: JSONCollectorView, channel: Optional[discord.TextChannel] = None):
        """Wait for user to send JSON data in chat."""
        def check(message):
            return (message.author == interaction.user and 
                   message.channel == interaction.channel and
                   view.waiting_for_json)
        
        try:
            # Wait for a message from the user
            message = await self.bot.wait_for('message', check=check, timeout=300)
            
            # Check if it's a file attachment
            if message.attachments:
                attachment = message.attachments[0]
                if attachment.filename.endswith('.txt'):
                    try:
                        # Read the file content
                        content = await attachment.read()
                        json_text = content.decode('utf-8')
                    except Exception as e:
                        await interaction.followup.send(f"Error reading file: {e}", ephemeral=True)
                        return
                else:
                    await interaction.followup.send("Please upload a `.txt` file with your JSON content.", ephemeral=True)
                    return
            else:
                # Use the message content directly
                json_text = message.content
            
            # Parse the JSON
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as e:
                await interaction.followup.send(f"Invalid JSON: {e}", ephemeral=True)
                return
            
            # Process and send the messages
            # Use the persistent flag from the view (fix: was referencing self.persistent which doesn't exist)
            await self._process_and_send_messages(interaction, data, channel, view.persistent)
            
            # Update the original message to show completion
            embed = discord.Embed(
                title="JSON Processed Successfully",
                description="Your JSON data has been processed and sent!",
                color=0x00ff00
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
        except asyncio.TimeoutError:
            await interaction.followup.send("Timeout: No JSON data received within 5 minutes.", ephemeral=True)
            view.waiting_for_json = False
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            view.waiting_for_json = False

    async def _process_and_send_messages(self, interaction: discord.Interaction, data: dict, channel: Optional[discord.TextChannel] = None, persistent: bool = False):
        """Process JSON data and send messages with embeds."""
        if not isinstance(data, dict):
            await interaction.followup.send("JSON must be an object with 'messages' or 'embeds' array.", ephemeral=True)
            return

        # Handle both new message format and legacy embed format
        messages_data = data.get("messages", [])
        embeds_raw = data.get("embeds", [])
        
        if messages_data:
            # New message format
            if not isinstance(messages_data, list) or not messages_data:
                await interaction.followup.send("No messages found in payload.", ephemeral=True)
                return
        elif embeds_raw:
            # Legacy embed format - convert to message format
            if not isinstance(embeds_raw, list) or not embeds_raw:
                await interaction.followup.send("No embeds found in payload.", ephemeral=True)
                return
            messages_data = [{"embeds": embeds_raw}]
        else:
            await interaction.followup.send("No messages or embeds found in payload.", ephemeral=True)
            return

        target = channel or (interaction.channel if interaction.channel else None)
        if not target:
            await interaction.followup.send("No valid target channel found.", ephemeral=True)
            return

        # Send each message
        total_embeds_sent = 0
        for message_data in messages_data:
            embeds_raw = message_data.get("embeds", [])
            if not embeds_raw:
                continue
                
            # Build embeds for this message
            primary_embeds = []
            for e in embeds_raw:
                try:
                    primary_embeds.append(_build_discord_embed(e))
                except Exception:
                    continue

            if not primary_embeds:
                continue

            # Create view for this message (only the first message gets the view)
            view = PayloadView(data, self.bot, persistent=persistent) if total_embeds_sent == 0 else None
            
            try:
                await target.send(embeds=primary_embeds, view=view if view and len(view.children) > 0 else None)
                total_embeds_sent += len(primary_embeds)
            except Exception as ex:
                await interaction.followup.send(f"Failed to send message: {ex}", ephemeral=True)
                return

        if total_embeds_sent > 0:
            await interaction.followup.send(f"Posted {total_embeds_sent} embed(s) across {len(messages_data)} message(s) to {target.mention}. Select options send linked message(s) ephemerally to you.", ephemeral=True)
        else:
            await interaction.followup.send("No valid embeds found to send.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedNewCog(bot))