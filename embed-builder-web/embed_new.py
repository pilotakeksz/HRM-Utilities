import os
import json
import base64
from typing import Optional, List, Dict, Any

import discord
from discord import app_commands, ui
from discord.ext import commands

EMBED_DIR = os.path.join(os.path.dirname(__file__), "../embed-builder-web/data/embeds")
LOG_CHANNEL_ID = None  # set if you want
os.makedirs(EMBED_DIR, exist_ok=True)


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
    if (thumb := _get_url(eobj, "thumbnail", "thumbnail_url", "thumbnail.url")):
        try: emb.set_thumbnail(url=thumb)
        except Exception: pass
    if (img := _get_url(eobj, "image", "image_url", "image.url")):
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
    def __init__(self, payload: Dict[str, Any], bot: commands.Bot, *, timeout: Optional[float] = 300.0):
        super().__init__(timeout=timeout)
        self.payload = payload
        self.bot = bot
        self.referenced = payload.get("referenced_embeds") or {}
        # Build buttons/selects from first embed's actions
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
                    if interaction.user is None:
                        return
                    await interaction.response.defer(ephemeral=ephemeral)
                    await self._handle_target_send(interaction, target, ephemeral)

                btn.callback = make_btn_cb
                self.add_item(btn)

        # Selects
        for s in first.get("selects", []) or []:
            options = []
            for o in s.get("options", []) or []:
                options.append(discord.SelectOption(
                    label=o.get("label") or o.get("value") or "Option",
                    value=o.get("value") or "",
                    description=o.get("description")
                ))
            if not options:
                continue
            sel = ui.Select(placeholder=s.get("placeholder") or "Choose…", min_values=1, max_values=1, options=options)

            async def make_sel_cb(interaction: discord.Interaction, select: ui.Select = sel):
                if interaction.user is None:
                    return
                await interaction.response.defer(ephemeral=True)
                val = (select.values or [None])[0]
                if not val:
                    await interaction.followup.send("No value selected.", ephemeral=True)
                    return
                await self._handle_target_send(interaction, val, False)

            sel.callback = make_sel_cb
            self.add_item(sel)

    async def _handle_target_send(self, interaction: discord.Interaction, target: str, ephemeral: bool):
        try:
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

            elif target.startswith("send:"):
                key = target.split(":", 1)[1]
                # try referenced_embeds first
                ref = self.referenced.get(key)
                if ref:
                    embeds_list = ref if isinstance(ref, list) else [ref]
                else:
                    # fallback to EMBED_DIR
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
                await interaction.followup.send(f"<{url}>", ephemeral=True)
                return
            else:
                await interaction.followup.send(f"Unknown target: {target}", ephemeral=True)
                return

            sent = 0
            target_channel = interaction.channel
            for eobj in embeds_list:
                try:
                    em = _build_discord_embed(eobj)
                    if ephemeral:
                        await interaction.followup.send(embed=em, ephemeral=True)
                    else:
                        if target_channel:
                            await target_channel.send(embed=em)
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

        # build primary embeds
        primary_embeds = []
        for e in embeds_raw:
            try:
                primary_embeds.append(_build_discord_embed(e))
            except Exception:
                continue

        # include referenced_embeds appended so all referenced content is present in the single message
        referenced = data.get("referenced_embeds") or {}
        referenced_embeds_objs = []
        if isinstance(referenced, dict):
            for key, rval in referenced.items():
                if isinstance(rval, dict):
                    referenced_embeds_objs.append(rval)

        # combine
        all_embed_objs = primary_embeds[:]
        for r in referenced_embeds_objs:
            try:
                all_embed_objs.append(_build_discord_embed(r))
            except Exception:
                continue

        target = channel or (interaction.channel if interaction.channel else None)
        if not target:
            await interaction.followup.send("No valid target channel found.", ephemeral=True)
            return

        # attach view built from payload (callbacks inside)
        view = PayloadView(data, self.bot)

        # send single message with all embeds + view
        try:
            await target.send(embeds=all_embed_objs, view=view if len(view.children) > 0 else None)
            await interaction.followup.send(f"Posted {len(all_embed_objs)} embed(s) to {target.mention}.", ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(f"Failed to send embeds: {ex}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedNewCog(bot))