import os
import json
import base64
import uuid
import threading
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
    def __init__(self, payload: Dict[str, Any], bot: commands.Bot, *, timeout: Optional[float] = 300.0):
        super().__init__(timeout=timeout)
        self.payload = payload
        self.bot = bot
        # local map of keys created for this view (not required but useful)
        self._local_keys: List[str] = []

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

                # handle send:KEY where KEY is present in payload.referenced_embeds -> persist the referenced embed dict
                elif orig_val.startswith("send:"):
                    keyname = orig_val.split(":", 1)[1]
                    ref = (payload.get("referenced_embeds") or {}).get(keyname)
                    if ref:
                        entry = {"type": "ref_embed", "embed": ref}
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
                options.append(discord.SelectOption(
                    label=o.get("label") or o.get("value") or "Option",
                    value=use_val,
                    description=o.get("description")
                ))

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
                        elif isinstance(obj, list):
                            embeds_list = obj
                        else:
                            embeds_list = [obj]
                    elif entry.get("type") == "ref_embed":
                        embed_obj = entry.get("embed")
                        embeds_list = [embed_obj] if isinstance(embed_obj, dict) else (embed_obj or [])
                    else:
                        await interaction.followup.send("Unknown mapped entry type.", ephemeral=True)
                        return

                    # send only these embeds ephemerally
                    sent = 0
                    for eobj in embeds_list:
                        try:
                            em = _build_discord_embed(eobj)
                            await interaction.followup.send(embed=em, ephemeral=True)
                            sent += 1
                        except Exception:
                            continue
                    if sent == 0:
                        await interaction.followup.send("No embeds were sent (empty or invalid).", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Sent {sent} embed(s) ephemerally.", ephemeral=True)
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
                    elif isinstance(obj, list):
                        embeds_list = obj
                    else:
                        embeds_list = [obj]
                elif entry.get("type") == "ref_embed":
                    embed_obj = entry.get("embed")
                    embeds_list = [embed_obj] if isinstance(embed_obj, dict) else (embed_obj or [])
                else:
                    await interaction.followup.send("Unknown mapped entry type.", ephemeral=True)
                    return

            elif target.startswith("send:"):
                key = target.split(":", 1)[1]
                # prefer referenced_embeds inside original payload if provided (not persisted)
                ref = (self.payload.get("referenced_embeds") or {}).get(key)
                if ref:
                    embeds_list = [ref]
                else:
                    path = os.path.join(EMBED_DIR, f"{key}.json")
                    if not os.path.exists(path):
                        await interaction.followup.send(f"Referenced embed '{key}' not found.", ephemeral=True)
                        return
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            saved = json.load(f)
                        payload = saved.get("payload") or saved
                        embeds_list = payload.get("embeds", [])
                    except Exception as ex:
                        await interaction.followup.send(f"Failed to load saved embed: {ex}", ephemeral=True)
                        return

            elif target.startswith("link:"):
                url = target.split(":", 1)[1]
                await interaction.followup.send(f"<{url}>", ephemeral=ephemeral)
                return

            else:
                await interaction.followup.send(f"Unknown target: {target}", ephemeral=True)
                return

            # send only the resolved embeds ephemerally or to channel depending on ephemeral flag
            sent = 0
            for eobj in embeds_list:
                try:
                    em = _build_discord_embed(eobj)
                    if ephemeral:
                        await interaction.followup.send(embed=em, ephemeral=True)
                    else:
                        if interaction.channel:
                            await interaction.channel.send(embed=em)
                        else:
                            await interaction.followup.send(embed=em, ephemeral=True)
                    sent += 1
                except Exception:
                    continue

            if sent == 0:
                await interaction.followup.send("No embeds were sent (empty or invalid).", ephemeral=True)
            else:
                await interaction.followup.send(f"Sent {sent} embed(s).", ephemeral=True)

        except Exception as ex:
            try:
                await interaction.followup.send(f"Error sending embeds: {ex}", ephemeral=True)
            except Exception:
                pass


class EmbedNewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="send_json", description="Send a complete embed JSON (embeds + referenced_embeds + actions)")
    @app_commands.describe(json_payload="The full JSON payload (as string)", channel="Optional target channel")
    async def send_json(self, interaction: discord.Interaction, json_payload: str, channel: Optional[discord.TextChannel] = None):
        await interaction.response.defer(ephemeral=True)
        try:
            data = json.loads(json_payload) if isinstance(json_payload, str) else json_payload
        except Exception as ex:
            await interaction.followup.send(f"Invalid JSON: {ex}", ephemeral=True)
            return

        if not isinstance(data, dict):
            await interaction.followup.send("JSON must be an object with an 'embeds' array.", ephemeral=True)
            return

        embeds_raw = data.get("embeds", [])
        if not isinstance(embeds_raw, list) or not embeds_raw:
            await interaction.followup.send("No embeds found in payload.", ephemeral=True)
            return

        # build primary embeds only (do not send referenced_embeds by default)
        primary_embeds = []
        for e in embeds_raw:
            try:
                primary_embeds.append(_build_discord_embed(e))
            except Exception:
                continue

        target = channel or (interaction.channel if interaction.channel else None)
        if not target:
            await interaction.followup.send("No valid target channel found.", ephemeral=True)
            return

        view = PayloadView(data, self.bot)
        try:
            await target.send(embeds=primary_embeds, view=view if len(view.children) > 0 else None)
            await interaction.followup.send(f"Posted {len(primary_embeds)} embed(s) to {target.mention}. Select options send linked embed(s) ephemerally to you.", ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(f"Failed to send embeds: {ex}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedNewCog(bot))