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
                    value = option.get("value", "") if isinstance(option, dict) else ""
                    if value.startswith("send:"):
                        key = value.split(":", 1)[1]
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
                    elif value.startswith("send_json:"):
                        b64 = value.split(":", 1)[1]
                        try:
                            obj = _decode_base64_json_token(b64)
                        except ValueError:
                            continue
                        if isinstance(obj, list):
                            linked_embeds.extend(obj)
                        elif isinstance(obj, dict) and obj.get("embeds"):
                            linked_embeds.extend(obj.get("embeds", []))
                        else:
                            linked_embeds.append(obj)

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
                "linked_embeds": linked_embeds,
                "metadata": self.payload.get("metadata", {})
            }
            
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
                            view.add_item(ui.Button(
                                label=b.get("label","link"), 
                                style=discord.ButtonStyle.link, 
                                url=b.get("url")
                            ))
                        elif b.get("type") == "send_embed":
                            btn = ui.Button(
                                label=b.get("label","send"), 
                                style=discord.ButtonStyle.secondary, 
                                custom_id=f"sendembed:{b.get('target') or ''}:e"
                            )
                            view.add_item(btn)
                if ephemeral:
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

    def _load_payload_from_key_or_json(self, key_or_json: str, guild=None):
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
        if not any(r.id == ALLOWED_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.followup.send("You do not have permission to run this.", ephemeral=True)
            return

        payload, err = self._load_payload_from_key_or_json(key_or_json, guild=interaction.guild)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        # Ask user to paste channel in chat
        prompt = await interaction.followup.send(f"{interaction.user.mention} — please paste the target channel mention (e.g. #channel) or channel ID in this channel within 60s.", ephemeral=False)
        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == prompt.channel.id

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
                    await interaction.followup.send("Couldn't parse channel. Please send a channel mention or channel ID.", ephemeral=True)
                    return
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for channel. Cancelled.", ephemeral=True)
            return

        # Show confirmation view
        conf_view = ConfirmView(self.bot, interaction.user, payload, chan_id)
        await interaction.followup.send(f"Selected channel: <#{chan_id}> — confirm send below (public or ephemeral to you).", view=conf_view, ephemeral=True)
        log(f"INTERACTIVE_SEND_STARTED by {interaction.user} key_or_json={key_or_json} target_channel={chan_id}")

    @commands.command(name="embed_send")
    async def embed_send(self, ctx, *, key_or_json: str = None):
        """Run interactive flow: show paste form, then ask for channel, then confirm."""
        if key_or_json:
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

        modal = KeyModal(self, ctx.author)
        await ctx.send_modal(modal)

    @app_commands.command(name="embed_send", description="Interactive send of saved embed(s) by key or JSON (modal)")
    async def slash_embed_send(self, interaction: discord.Interaction, key_or_json: str = None):
        if key_or_json:
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

        modal = KeyModal(self, interaction.user)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="embed_webhook", description="Send comprehensive embed data via webhook")
    async def embed_webhook(self, interaction: discord.Interaction, webhook_url: str, key_or_json: str = None):
        """Send comprehensive embed data via webhook with complete JSON export."""
        if not any(r.id == ALLOWED_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        payload, err = self._load_payload_from_key_or_json(key_or_json, guild=interaction.guild)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        try:
            # Create comprehensive webhook payload
            webhook_payload = {
                "embeds": payload.get("embeds", []),
                "metadata": payload.get("metadata", {}),
                "username": "Maple Cliff National Guard",
                "avatar_url": "https://example.com/avatar.png"  # Replace with actual avatar
            }

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=webhook_payload) as response:
                    if response.status in (200, 204):
                        await interaction.followup.send("Webhook sent successfully with complete embed data!", ephemeral=True)
                        log(f"WEBHOOK: {interaction.user} sent webhook to {webhook_url}")
                    else:
                        error_text = await response.text()
                        await interaction.followup.send(f"Webhook failed: {response.status} - {error_text}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Failed to send webhook: {e}", ephemeral=True)
            log(f"ERROR webhook: {e}")

    @app_commands.command(name="embed_send_json", description="Send embeds directly from complete JSON data")
    async def embed_send_json(self, interaction: discord.Interaction, json_data: str, channel: discord.TextChannel = None):
        """Send embeds directly from complete JSON data to a channel."""
        if not any(r.id == ALLOWED_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Parse the JSON data
            data = json.loads(json_data)
            
            # Debug: Log the parsed data structure
            log(f"Parsed JSON data keys: {list(data.keys()) if isinstance(data, dict) else 'non-dict'}")
            
            # Extract embeds from the data
            embeds_data = data.get("embeds", []) if isinstance(data, dict) else []
            log(f"Found {len(embeds_data)} embeds in data")
            
            if not embeds_data:
                await interaction.followup.send("No embeds found in the JSON data.", ephemeral=True)
                return

            # Determine target channel
            target_channel = channel or interaction.channel
            if not target_channel:
                await interaction.followup.send("No valid channel found.", ephemeral=True)
                return

            # Send each embed
            sent_count = 0
            for i, embed_data in enumerate(embeds_data):
                try:
                    # Debug: Log embed data keys
                    log(f"Processing embed {i} keys: {list(embed_data.keys()) if isinstance(embed_data, dict) else 'non-dict'}")
                    
                    if not isinstance(embed_data, dict):
                        log(f"Skipping non-dict embed at index {i}")
                        continue

                    # Create Discord embed
                    embed = discord.Embed(
                        title=embed_data.get("title"),
                        description=embed_data.get("description"),
                        color=_parse_color(embed_data.get("color")),
                        url=embed_data.get("url")
                    )
                    
                    # Quick content check
                    has_content = any([
                        embed.title,
                        embed.description,
                        embed_data.get("fields"),
                        (embed_data.get("author") or {}).get("name"),
                        (embed_data.get("footer") or {}).get("text"),
                        _get_url(embed_data, "thumbnail", "thumbnail_url"),
                        _get_url(embed_data, "image", "image_url")
                    ])
                    
                    if not has_content:
                        log(f"Skipping empty embed {i}")
                        continue

                    # Add author if present
                    if (embed_data.get("author") or {}).get("name"):
                        author = embed_data.get("author", {})
                        embed.set_author(
                            name=author.get("name"),
                            url=author.get("url"),
                            icon_url=author.get("icon_url")
                        )

                    # Add thumbnail if present
                    thumb_url = _get_url(embed_data, "thumbnail", "thumbnail_url")
                    if thumb_url:
                        embed.set_thumbnail(url=thumb_url)

                    # Add image if present
                    image_url = _get_url(embed_data, "image", "image_url")
                    if image_url:
                        embed.set_image(url=image_url)

                    # Add fields if present
                    for field in embed_data.get("fields", []):
                        try:
                            embed.add_field(
                                name=field.get("name", "\u200b"),
                                value=field.get("value", "\u200b"),
                                inline=field.get("inline", False)
                            )
                        except Exception:
                            continue

                    # Add footer if present
                    footer = embed_data.get("footer", {}) or {}
                    if footer.get("text"):
                        embed.set_footer(
                            text=footer.get("text"),
                            icon_url=footer.get("icon_url")
                        )

                    # Create view with buttons and select menus
                    view = discord.ui.View()
                    
                    # Add buttons
                    for button_data in embed_data.get("buttons", []) or []:
                        if button_data.get("type") == "link" and button_data.get("url"):
                            view.add_item(discord.ui.Button(
                                label=button_data.get("label", "Button"),
                                style=discord.ButtonStyle.link,
                                url=button_data["url"]
                            ))

                    # Add select menus
                    for select_data in embed_data.get("selects", []) or []:
                        options = []
                        for option_data in select_data.get("options", []) or []:
                            options.append(discord.SelectOption(
                                label=option_data.get("label", "Option"),
                                value=option_data.get("value", ""),
                                description=option_data.get("description", "")
                            ))
                        
                        if options:
                            select = discord.ui.Select(
                                placeholder=select_data.get("placeholder", "Choose an option..."),
                                min_values=1,
                                max_values=1,
                                options=options
                            )
                            
                            async def select_callback(interaction: discord.Interaction, select_obj=select, select_data=select_data):
                                await interaction.response.defer(ephemeral=True)
                                try:
                                    selected_value = interaction.data.get("values", [None])[0]
                                    if not selected_value:
                                        await interaction.followup.send("No value selected.", ephemeral=True)
                                        return

                                    if selected_value.startswith("send:"):
                                        key = selected_value.split(":", 1)[1]
                                        path = os.path.join(EMBED_DIR, f"{key}.json")
                                        if os.path.exists(path):
                                            try:
                                                with open(path, "r", encoding="utf-8") as f:
                                                    saved_data = json.load(f)
                                                saved_payload = saved_data.get("payload") or saved_data
                                                for saved_embed_data in saved_payload.get("embeds", []):
                                                    se = discord.Embed(
                                                        title=saved_embed_data.get("title"),
                                                        description=saved_embed_data.get("description"),
                                                        color=_parse_color(saved_embed_data.get("color"))
                                                    )
                                                    thumb = _get_url(saved_embed_data, "thumbnail", "thumbnail_url")
                                                    img = _get_url(saved_embed_data, "image", "image_url")
                                                    if thumb: se.set_thumbnail(url=thumb)
                                                    if img: se.set_image(url=img)
                                                    for name, value, inline in _iter_fields(saved_embed_data.get("fields")):
                                                        try:
                                                            se.add_field(name=name, value=value, inline=inline)
                                                        except Exception:
                                                            pass
                                                    await interaction.followup.send(embed=se, ephemeral=True)
                                            except Exception as e:
                                                await interaction.followup.send(f"Error loading saved embed: {e}", ephemeral=True)
                                        else:
                                            await interaction.followup.send(f"Saved embed '{key}' not found.", ephemeral=True)
                                    
                                    elif selected_value.startswith("link:"):
                                        url = selected_value.split(":", 1)[1]
                                        await interaction.followup.send(f"<{url}>", ephemeral=True)
                                    
                                    elif selected_value.startswith("send_json:"):
                                        b64 = selected_value.split(":",1)[1]
                                        try:
                                            obj = _decode_base64_json_token(b64)
                                        except ValueError as ex:
                                            await interaction.followup.send(f"Failed to decode JSON option: {ex}", ephemeral=True)
                                            return
                                        if isinstance(obj, list):
                                            payload_embeds = obj
                                        elif isinstance(obj, dict) and obj.get("embeds"):
                                            payload_embeds = obj.get("embeds", [])
                                        else:
                                            payload_embeds = [obj]
                                        for eemb in payload_embeds:
                                            se = discord.Embed(
                                                title=eemb.get("title"),
                                                description=eemb.get("description"),
                                                color=_parse_color(eemb.get("color"))
                                            )
                                            thumb = _get_url(eemb, "thumbnail", "thumbnail_url")
                                            img = _get_url(eemb, "image", "image_url")
                                            if thumb: se.set_thumbnail(url=thumb)
                                            if img: se.set_image(url=img)
                                            for name, value, inline in _iter_fields(eemb.get("fields")):
                                                try:
                                                    se.add_field(name=name, value=value, inline=inline)
                                                except Exception:
                                                    pass
                                            await interaction.followup.send(embed=se, ephemeral=True)

                                    else:
                                        await interaction.followup.send(f"Selected: {selected_value}", ephemeral=True)
                                except Exception as ex:
                                    await interaction.followup.send(f"Select handling error: {ex}", ephemeral=True)

                            select.callback = select_callback
                            view.add_item(select)

                    # Send the embed
                    await target_channel.send(embed=embed, view=view if view.children else None)
                    sent_count += 1

                except Exception as e:
                    log(f"ERROR sending embed: {e}")
                    continue

            # Send confirmation
            if sent_count == 0:
                await interaction.followup.send(
                    f"No embeds were sent. This might be because all embeds were empty or invalid. Check the logs for details.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Successfully sent {sent_count} embed(s) to {target_channel.mention}!", 
                    ephemeral=True
                )
            
            # Log the action
            log(f"EMBED_SEND_JSON: {interaction.user} sent {sent_count} embeds to {target_channel.id}")
            
            # Send to log channel
            try:
                lc = self.bot.get_channel(LOG_CHANNEL_ID) or await self.bot.fetch_channel(LOG_CHANNEL_ID)
                await lc.send(f"`[{datetime.now(timezone.utc).isoformat()}]` {interaction.user} sent {sent_count} embeds to {target_channel.mention} via JSON")
            except Exception:
                pass

        except json.JSONDecodeError as e:
            await interaction.followup.send(f"Invalid JSON format: {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error processing JSON: {e}", ephemeral=True)
            log(f"ERROR embed_send_json: {e}")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions for embed sending."""
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    custom_id = interaction.data["custom_id"]

    # Handle sendembed buttons
    if custom_id.startswith("sendembed:"):
        try:
            # Robust parsing: target may contain ":" (e.g. send_json:BASE64)
            payload = custom_id[len("sendembed:"):]
            is_ephemeral = False
            target = payload

            # If there is a trailing ephemeral flag ':e' or ':p', split it
            if payload.endswith(":e") or payload.endswith(":p"):
                is_ephemeral = payload.endswith(":e")
                # drop trailing ":e" or ":p"
                target = payload[:-2]
                # trim any leading ':' left accidentally
                if target.startswith(":"):
                    target = target[1:]

            # Now 'target' contains the whole target string (may include colons)
            # 'is_ephemeral' contains the flag

            # Load the embed data
            embed_data = None

            # Check if target is a send_json:b64 format
            if target.startswith("send_json:"):
                import base64
                import json
                try:
                    b64_data = target.split(":", 1)[1]
                    raw = base64.b64decode(b64_data + "===")
                    embed_data = json.loads(raw.decode("utf-8"))
                except Exception as ex:
                    await interaction.response.send_message(f"Failed to decode embedded JSON: {ex}", ephemeral=True)
                    return

            # If target is 'send:KEY' we need to load saved file
            elif target.startswith("send:"):
                key = target.split(":", 1)[1]
                try:
                    path = os.path.join(os.path.dirname(__file__), "embed-builder-web", "data", "embeds", f"{key}.json")
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            saved = json.load(f)
                        embed_data = saved.get("payload") or saved
                    else:
                        await interaction.response.send_message(f"Saved key not found: {key}", ephemeral=True)
                        return
                except Exception as ex:
                    await interaction.response.send_message(f"Failed to load saved embed: {ex}", ephemeral=True)
                    return
            else:
                # Unknown target format
                await interaction.response.send_message("Unknown sendembed target.", ephemeral=True)
                return

            # At this point embed_data should be a dict or list of embeds
            if not embed_data:
                await interaction.response.send_message("No embeds were found in the payload.", ephemeral=True)
                return

            # Send either ephemeral or to the channel that triggered interaction
            await interaction.response.defer(ephemeral=is_ephemeral)
            # reuse existing code paths to send embed(s) — minimal demonstration:
            if isinstance(embed_data, dict) and embed_data.get("embeds"):
                payload_embeds = embed_data["embeds"]
            elif isinstance(embed_data, list):
                payload_embeds = embed_data
            else:
                payload_embeds = [embed_data]

            sent = 0
            for emb in payload_embeds:
                # construct discord.Embed safely
                try:
                    e = discord.Embed(
                        title=emb.get("title") or None,
                        description=emb.get("description") or None,
                        color=_parse_color(emb.get("color"))
                    )
                    # optional fields
                    if _get_url(emb, "thumbnail", "thumbnail_url"):
                        e.set_thumbnail(url=_get_url(emb, "thumbnail", "thumbnail_url"))
                    if _get_url(emb, "image", "image_url"):
                        e.set_image(url=_get_url(emb, "image", "image_url"))
                    for name, value, inline in _iter_fields(emb.get("fields")):
                        try:
                            e.add_field(name=name, value=value, inline=inline)
                        except Exception:
                            pass
                    if is_ephemeral:
                        await interaction.followup.send(embed=e, ephemeral=True)
                    else:
                        await interaction.channel.send(embed=e)
                    sent += 1
                except Exception as ex:
                    # skip invalid embed
                    continue

            if sent == 0:
                await interaction.followup.send("No embeds were sent. This might be because all embeds were empty or invalid. Check the logs for details.", ephemeral=True)
            else:
                await interaction.followup.send(f"Sent {sent} embed(s).", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error handling sendembed: {e}", ephemeral=True)
            return

async def setup(bot):
    await bot.add_cog(EmbedNewCog(bot))
# ...existing code...