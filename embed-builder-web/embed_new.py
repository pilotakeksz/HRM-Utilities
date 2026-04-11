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

try:
    from embed_storage import store_embed
    EMBED_STORAGE_AVAILABLE = True
except ImportError:
    EMBED_STORAGE_AVAILABLE = False
    def store_embed(*args, **kwargs):
        pass

EMBED_DIR = os.path.join(os.path.dirname(__file__), "data", "embeds")
os.makedirs(EMBED_DIR, exist_ok=True)
SEND_MAP_FILE = os.path.join(EMBED_DIR, "send_map.json")
# Persistent message registry: message_id -> {channel_id, payload, view_key}
MSG_REGISTRY_FILE = os.path.join(EMBED_DIR, "msg_registry.json")
_SEND_MAP_LOCK = threading.Lock()
_MSG_REGISTRY_LOCK = threading.Lock()

LOG_CHANNEL_ID = None


# ─── send_map helpers ────────────────────────────────────────────────────────

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


# ─── msg_registry helpers ─────────────────────────────────────────────────────

def _load_msg_registry() -> Dict[str, Any]:
    with _MSG_REGISTRY_LOCK:
        try:
            if os.path.exists(MSG_REGISTRY_FILE):
                with open(MSG_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}


def _save_msg_registry(m: Dict[str, Any]):
    with _MSG_REGISTRY_LOCK:
        tmp = MSG_REGISTRY_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(tmp, MSG_REGISTRY_FILE)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass


def _register_message(message_id: int, channel_id: int, payload: Dict[str, Any], view_key: str):
    m = _load_msg_registry()
    m[str(message_id)] = {
        "channel_id": channel_id,
        "view_key": view_key,
        "payload": payload,
    }
    _save_msg_registry(m)


def _get_registered_message(message_id: int) -> Optional[Dict[str, Any]]:
    m = _load_msg_registry()
    return m.get(str(message_id))


def _all_registered_messages() -> Dict[str, Any]:
    return _load_msg_registry()


# ─── misc helpers ─────────────────────────────────────────────────────────────

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


def _resolve_embeds_list(target: str, payload: Dict[str, Any]) -> Optional[List[Dict]]:
    """Resolve a target string to a list of embed dicts. Returns None on failure."""
    if target.startswith("send_json:"):
        b64 = target.split(":", 1)[1]
        obj = _decode_base64_json_token(b64)
        return _extract_embeds_from_obj(obj)

    if target.startswith("send_map:"):
        key = target.split(":", 1)[1]
        entry = _get_send_map_entry(key)
        if not entry:
            return None
        return _resolve_entry(entry, payload)

    if target.startswith("send:"):
        key = target.split(":", 1)[1]
        ref = (payload.get("referenced_messages") or {}).get(key)
        if ref:
            return _extract_embeds_from_obj(ref)
        path = os.path.join(EMBED_DIR, f"{key}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return _extract_embeds_from_obj(saved.get("payload") or saved)

    return None


def _resolve_entry(entry: Dict[str, Any], payload: Dict[str, Any]) -> Optional[List[Dict]]:
    t = entry.get("type")
    if t == "send_json":
        obj = _decode_base64_json_token(entry.get("b64", ""))
        return _extract_embeds_from_obj(obj)
    if t == "ref_message":
        return _extract_embeds_from_obj(entry.get("message") or {})
    if t == "ref_embed":
        e = entry.get("embed")
        return [e] if isinstance(e, dict) else (e or [])
    return None


def _extract_embeds_from_obj(obj) -> List[Dict]:
    if isinstance(obj, dict):
        if obj.get("messages"):
            out = []
            for msg in obj["messages"]:
                out.extend(msg.get("embeds", []))
            return out
        if obj.get("embeds"):
            return obj["embeds"]
        return [obj]
    if isinstance(obj, list):
        return obj
    return []


# ─── persistent custom_id scheme ──────────────────────────────────────────────
# Buttons: "pb:<view_key>:<target_b64>:<ephemeral>"
# Selects: "ps:<view_key>"   (options carry value as before)

def _encode_custom_id_target(target: str) -> str:
    return base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")


def _decode_custom_id_target(s: str) -> str:
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s).decode()


# ─── PayloadView ──────────────────────────────────────────────────────────────

class PayloadView(ui.View):
    """Persistent view. All components survive bot restarts via view_key + msg_registry."""

    def __init__(self, payload: Dict[str, Any], bot: commands.Bot, *,
                 timeout: Optional[float] = None, view_key: Optional[str] = None):
        super().__init__(timeout=None)  # always persistent
        self.payload = payload
        self.bot = bot
        self._local_keys: List[str] = []
        self.view_key = view_key or uuid.uuid4().hex

        first = self._first_embed(payload)
        if not first:
            return

        # ── buttons ──
        for b in first.get("buttons", []) or []:
            if b.get("type") == "link" and b.get("url"):
                btn = ui.Button(
                    label=b.get("label") or "Link",
                    style=discord.ButtonStyle.link,
                    url=b.get("url"),
                )
                self.add_item(btn)
            elif b.get("type") == "send_embed":
                label = b.get("label") or "Send"
                target = self._persist_target(b.get("target") or "")
                ephemeral = bool(b.get("ephemeral"))
                eph_str = "1" if ephemeral else "0"
                target_b64 = _encode_custom_id_target(target)
                custom_id = f"pb:{self.view_key}:{target_b64}:{eph_str}"[:100]

                btn = ui.Button(
                    label=label,
                    style=discord.ButtonStyle.secondary,
                    custom_id=custom_id,
                )

                async def _btn_cb(interaction: discord.Interaction, _target=target, _eph=ephemeral):
                    await interaction.response.defer(ephemeral=_eph)
                    await self._handle_target_send(interaction, _target, _eph)

                btn.callback = _btn_cb
                self.add_item(btn)

        # ── selects ──
        for s in first.get("selects", []) or []:
            options = []
            for o in s.get("options", []) or []:
                orig_val = o.get("value") or ""
                use_val = self._persist_target(orig_val)

                option_kwargs = {
                    "label": o.get("label") or o.get("value") or "Option",
                    "value": use_val[:100],
                    "description": o.get("description"),
                }
                if o.get("emoji"):
                    option_kwargs["emoji"] = o.get("emoji")
                options.append(discord.SelectOption(**option_kwargs))

            if not options:
                continue

            custom_id = f"ps:{self.view_key}"[:100]
            sel = ui.Select(
                placeholder=s.get("placeholder") or "Choose…",
                min_values=1,
                max_values=1,
                options=options,
                custom_id=custom_id,
            )

            async def _sel_cb(interaction: discord.Interaction, select: ui.Select = sel):
                await interaction.response.defer(ephemeral=True)
                val = (select.values or [None])[0]
                if not val:
                    await interaction.followup.send("No value selected.", ephemeral=True)
                    return
                await self._handle_target_send(interaction, val, True)

            sel.callback = _sel_cb
            self.add_item(sel)

    # ── helpers ──

    @staticmethod
    def _first_embed(payload: Dict[str, Any]) -> Optional[Dict]:
        if payload.get("messages"):
            first_msg = payload["messages"][0]
            embeds = first_msg.get("embeds") if isinstance(first_msg, dict) else None
            return embeds[0] if embeds else None
        if payload.get("embeds"):
            return payload["embeds"][0]
        return None

    def _persist_target(self, orig_val: str) -> str:
        """Convert large inline targets to send_map: references."""
        if orig_val.startswith("send_json:"):
            b64 = orig_val.split(":", 1)[1]
            entry = {"type": "send_json", "b64": b64}
            key = _put_send_map_entry(entry)
            self._local_keys.append(key)
            return f"send_map:{key}"
        if orig_val.startswith("send:"):
            keyname = orig_val.split(":", 1)[1]
            ref = (self.payload.get("referenced_messages") or {}).get(keyname)
            if ref:
                entry = {"type": "ref_message", "message": ref}
                key = _put_send_map_entry(entry)
                self._local_keys.append(key)
                return f"send_map:{key}"
        return orig_val

    async def _handle_target_send(self, interaction: discord.Interaction, target: str, ephemeral: bool):
        try:
            if not target:
                await interaction.followup.send("No target specified.", ephemeral=True)
                return

            if target.startswith("link:"):
                url = target.split(":", 1)[1]
                await interaction.followup.send(f"<{url}>", ephemeral=ephemeral)
                return

            try:
                embeds_list = _resolve_embeds_list(target, self.payload)
            except Exception as ex:
                await interaction.followup.send(f"Error resolving target: {ex}", ephemeral=True)
                return

            if not embeds_list:
                await interaction.followup.send("Referenced embed not found.", ephemeral=True)
                return

            discord_embeds = []
            for eobj in embeds_list:
                try:
                    discord_embeds.append(_build_discord_embed(eobj))
                except Exception:
                    continue

            if not discord_embeds:
                await interaction.followup.send("No valid embeds found.", ephemeral=True)
                return

            if ephemeral:
                await interaction.followup.send(embeds=discord_embeds, ephemeral=True)
            else:
                if interaction.channel:
                    msg = await interaction.channel.send(embeds=discord_embeds)
                    if EMBED_STORAGE_AVAILABLE and msg:
                        try:
                            for em in discord_embeds:
                                embed_json = em.to_dict()
                                store_embed(
                                    message_id=msg.id,
                                    channel_id=interaction.channel.id,
                                    embed_data=embed_json,
                                    embed_json=json.dumps(embed_json, indent=2),
                                    description=f"Embed from {interaction.user} via embed-builder",
                                )
                        except Exception as e:
                            print(f"Failed to store embed: {e}")
                else:
                    await interaction.followup.send(embeds=discord_embeds, ephemeral=True)

        except Exception as ex:
            try:
                await interaction.followup.send(f"Error: {ex}", ephemeral=True)
            except Exception:
                pass


# ─── JSONCollectorView ────────────────────────────────────────────────────────

class JSONCollectorView(ui.View):
    def __init__(self, cog, channel=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.channel = channel
        self.waiting_for_json = True

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.waiting_for_json = False
        await interaction.response.edit_message(content="JSON collection cancelled.", view=None)

    async def on_timeout(self):
        self.waiting_for_json = False


# ─── Cog ─────────────────────────────────────────────────────────────────────

class EmbedNewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Re-register all persistent views from the message registry on startup."""
        registry = _all_registered_messages()
        restored = 0
        for msg_id_str, entry in registry.items():
            payload = entry.get("payload") or {}
            view_key = entry.get("view_key") or msg_id_str
            try:
                view = PayloadView(payload, self.bot, view_key=view_key)
                if view.children:
                    self.bot.add_view(view)
                    restored += 1
            except Exception as e:
                print(f"[embed_new] Failed to restore view for msg {msg_id_str}: {e}")
        if restored:
            print(f"[embed_new] Restored {restored} persistent view(s) from registry.")

    # ── /send_json ──

    @app_commands.command(name="send_json", description="Send a complete message JSON (messages with embeds + referenced_messages + actions)")
    @app_commands.describe(channel="Optional target channel")
    async def send_json(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        view = JSONCollectorView(self, channel)

        embed = discord.Embed(
            title="JSON Collection",
            description=(
                "Please send your JSON data in this chat. You can either:\n"
                "• Send the JSON as a message (if short enough)\n"
                "• Upload a `.txt` file with the JSON content (for large data)\n\n"
                "I'll wait for 5 minutes for your response."
            ),
            color=0x7289da,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await self._wait_for_json(interaction, view, channel)

    async def _wait_for_json(self, interaction: discord.Interaction, view: JSONCollectorView, channel: Optional[discord.TextChannel] = None):
        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
                and view.waiting_for_json
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=300)

            if message.attachments:
                attachment = message.attachments[0]
                if not attachment.filename.endswith(".txt"):
                    await interaction.followup.send("Please upload a `.txt` file.", ephemeral=True)
                    return
                try:
                    json_text = (await attachment.read()).decode("utf-8")
                except Exception as e:
                    await interaction.followup.send(f"Error reading file: {e}", ephemeral=True)
                    return
            else:
                json_text = message.content

            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as e:
                await interaction.followup.send(f"Invalid JSON: {e}", ephemeral=True)
                return

            await self._process_and_send_messages(interaction, data, channel)

            embed = discord.Embed(
                title="JSON Processed Successfully",
                description="Your JSON data has been processed and sent!",
                color=0x00FF00,
            )
            await interaction.edit_original_response(embed=embed, view=None)

        except asyncio.TimeoutError:
            await interaction.followup.send("Timeout: No JSON data received within 5 minutes.", ephemeral=True)
            view.waiting_for_json = False
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            view.waiting_for_json = False

    async def _process_and_send_messages(self, interaction: discord.Interaction, data: dict, channel: Optional[discord.TextChannel] = None):
        if not isinstance(data, dict):
            await interaction.followup.send("JSON must be an object with 'messages' or 'embeds' array.", ephemeral=True)
            return

        messages_data = data.get("messages", [])
        embeds_raw = data.get("embeds", [])

        if messages_data:
            if not isinstance(messages_data, list) or not messages_data:
                await interaction.followup.send("No messages found in payload.", ephemeral=True)
                return
        elif embeds_raw:
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

        total_embeds_sent = 0
        first_message_sent = False

        for message_data in messages_data:
            embeds_raw_msg = message_data.get("embeds", [])
            if not embeds_raw_msg:
                continue

            primary_embeds = []
            for e in embeds_raw_msg:
                try:
                    primary_embeds.append(_build_discord_embed(e))
                except Exception:
                    continue

            if not primary_embeds:
                continue

            # Only the first message carries the interactive view
            if not first_message_sent:
                view_key = uuid.uuid4().hex
                view = PayloadView(data, self.bot, view_key=view_key)
                view_to_send = view if view.children else None
            else:
                view_to_send = None
                view_key = None

            try:
                msg = await target.send(embeds=primary_embeds, view=view_to_send)
                total_embeds_sent += len(primary_embeds)

                # Register for persistence
                if not first_message_sent and view_key:
                    _register_message(msg.id, target.id, data, view_key)
                    # Re-add view with message binding so discord.py tracks it
                    if view_to_send:
                        self.bot.add_view(view_to_send, message_id=msg.id)

                first_message_sent = True

            except Exception as ex:
                await interaction.followup.send(f"Failed to send message: {ex}", ephemeral=True)
                return

        if total_embeds_sent > 0:
            await interaction.followup.send(
                f"Posted {total_embeds_sent} embed(s) across {len(messages_data)} message(s) to {target.mention}. "
                "Buttons and selects are persistent across restarts.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send("No valid embeds found to send.", ephemeral=True)

    # ── /restore_json ──

    @app_commands.command(name="restore_json", description="Retrieve the original JSON payload for a sent embed message")
    @app_commands.describe(message_id="The Discord message ID of the sent embed")
    async def restore_json(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)

        try:
            mid = int(message_id.strip())
        except ValueError:
            await interaction.followup.send("Invalid message ID.", ephemeral=True)
            return

        entry = _get_registered_message(mid)
        if not entry:
            await interaction.followup.send(
                "No payload found for that message ID. Only messages sent via `/send_json` after this update are tracked.",
                ephemeral=True,
            )
            return

        payload = entry.get("payload") or {}
        try:
            json_str = json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception as e:
            await interaction.followup.send(f"Failed to serialize payload: {e}", ephemeral=True)
            return

        if len(json_str) <= 1900:
            await interaction.followup.send(f"```json\n{json_str}\n```", ephemeral=True)
        else:
            # Send as file
            import io
            file = discord.File(fp=io.BytesIO(json_str.encode("utf-8")), filename=f"payload_{mid}.json")
            await interaction.followup.send(
                content=f"Payload for message `{mid}` (too large for inline display):",
                file=file,
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedNewCog(bot))