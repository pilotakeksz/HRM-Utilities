# ...existing code...
import os
import json
import asyncio
import re
import io
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from datetime import datetime, timezone
import base64
from json import JSONDecodeError

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

def _get_url(obj, *keys):
    """Helper to find url in nested fields like image.url or image_url."""
    for k in keys:
        v = obj.get(k)
        if isinstance(v, dict):
            # look for url inside object
            if v.get("url"):
                return v.get("url")
        elif v:
            return v
    return None

def _decode_base64_json_token(token: str):
    """Robustly decode a base64 token produced by the frontend btoa(...) wrapper and return parsed JSON.
       Raises ValueError on failure with a helpful message.
    """
    s = token.strip()
    if not s:
        raise ValueError("Empty base64 payload")
    # Fix padding
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    # Try standard then urlsafe decode
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
    try:
        return json.loads(text)
    except JSONDecodeError as ex:
        preview = text[:300].replace("\n", "\\n")
        raise ValueError(f"JSON parse error: {ex}. Decoded preview: {preview}")

class ChannelSelect(discord.ui.Select):
    def __init__(self, channels):
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Choose target channel", min_values=1, max_values=1, options=options)

class ComprehensiveSendView(discord.ui.View):
    def __init__(self, bot, author, payload):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.payload = payload
        self.target_channel = None
        self.add_item(discord.ui.Button(label="Send Public", style=discord.ButtonStyle.primary, custom_id="send_public"))
        self.add_item(discord.ui.Button(label="Send Ephemeral", style=discord.ButtonStyle.secondary, custom_id="send_ephemeral"))
        self.add_item(discord.ui.Button(label="Export Complete JSON", style=discord.ButtonStyle.secondary, custom_id="export_json"))
    
    def _convert_to_discord_embed(self, embed_data):
        """Normalize referenced embed object (dict) into a consistent dict form for later building."""
        # keep original structure but ensure keys for thumbnail/image/footer are present
        return {
            "title": embed_data.get("title"),
            "description": embed_data.get("description"),
            "color": embed_data.get("color"),
            "url": embed_data.get("url"),
            "author": embed_data.get("author") or {},
            "thumbnail": embed_data.get("thumbnail") or embed_data.get("thumbnail_url") or {},
            "image": embed_data.get("image") or embed_data.get("image_url") or {},
            "fields": embed_data.get("fields", []),
            "footer": embed_data.get("footer") or embed_data.get("footer_icon") or {},
            "actions": embed_data.get("actions", []) or []
        }

    def _collect_linked_embeds(self):
        """Collect all embed dicts referenced in select menus and buttons (no I/O side-effects)."""
        linked_embeds = []
        seen_keys = set()

        # referenced_embeds first (keeps provided objects)
        if isinstance(self.payload.get("referenced_embeds"), dict):
            for key, embed_data in self.payload["referenced_embeds"].items():
                if key not in seen_keys:
                    seen_keys.add(key)
                    linked_embeds.append(self._convert_to_discord_embed(embed_data))

        for emb in self.payload.get("embeds", []):
            # selects
            for select in emb.get("selects", []) or []:
                for option in select.get("options", []) or []:
                    value = option.get("value", "") if isinstance(option, dict) else ""
                    if value.startswith("send:"):
                        key = value.split(":", 1)[1]
                        if key and key not in seen_keys:
                            seen_keys.add(key)
                            # check referenced_embeds first
                            ref = (self.payload.get("referenced_embeds") or {}).get(key)
                            if ref:
                                linked_embeds.append(self._convert_to_discord_embed(ref))
                            else:
                                # load from file if exists
                                path = os.path.join(EMBED_DIR, f"{key}.json")
                                if os.path.exists(path):
                                    try:
                                        with open(path, "r", encoding="utf-8") as f:
                                            saved = json.load(f)
                                        ref_payload = saved.get("payload") or saved
                                        linked_embeds.extend(ref_payload.get("embeds", []))
                                    except Exception:
                                        # ignore broken saved file
                                        continue
                    elif value.startswith("send_json:"):
                        b64 = value.split(":", 1)[1]
                        try:
                            obj = _decode_base64_json_token(b64)
                        except ValueError:
                            continue
                        # normalize to embeds list and append
                        if isinstance(obj, list):
                            linked_embeds.extend(obj)
                        elif isinstance(obj, dict) and obj.get("embeds"):
                            linked_embeds.extend(obj.get("embeds", []))
                        else:
                            linked_embeds.append(obj)

            # buttons: send_embed targets
            for button in emb.get("buttons", []) or []:
                if button.get("type") == "send_embed":
                    key = button.get("target", "")
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        ref = (self.payload.get("referenced_embeds") or {}).get(key)
                        if ref:
                            linked_embeds.append(self._convert_to_discord_embed(ref))
                        else:
                            path = os.path.join(EMBED_DIR, f"{key}.json")
                            if os.path.exists(path):
                                try:
                                    with open(path, "r", encoding="utf-8") as f:
                                        saved = json.load(f)
                                    ref_payload = saved.get("payload") or saved
                                    linked_embeds.extend(ref_payload.get("embeds", []))
                                except Exception:
                                    continue

        return linked_embeds

    def _add_selects_to_view(self, view, emb, ctx_channel=None, referenced=None):
        """
        Build Select items for the embed dict `emb`.
        referenced: optional dict of referenced_embeds from payload (key -> embed object)
        """
        referenced = referenced or {}
        for si, sel in enumerate(emb.get("selects", []) or []):
            options = []
            for o in sel.get("options", []) or []:
                options.append(discord.SelectOption(
                    label=o.get("label") or o.get("value") or "opt",
                    value=(o.get("value") or ""),
                    description=o.get("description")
                ))
            if not options:
                continue
            sel_obj = discord.ui.Select(placeholder=sel.get("placeholder") or "Choose…", min_values=1, max_values=1, options=options)

            async def sel_callback(interaction: discord.Interaction, select: discord.ui.Select, _sel=sel):
                # restrict to original invoker (change if you want open access)
                if interaction.user.id != self.author.id:
                    await interaction.response.send_message("Only the original invoker can use this.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                val = select.values[0]
                try:
                    # send embedded JSON included in payload (send_json:<b64>)
                    if val.startswith("send_json:"):
                        b64 = val.split(":",1)[1]
                        try:
                            obj = _decode_base64_json_token(b64)
                        except ValueError as ex:
                            await interaction.followup.send(f"Failed to decode JSON option: {ex}", ephemeral=True)
                            return
                        # normalize payload -> ensure {"embeds":[...]}
                        if isinstance(obj, list):
                            payload = {"embeds": obj}
                        elif isinstance(obj, dict) and obj.get("embeds"):
                            payload = obj
                        else:
                            payload = {"embeds": [obj]}
                        target_chan = ctx_channel or interaction.channel
                        sent = 0
                        for eemb in payload.get("embeds", []):
                            e = discord.Embed(
                                title=eemb.get("title") or None,
                                description=eemb.get("description") or None,
                                color=_parse_color(eemb.get("color"))
                            )
                            thumb = _get_url(eemb, "thumbnail", "thumbnail_url")
                            img = _get_url(eemb, "image", "image_url")
                            if thumb: e.set_thumbnail(url=thumb)
                            if img: e.set_image(url=img)
                            if eemb.get("footer"):
                                footer = eemb.get("footer") if isinstance(eemb.get("footer"), dict) else {}
                                footer_text = footer.get("text") or eemb.get("footer")
                                footer_icon = footer.get("icon_url") or eemb.get("footer_icon")
                                e.set_footer(text=footer_text or None, icon_url=footer_icon or None)
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

                    # send referenced embed by key if present in payload referenced_embeds
                    elif val.startswith("send:"):
                        parts = val.split(":", 2)
                        key = parts[1] if len(parts) >= 2 else ""
                        eph = False
                        if len(parts) == 3 and parts[2] == "e":
                            eph = True

                        # prefer referenced_embeds from payload, fallback to local file
                        ref = (referenced or {}).get(key)
                        payload = None
                        if ref:
                            payload = {"embeds": [ref]} if isinstance(ref, dict) else {"embeds": ref}
                        else:
                            path = os.path.join(EMBED_DIR, f"{key}.json")
                            if not os.path.exists(path):
                                await interaction.followup.send(f"Saved key not found: {key}", ephemeral=True)
                                return
                            with open(path, "r", encoding="utf-8") as f:
                                saved = json.load(f)
                            payload = saved.get("payload") or saved

                        target_chan = ctx_channel or interaction.channel
                        sent = 0
                        for eemb in payload.get("embeds", []):
                            e = discord.Embed(
                                title=eemb.get("title") or None,
                                description=eemb.get("description") or None,
                                color=_parse_color(eemb.get("color"))
                            )
                            thumb = _get_url(eemb, "thumbnail", "thumbnail_url")
                            img = _get_url(eemb, "image", "image_url")
                            if thumb: e.set_thumbnail(url=thumb)
                            if img: e.set_image(url=img)
                            if eemb.get("footer"):
                                footer = eemb.get("footer") if isinstance(eemb.get("footer"), dict) else {}
                                footer_text = footer.get("text") or eemb.get("footer")
                                footer_icon = footer.get("icon_url") or eemb.get("footer_icon")
                                e.set_footer(text=footer_text or None, icon_url=footer_icon or None)
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
        try:
            payload = self.payload or {}
            plain = payload.get("plain_message", "") or None

            # build discord.Embed objects for all primary embeds
            embeds_to_send = []
            for emb in payload.get("embeds", []):
                e = discord.Embed(
                    title=emb.get("title") or None,
                    description=emb.get("description") or None,
                    color=_parse_color(emb.get("color"))
                )
                thumb = _get_url(emb, "thumbnail_url", "thumbnail")
                img = _get_url(emb, "image_url", "image")
                if thumb: e.set_thumbnail(url=thumb)
                if img: e.set_image(url=img)
                if emb.get("footer"):
                    footer = emb.get("footer") if isinstance(emb.get("footer"), dict) else {}
                    footer_text = footer.get("text") or emb.get("footer")
                    footer_icon = footer.get("icon_url") or emb.get("footer_icon")
                    e.set_footer(text=footer_text or None, icon_url=footer_icon or None)
                for name, value, inline in _iter_fields(emb.get("fields")):
                    try:
                        e.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        pass
                embeds_to_send.append(e)

            # append referenced_embeds (if any) so they are sent together with the message that contains the menu
            for key, ref in (payload.get("referenced_embeds") or {}).items():
                try:
                    ref_obj = ref
                    e = discord.Embed(
                        title=ref_obj.get("title") or None,
                        description=ref_obj.get("description") or None,
                        color=_parse_color(ref_obj.get("color"))
                    )
                    thumb = _get_url(ref_obj, "thumbnail", "thumbnail_url")
                    img = _get_url(ref_obj, "image", "image_url")
                    if thumb: e.set_thumbnail(url=thumb)
                    if img: e.set_image(url=img)
                    if ref_obj.get("footer"):
                        footer = ref_obj.get("footer") if isinstance(ref_obj.get("footer"), dict) else {}
                        footer_text = footer.get("text") or ref_obj.get("footer")
                        footer_icon = footer.get("icon_url") or ref_obj.get("footer_icon")
                        e.set_footer(text=footer_text or None, icon_url=footer_icon or None)
                    for name, value, inline in _iter_fields(ref_obj.get("fields")):
                        try:
                            e.add_field(name=name, value=value, inline=inline)
                        except Exception:
                            pass
                    embeds_to_send.append(e)
                except Exception:
                    # skip broken referenced embed
                    continue

            # build view (use first embed's actions)
            view = None
            first_emb = payload.get("embeds", [None])[0]
            if first_emb and (first_emb.get("buttons") or first_emb.get("selects")):
                view = discord.ui.View()
                # add buttons
                for b in first_emb.get("buttons", []) or []:
                    if b.get("type") == "link" and b.get("url"):
                        view.add_item(discord.ui.Button(label=b.get("label","link"), style=discord.ButtonStyle.link, url=b.get("url")))
                    elif b.get("type") == "send_embed":
                        btn = discord.ui.Button(label=b.get("label","send"), style=discord.ButtonStyle.secondary, custom_id=f"sendembed:{b.get('target') or ''}:{'e' if b.get('ephemeral') else 'p'}")
                        view.add_item(btn)
                # add selects, pass referenced_embeds mapping so callbacks can find referenced embeds in payload
                self._add_selects_to_view(view, first_emb, ctx_channel=chan, referenced=payload.get("referenced_embeds"))

            # send single message with all embeds + view attached
            if embeds_to_send:
                await chan.send(content=plain, embeds=embeds_to_send, view=view)
            else:
                await interaction.followup.send("No embeds to send.", ephemeral=True)
                return

            await interaction.followup.send(f"Posted {len(payload.get('embeds', []))} embed(s) to {chan.mention}.", ephemeral=True)
            log(f"SEND: {interaction.user} posted key to channel {chan.id} embeds={len(payload.get('embeds', []))}")
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} posted embeds to {chan.mention} (key)")
            except Exception:
                pass
            return
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
                "linked_embeds": linked_embeds,
                "metadata": self.payload.get("metadata", {})
            }
            
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

    @discord.ui.button(label="Export Complete JSON", style=discord.ButtonStyle.secondary, custom_id="export_json")
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Collect all linked embeds
            linked_embeds = self._collect_linked_embeds()
            
            # Create complete JSON payload with all embeds
            complete_payload = {
                "embeds": self.payload.get("embeds", []) + linked_embeds,
                "plain_message": self.payload.get("plain_message", ""),
                "linked_embeds": linked_embeds,
                "metadata": self.payload.get("metadata", {}),
                "export_info": {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "total_embeds": len(self.payload.get("embeds", [])),
                    "linked_embeds_count": len(linked_embeds),
                    "has_actions": any(emb.get("buttons") or emb.get("selects") for emb in self.payload.get("embeds", [])),
                    "exported_by": str(interaction.user)
                }
            }
            
            # Create file and send
            json_str = json.dumps(complete_payload, indent=2, ensure_ascii=False)
            file_obj = discord.File(
                io=io.BytesIO(json_str.encode('utf-8')),
                filename=f"complete_embed_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            await interaction.followup.send(
                f"Complete JSON export with {len(linked_embeds)} linked embeds included:",
                file=file_obj,
                ephemeral=True
            )
            
            log(f"EXPORT: {interaction.user} exported complete JSON with {len(linked_embeds)} linked embeds")
            
        except Exception as e:
            await interaction.followup.send(f"Failed to export JSON: {e}", ephemeral=True)
            log(f"ERROR exporting JSON: {e}")

class KeyModal(ui.Modal, title="Paste embed key or JSON"):
    key_or_json = ui.TextInput(label="Key or full JSON", style=discord.TextStyle.long, placeholder="Paste key or the JSON payload here", required=True)

    def __init__(self, cog, author):
        super().__init__()
        self.cog = cog
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
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
    
    def _convert_to_discord_embed(self, embed_data):
        return {
            "title": embed_data.get("title"),
            "description": embed_data.get("description"),
            "color": embed_data.get("color"),
            "url": embed_data.get("url"),
            "author": embed_data.get("author") or {},
            "thumbnail": embed_data.get("thumbnail") or embed_data.get("thumbnail_url") or {},
            "image": embed_data.get("image") or embed_data.get("image_url") or {},
            "fields": embed_data.get("fields", []),
            "footer": embed_data.get("footer") or embed_data.get("footer_icon") or {},
            "actions": embed_data.get("actions", []) or []
        }

    def _collect_linked_embeds(self):
        """Collect all embeds referenced in select menus and buttons (no I/O side-effects)."""
        linked_embeds = []
        seen_keys = set()

        # referenced_embeds first
        if isinstance(self.payload.get("referenced_embeds"), dict):
            for key, embed_data in self.payload["referenced_embeds"].items():
                if key not in seen_keys:
                    seen_keys.add(key)
                    linked_embeds.append(self._convert_to_discord_embed(embed_data))

        for emb in self.payload.get("embeds", []) or []:
            for select in emb.get("selects", []) or []:
                for option in select.get("options", []) or []:
                    value = option.get("value", "") if isinstance(option, dict) :