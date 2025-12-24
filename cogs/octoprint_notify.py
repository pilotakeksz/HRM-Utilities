import os
import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime, timedelta, timezone
import random
import asyncio
from io import BytesIO

# ---------------------------
# Logging setup
# ---------------------------
LOGS_DIR = os.path.join(os.path.dirname(__file__), "../logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "octoprint_buttons.log")

def log_button_click(user: discord.User, button_name: str, action: str, result: str = "", details: str = ""):
    """Log button click events to local file."""
    try:
        ts = datetime.now(timezone.utc).isoformat()
        user_info = f"{user} ({user.id})"
        log_line = f"[{ts}] {user_info} | Button: {button_name} | Action: {action}"
        if result:
            log_line += f" | Result: {result}"
        if details:
            log_line += f" | Details: {details}"
        log_line += "\n"
        
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Failed to log button click: {e}")

# ---------------------------
# Authorized E-STOP users
# ---------------------------
ESTOP_ALLOWED = {840949634071658507, 735167992966676530}

# ---------------------------
# LCD Message Modal
# ---------------------------
class LCDMessageModal(discord.ui.Modal, title="Send Message to Printer LCD"):
    message = discord.ui.TextInput(
        label="Message",
        placeholder="Enter message to display on printer LCD (max 20 chars recommended)",
        required=True,
        max_length=50
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        message_text = self.message.value.strip()
        
        # Double-check cooldown (in case of race condition)
        if user_id in self.cog.lcd_cooldowns:
            last_used = self.cog.lcd_cooldowns[user_id]
            time_since = datetime.utcnow() - last_used
            cooldown_delta = timedelta(minutes=self.cog.lcd_cooldown_minutes)
            if time_since < cooldown_delta:
                remaining = cooldown_delta - time_since
                total_seconds = int(remaining.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                if minutes > 0:
                    time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
                else:
                    time_str = f"{seconds}s"
                log_button_click(interaction.user, "Send LCD Message", "Cooldown active (modal)", "Denied", f"Message: {message_text}, {time_str} remaining")
                await interaction.response.send_message(
                    f"⏰ You can send another message in {time_str}. ({self.cog.lcd_cooldown_minutes}min cooldown per person)",
                    ephemeral=True
                )
                return
        
        # Check if printer is still connected
        data = self.cog._get_status()
        connected = data.get("connected", False)
        
        if not connected:
            log_button_click(interaction.user, "Send LCD Message", "Printer offline (modal)", "Failed", f"Message: {message_text}")
            await interaction.response.send_message("Printer went offline. Cannot send message.", ephemeral=True)
            return
        
        # Send M117 G-code command to display message on LCD
        gcode_command = f"M117 {message_text}"
        result = self.cog._send_gcode(gcode_command)
        
        # Update cooldown
        self.cog.lcd_cooldowns[user_id] = datetime.utcnow()
        
        if result == "OK":
            # Update current LCD message tracking
            self.cog.current_lcd_message = {
                "message": message_text,
                "sender_id": user_id,
                "sender_name": str(interaction.user),
                "timestamp": datetime.utcnow()
            }
            
            # Update the status embed to show the new LCD message
            try:
                channel_id = os.getenv("OCTO_NOTIFY_CHANNEL_ID")
                if channel_id:
                    channel = self.cog.bot.get_channel(int(channel_id))
                    if channel:
                        data = self.cog._get_status()
                        await self.cog._send_update(channel, data, update_existing=True)
            except Exception as e:
                print(f"Failed to update status embed after LCD message: {e}")
            
            log_button_click(interaction.user, "Send LCD Message", "Message sent", "Success", f"Message: {message_text}")
            await interaction.response.send_message(
                f"✅ Message sent to printer LCD: `{message_text}`\n⏰ Next use available in {self.cog.lcd_cooldown_minutes} minutes.",
                ephemeral=True
            )
        else:
            log_button_click(interaction.user, "Send LCD Message", "Send failed", "Error", f"Message: {message_text}, Error: {result}")
            await interaction.response.send_message(
                f"❌ Failed to send message: {result}",
                ephemeral=True
            )

# ---------------------------
# E-STOP view (button on every embed)
# ---------------------------
class EStopView(discord.ui.View):
    def __init__(self, bot, cog=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog

        # Replace the previous per-button UI with a single select (dropdown) containing all actions
        # This keeps the UI compact and avoids accidental clicks.
        options = [
            discord.SelectOption(label="EMERGENCY STOP", value="estop", description="Request E-STOP (authorized users only)", emoji="⛔"),
            discord.SelectOption(label="Update Image", value="update_image", description="Fetch latest camera snapshot and update the embed", emoji="🖼️"),
            discord.SelectOption(label="Send LCD Message", value="lcd_message", description="Send a message to the printer LCD", emoji="💬"),
            discord.SelectOption(label="Enable Per-Print Camera", value="enable_per_print", description="Enable per-print camera switching for next print (admin)", emoji="✅"),
            discord.SelectOption(label="Disable Per-Print Camera", value="disable_per_print", description="Disable per-print camera switching (admin)", emoji="⛔"),
            discord.SelectOption(label="Switch Camera Now", value="switch_camera", description="Toggle primary/secondary camera immediately (admin)", emoji="🔀"),
        ]

        select = discord.ui.Select(placeholder="Choose action...", min_values=1, max_values=1, options=options)

        async def select_callback(interaction: discord.Interaction):
            # Single entry selected
            action = select.values[0]

            # EMERGENCY STOP flow
            if action == "estop":
                user_id = interaction.user.id
                if user_id not in ESTOP_ALLOWED:
                    log_button_click(interaction.user, "EMERGENCY STOP", "Unauthorized attempt", "Denied")
                    await interaction.response.send_message("You are not authorized to request an E-STOP.", ephemeral=True)
                    return
                token = str(random.randint(100000, 999999))
                self.bot.active_tokens[user_id] = token
                log_button_click(interaction.user, "EMERGENCY STOP", "Token generated", "Pending confirmation", f"Token: {token}")
                await interaction.response.send_message(
                    f"⚠️ Confirmation required: Send the token `{token}` in chat within 60s to execute E-STOP.",
                    ephemeral=True
                )

                async def expire_token():
                    await asyncio.sleep(60)
                    self.bot.active_tokens.pop(user_id, None)
                asyncio.create_task(expire_token())
                return

            # UPDATE IMAGE
            if action == "update_image":
                log_button_click(interaction.user, "Update Image", "Select used")
                await interaction.response.defer()
                if not self.cog:
                    log_button_click(interaction.user, "Update Image", "Error", "Cog reference not available")
                    await interaction.followup.send("Error: Cog reference not available.", ephemeral=True)
                    return
                data = self.cog._get_status()
                connected = data.get("connected", False)
                if not connected:
                    log_button_click(interaction.user, "Update Image", "Printer offline", "Failed")
                    await interaction.followup.send("Printer is offline. Cannot update image.", ephemeral=True)
                    return
                snapshot_file = None
                if self.cog.active_snapshot_url:
                    try:
                        headers = {"X-Api-Key": self.cog.api_key} if self.cog.api_key else {}
                        r = requests.get(self.cog.active_snapshot_url, headers=headers, timeout=3)
                        if r.status_code == 200:
                            fp = BytesIO(r.content)
                            fp.seek(0)
                            snapshot_file = discord.File(fp, filename="snapshot.jpg")
                    except Exception as e:
                        log_button_click(interaction.user, "Update Image", "Snapshot fetch failed", "Error", str(e))
                        await interaction.followup.send(f"Failed to fetch snapshot: {e}", ephemeral=True)
                        return
                try:
                    message = interaction.message
                    embed = message.embeds[0] if message.embeds else None
                    if embed and snapshot_file:
                        embed.set_image(url="attachment://snapshot.jpg")
                        await message.edit(embed=embed, attachments=[snapshot_file], view=self)
                        log_button_click(interaction.user, "Update Image", "Image updated", "Success")
                        await interaction.followup.send("Image updated!", ephemeral=True)
                    elif embed:
                        embed.set_image(url=None)
                        await message.edit(embed=embed, attachments=[], view=self)
                        log_button_click(interaction.user, "Update Image", "Image removed", "Snapshot unavailable")
                        await interaction.followup.send("Image removed (snapshot unavailable).", ephemeral=True)
                    else:
                        log_button_click(interaction.user, "Update Image", "No embed found", "Failed")
                        await interaction.followup.send("No embed found to update.", ephemeral=True)
                except Exception as e:
                    log_button_click(interaction.user, "Update Image", "Update failed", "Error", str(e))
                    await interaction.followup.send(f"Failed to update message: {e}", ephemeral=True)
                return

            # SEND LCD MESSAGE
            if action == "lcd_message":
                log_button_click(interaction.user, "Send LCD Message", "Select used")
                if not self.cog:
                    log_button_click(interaction.user, "Send LCD Message", "Error", "Cog reference not available")
                    await interaction.response.send_message("Error: Cog reference not available.", ephemeral=True)
                    return
                # Check cooldown
                user_id = interaction.user.id
                if user_id in self.cog.lcd_cooldowns:
                    last_used = self.cog.lcd_cooldowns[user_id]
                    time_since = datetime.utcnow() - last_used
                    cooldown_delta = timedelta(minutes=self.cog.lcd_cooldown_minutes)
                    if time_since < cooldown_delta:
                        remaining = cooldown_delta - time_since
                        total_seconds = int(remaining.total_seconds())
                        minutes = total_seconds // 60
                        seconds = total_seconds % 60
                        if minutes > 0:
                            time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
                        else:
                            time_str = f"{seconds}s"
                        log_button_click(interaction.user, "Send LCD Message", "Cooldown active", "Denied", f"{time_str} remaining")
                        await interaction.response.send_message(
                            f"⏰ You can send another message in {time_str}. ({self.cog.lcd_cooldown_minutes}min cooldown per person)",
                            ephemeral=True
                        )
                        return
                # Check if printer is connected
                data = self.cog._get_status()
                connected = data.get("connected", False)
                if not connected:
                    log_button_click(interaction.user, "Send LCD Message", "Printer offline", "Failed")
                    await interaction.response.send_message("Printer is offline. Cannot send message.", ephemeral=True)
                    return
                # Show modal
                modal = LCDMessageModal(self.cog)
                await interaction.response.send_modal(modal)
                return

            # ENABLE / DISABLE PER-PRINT CAMERA
            if action == "enable_per_print":
                user_id = interaction.user.id
                if not (getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator and str(user_id).startswith("840949634071658507")):
                    log_button_click(interaction.user, "Enable Per-Print Camera", "Unauthorized", "Denied")
                    await interaction.response.send_message("Only server administrators with a user ID starting with '840949634071658507' can enable per-print camera switching.", ephemeral=True)
                    return
                self.cog.camera_allowed_once = True
                self.cog.camera_mode = "one_print"
                log_button_click(interaction.user, "Enable Per-Print Camera", "Enabled for next print")
                await interaction.response.send_message("Per-print camera switching has been enabled for the next print.", ephemeral=True)
                return

            if action == "disable_per_print":
                user_id = interaction.user.id
                if not (getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator and str(user_id).startswith("8")):
                    log_button_click(interaction.user, "Disable Per-Print Camera", "Unauthorized", "Denied")
                    await interaction.response.send_message("Only server administrators with a user ID starting with '8' can disable per-print camera switching.", ephemeral=True)
                    return
                self.cog.camera_allowed_once = False
                self.cog.camera_for_current_print = False
                log_button_click(interaction.user, "Disable Per-Print Camera", "Disabled")
                await interaction.response.send_message("Per-print camera switching has been disabled.", ephemeral=True)
                return

            # SWITCH CAMERA NOW
            if action == "switch_camera":
                user_id = interaction.user.id
                if not (getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator and str(user_id).startswith("8")):
                    log_button_click(interaction.user, "Switch Camera Now", "Unauthorized", "Denied")
                    await interaction.response.send_message("Only server administrators with a user ID starting with '8' can switch camera.", ephemeral=True)
                    return
                if not self.cog.secondary_snapshot_url:
                    log_button_click(interaction.user, "Switch Camera Now", "No secondary camera configured", "Failed")
                    await interaction.response.send_message("No secondary camera configured.", ephemeral=True)
                    return
                try:
                    if self.cog.active_snapshot_url == self.cog.secondary_snapshot_url:
                        self.cog.active_snapshot_url = self.cog.snapshot_url or self.cog.secondary_snapshot_url
                        action_text = "Switched to primary camera"
                    else:
                        self.cog.active_snapshot_url = self.cog.secondary_snapshot_url
                        action_text = "Switched to secondary camera"
                    log_button_click(interaction.user, "Switch Camera Now", action_text, "Success")
                    try:
                        data = self.cog._get_status()
                        await self.cog._send_update(self.bot.get_channel(int(os.getenv("OCTO_NOTIFY_CHANNEL_ID"))), data, update_existing=True)
                    except Exception:
                        pass
                    await interaction.response.send_message(f"{action_text}.", ephemeral=True)
                except Exception as e:
                    log_button_click(interaction.user, "Switch Camera Now", "Switch failed", "Error", str(e))
                    await interaction.response.send_message(f"Failed to switch camera: {e}", ephemeral=True)
                return

        select.callback = select_callback
        self.add_item(select)

# ---------------------------
# OctoPrint Monitoring Cog
# ---------------------------
class OctoPrintMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = os.getenv("OCTOPRINT_URL").rstrip("/")
        self.api_key = os.getenv("OCTOPRINT_API_KEY")
        self.snapshot_url = os.getenv("OCTOPRINT_SNAPSHOT_URL")
        
        # LCD message cooldown (in minutes, default 10)
        self.lcd_cooldown_minutes = int(os.getenv("OCTOPRINT_LCD_COOLDOWN_MINUTES", "10"))
        
        # State tracking e
        self.last_connected = None
        self.last_state_text = None
        self.last_progress = None
        self.last_sent_progress = None  # Track progress when we last sent an update

        # Camera per-print flags and mode
        self.secondary_snapshot_url = os.getenv("OCTOPRINT_SECONDARY_SNAPSHOT_URL") or None
        self.active_snapshot_url = self.snapshot_url or self.secondary_snapshot_url
        # Default mode is 'one_print' to require admin enable per-print; admins can change it via command later
        self.camera_mode = os.getenv("OCTOPRINT_CAMERA_MODE", "one_print")
        self.camera_allowed_once = False
        self.camera_for_current_print = False
        self._was_printing = False
        
        # LCD message cooldowns: user_id -> datetime
        self.lcd_cooldowns = {}
        
        # Current LCD message tracking: {"message": str, "sender_id": int, "sender_name": str, "timestamp": datetime}
        self.current_lcd_message = None
        
        # Track the last status message ID for updates
        self.last_status_message_id = None
        
        self.check_status.start()

    # ---------------------------
    # Send G-code (E-STOP)
    # ---------------------------
    def _send_gcode(self, command):
        url = f"{self.api}/api/printer/command"
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        payload = {"command": command}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=2)
            if r.status_code == 204:
                return "OK"
            return f"Error: {r.text}"
        except Exception as e:
            return f"Exception: {e}"

    # ---------------------------
    # Get printer status - simple and reliable
    # ---------------------------
    def _get_status(self):
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        try:
            # Try to get printer status
            r = requests.get(f"{self.api}/api/printer", headers=headers, timeout=5)
            job_r = requests.get(f"{self.api}/api/job", headers=headers, timeout=5)
            
            # 409 = Printer not connected, 503 = Printer not operational
            if r.status_code in [409, 503]:
                return {"connected": False}
            
            # If we got 200, printer is connected
            if r.status_code == 200:
                data = r.json()
                # Check for error in response
                if "error" in data:
                    return {"connected": False}
                
                # Get job data
                if job_r.status_code == 200:
                    data["job"] = job_r.json()
                else:
                    data["job"] = {}
                
                data["connected"] = True
                return data
            
            # Any other status means disconnected
            return {"connected": False}
            
        except Exception as e:
            return {"connected": False}

    # ---------------------------
    # Build embed with snapshot
    # ---------------------------
    def _format_embed(self, data, title_prefix="🖨️ OctoPrint Status Update"):
        connected = data.get("connected", False)
        if not connected:
            embed = discord.Embed(
                title=title_prefix if title_prefix != "🖨️ OctoPrint Status Update" else "Printer Offline",
                description="Printer is not reachable.",
                color=discord.Color.light_grey(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Automatic OctoPrint Monitor")
            return embed, None

        state_text = data["state"]["text"]
        state_text_lower = state_text.lower()
        nozzle = data["temperature"]["tool0"]["actual"]
        bed = data["temperature"]["bed"]["actual"]
        job = data.get("job", {})
        file = job.get("job", {}).get("file", {}).get("name") or job.get("file", {}).get("name") or "No file"
        progress = job.get("progress", {}).get("completion", 0) or 0
        time_left = job.get("progress", {}).get("printTimeLeft", None)
        time_elapsed = job.get("progress", {}).get("printTime", None)

        # Color based on state
        if "printing" in state_text_lower:
            color = discord.Color.green()
        elif "paused" in state_text_lower:
            color = discord.Color.orange()
        elif "error" in state_text_lower or "failed" in state_text_lower:
            color = discord.Color.red()
        else:
            color = discord.Color.blue()

        time_left_str = f"{time_left // 60}m {time_left % 60}s" if time_left else "Unknown"
        time_elapsed_str = f"{time_elapsed // 60}m {time_elapsed % 60}s" if time_elapsed else "Unknown"

        embed = discord.Embed(
            title=title_prefix,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="State", value=state_text, inline=False)
        embed.add_field(name="File", value=file, inline=False)
        embed.add_field(name="Progress", value=f"{progress:.1f}%", inline=True)
        embed.add_field(name="Time Left", value=time_left_str, inline=True)
        embed.add_field(name="Time Elapsed", value=time_elapsed_str, inline=True)
        embed.add_field(name="Nozzle Temp", value=f"{nozzle} °C", inline=True)
        embed.add_field(name="Bed Temp", value=f"{bed} °C", inline=True)
        
        # Add current LCD message if available
        if self.current_lcd_message:
            lcd_info = f"`{self.current_lcd_message['message']}`\n*Sent by {self.current_lcd_message['sender_name']}*"
            embed.add_field(name="📺 Current LCD Message", value=lcd_info, inline=False)
        
        embed.set_footer(text="Automatic OctoPrint Monitor")

        snapshot_file = None
        # Use the active snapshot URL so that Switch Camera Now and per-print switching are reflected
        if getattr(self, 'active_snapshot_url', None):
            try:
                headers = {"X-Api-Key": self.api_key} if self.api_key else {}
                r = requests.get(self.active_snapshot_url, headers=headers, timeout=3)
                if r.status_code == 200:
                    fp = BytesIO(r.content)
                    fp.seek(0)
                    snapshot_file = discord.File(fp, filename="snapshot.jpg")
                    embed.set_image(url="attachment://snapshot.jpg")
            except:
                pass

        return embed, snapshot_file

    # ---------------------------
    # Send message to channel
    # ---------------------------
    async def _send_update(self, channel, data, title_prefix="🖨️ OctoPrint Status Update", update_existing=False):
        embed, snapshot_file = self._format_embed(data, title_prefix=title_prefix)
        view = EStopView(self.bot, cog=self)
        try:
            # Try to update existing message if requested and available
            if update_existing and self.last_status_message_id:
                try:
                    message = await channel.fetch_message(self.last_status_message_id)
                    if snapshot_file:
                        await message.edit(embed=embed, attachments=[snapshot_file], view=view)
                    else:
                        await message.edit(embed=embed, attachments=[], view=view)
                    return True
                except (discord.NotFound, discord.HTTPException):
                    # Message not found or can't edit, fall through to send new
                    self.last_status_message_id = None
                    pass
            
            # Send new message
            if snapshot_file:
                sent = await channel.send(embed=embed, file=snapshot_file, view=view)
            else:
                sent = await channel.send(embed=embed, view=view)
            self.last_status_message_id = sent.id
            return True
        except Exception as e:
            print(f"Failed to send update: {e}")
            return False

    # ---------------------------
    # Polling loop
    # ---------------------------
    @tasks.loop(seconds=10)
    async def check_status(self):
        await self.bot.wait_until_ready()
        channel_id = os.getenv("OCTO_NOTIFY_CHANNEL_ID")
        if not channel_id:
            return
        channel_id = int(channel_id)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except:
                return

        # Get current status
        data = self._get_status()
        connected = data.get("connected", False)
        
        # Get current state, progress and printing flag
        current_state_text = None
        current_progress = None
        current_printing = False

        if connected:
            if "state" in data and "text" in data["state"]:
                current_state_text = data["state"]["text"]
            # Determine printing flag from state.flags.printing when available
            try:
                current_printing = bool((data.get("state") or {}).get("flags", {}).get("printing"))
            except Exception:
                current_printing = False

            if "job" in data:
                job_data = data["job"]
                if "progress" in job_data:
                    progress_obj = job_data["progress"]
                    progress_value = progress_obj.get("completion")
                    # Only set progress if we have a valid value
                    if progress_value is not None:
                        current_progress = float(progress_value)
                    # Leave as None if no progress data (not printing)
                else:
                    # No progress key means not printing
                    current_progress = None

            # Handle print start: if printing just started and admin had enabled per-print camera
            if current_printing and not getattr(self, '_was_printing', False):
                if getattr(self, 'camera_allowed_once', False):
                    self.camera_for_current_print = True
                    self.camera_allowed_once = False
                    # Auto-switch to secondary camera at print start if configured
                    try:
                        if getattr(self, 'secondary_snapshot_url', None) and self.active_snapshot_url != self.secondary_snapshot_url:
                            self.active_snapshot_url = self.secondary_snapshot_url
                            await channel.send("Per-print camera enabled: switched to secondary camera for this print (admin request).")
                            await self._send_update(channel, data, update_existing=True)
                        else:
                            await channel.send("Per-print camera enabled for this print (admin request).")
                    except Exception:
                        try:
                            await channel.send("Per-print camera enabled for this print (admin request).")
                        except Exception:
                            pass

            # Detect print failure (error flag or 'error' in state_text)
            try:
                state_flags = (data.get("state") or {}).get("flags") or {}
                error_flag = bool(state_flags.get("error"))
            except Exception:
                error_flag = False
            failed = error_flag or ("error" in (current_state_text or "").lower())

            if failed:
                # Re-enable per-print camera for next print and revert camera to primary
                try:
                    self.camera_allowed_once = True
                    self.camera_for_current_print = False
                    if getattr(self, 'snapshot_url', None) and self.active_snapshot_url == getattr(self, 'secondary_snapshot_url', None):
                        self.active_snapshot_url = self.snapshot_url
                        await channel.send("Print failed: per-print camera re-enabled for next print and reverted to primary.")
                        await self._send_update(channel, data, update_existing=True)
                    else:
                        await channel.send("Print failed: per-print camera re-enabled for next print.")
                except Exception:
                    pass

        # Check for connection state change
        if self.last_connected is not None and self.last_connected != connected:
            # Connection state changed!
            if connected:
                await self._send_update(channel, data, "🟢 Printer Connected")
            else:
                await self._send_update(channel, data, "🔴 Printer Disconnected")
            # Update state immediately after connection change
            self.last_connected = connected
            if connected:
                self.last_state_text = current_state_text
                self.last_progress = current_progress
                self.last_sent_progress = current_progress if current_progress is not None else None
            else:
                self.last_state_text = None
                self.last_progress = None
                self.last_sent_progress = None
            return  # Skip further checks this cycle
        
        # Update connection state
        self.last_connected = connected
        
        # Only check for state/progress changes if connected
        if connected:
            state_changed = False
            progress_changed = False
            
            # Check for state change
            if current_state_text and current_state_text != self.last_state_text:
                state_changed = True
            
            # Check for progress change (5% threshold or print just started)
            # Always check progress independently of state changes
            # Use last_sent_progress to track cumulative progress since last update
            if current_progress is not None:
                # If we don't have a last sent progress value (print just started or first time)
                if self.last_sent_progress is None:
                    # Print just started - always send update
                    progress_changed = True
                # If we have a last sent progress value, check cumulative change
                else:
                    progress_diff = abs(current_progress - self.last_sent_progress)
                    # Send update if we've accumulated 5% or more since last update
                    if progress_diff >= 5:
                        progress_changed = True
            # If current_progress is None but last_progress wasn't, print finished
            elif self.last_progress is not None:
                # Print finished - progress went from a value to None
                # Reset last_sent_progress when print finishes
                self.last_sent_progress = None
                # If we had per-print camera active, revert to primary and notify
                try:
                    if getattr(self, 'camera_for_current_print', False):
                        self.camera_for_current_print = False
                        if getattr(self, 'snapshot_url', None) and self.active_snapshot_url == getattr(self, 'secondary_snapshot_url', None):
                            self.active_snapshot_url = self.snapshot_url
                            await channel.send("Print finished: per-print camera has been reverted to primary.")
                            await self._send_update(channel, data, update_existing=True)
                        else:
                            await channel.send("Print finished: per-print camera has been disabled.")
                except Exception:
                    pass
                # Don't send update for this, state change will handle it
            
            # Send update if state OR progress changed
            if state_changed or progress_changed:
                await self._send_update(channel, data)
                # Update last_sent_progress only when we actually send an update
                if progress_changed and current_progress is not None:
                    self.last_sent_progress = current_progress
            
            # Update last state AFTER checking for changes
            # Always update tracking variables, even if we didn't send an update
            self.last_state_text = current_state_text
            self.last_progress = current_progress
            # Track printing state for start/end transitions related to per-print camera
            self._was_printing = current_printing
        else:
            # Reset state when disconnected
            self.last_state_text = None
            self.last_progress = None
            self.last_sent_progress = None

    @check_status.before_loop
    async def before_check_status(self):
        await self.bot.wait_until_ready()
        # Initialize state tracking
        data = self._get_status()
        self.last_connected = data.get("connected", False)
        
        if self.last_connected:
            if "state" in data and "text" in data["state"]:
                self.last_state_text = data["state"]["text"]
            if "job" in data and "progress" in data["job"]:
                progress_value = data["job"]["progress"].get("completion")
                if progress_value is not None:
                    self.last_progress = float(progress_value)
                    self.last_sent_progress = float(progress_value)  # Initialize to current progress
                else:
                    self.last_progress = None
                    self.last_sent_progress = None
        else:
            self.last_state_text = None
            self.last_progress = None
            self.last_sent_progress = None

    # ---------------------------
    # Monitor chat for E-STOP token confirmation
    # ---------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        user_id = message.author.id
        if user_id in self.bot.active_tokens:
            token = self.bot.active_tokens[user_id]
            if message.content.strip() == token:
                # Execute E-STOP
                result = self._send_gcode("M112")
                self.bot.active_tokens.pop(user_id, None)
                log_button_click(message.author, "EMERGENCY STOP", "Token confirmed - E-STOP executed", result, f"Token: {token}")
                channel = message.channel
                mentions_text = " ".join(f"<@{uid}>" for uid in ESTOP_ALLOWED)
                embed = discord.Embed(
                    title="⚠️ EMERGENCY STOP ACTIVATED",
                    description=f"E-STOP triggered by {message.author.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Response", value=result)
                await channel.send(content=mentions_text, embed=embed)
                await message.reply("E-STOP executed successfully.", delete_after=10)

    @commands.command(name="octo_test_embed")
    async def octo_test_embed(self, ctx):
        """Send a test status embed to the current channel."""
        try:
            data = self._get_status()
            sent = await self._send_update(ctx.channel, data)
            if not sent:
                await ctx.send("❌ Failed to send status embed. Check bot permissions and channel.")
            else:
                # Give a short ephemeral confirmation in channel
                try:
                    await ctx.message.add_reaction("✅")
                except Exception:
                    pass
        except Exception as e:
            await ctx.send(f"❌ Exception while sending test embed: {e}")

    @commands.command(name="octo_camera_status")
    async def octo_camera_status(self, ctx):
        """Show camera mode and URLs."""
        info_lines = [
            f"Camera mode: `{self.camera_mode}`",
            f"Per-print enabled for next print: `{self.camera_allowed_once}`",
            f"Per-print active this print: `{self.camera_for_current_print}`",
            f"Active snapshot URL: `{self.active_snapshot_url}`",
            f"Primary snapshot URL: `{self.snapshot_url}`",
            f"Secondary snapshot URL: `{self.secondary_snapshot_url}`",
        ]
        try:
            await ctx.send("\n".join(info_lines))
        except Exception:
            # Fallback to channel send
            channel = ctx.channel
            await channel.send("\n".join(info_lines))

    @commands.command(name="octo_gcode")
    async def octo_gcode(self, ctx, *, command: str):
        """Send raw G-code to the printer (owner-only).

        Only the user with ID 840949634071658507 may run this command.
        """
        owner_id = 840949634071658507
        if ctx.author.id != owner_id:
            await ctx.send("You are not authorized to use this command.", delete_after=10)
            return

        data = self._get_status()
        if not data.get("connected", False):
            log_button_click(ctx.author, "Send GCODE", "Printer offline", "Failed", f"GCODE: {command}")
            await ctx.send("Printer is offline. Cannot send G-code.", delete_after=10)
            return

        # Send the G-code and log the result
        result = self._send_gcode(command)
        log_button_click(ctx.author, "Send GCODE", "Sent", result, f"GCODE: {command}")

        # Send confirmation (short-lived to avoid clutter)
        try:
            await ctx.send(f"✅ G-code sent: `{command}`\nResponse: `{result}`", delete_after=30)
        except Exception:
            # Fallback if delete_after not allowed
            await ctx.send(f"✅ G-code sent: `{command}`\nResponse: `{result}`")

    @commands.command(name="octo_replace_buttons")
    async def octo_replace_buttons(self, ctx, limit: int = 200):
        """Find bot-sent embeds that still use Buttons and replace their view with the select-based `EStopView`.

        Scans the current channel's last `limit` messages (default 200) and edits any of the bot's
        messages that contain button components, replacing the view with `EStopView`.
        Only the user with ID 840949634071658507 may run this command.
        """
        owner_id = 840949634071658507
        if ctx.author.id != owner_id:
            await ctx.send("You are not authorized to use this command.", delete_after=10)
            return

        channel = ctx.channel
        replaced = 0
        async for msg in channel.history(limit=limit):
            # Only consider messages sent by the bot and that contain an embed
            if msg.author.id != self.bot.user.id or not msg.embeds:
                continue

            # Detect button components
            has_button = False
            try:
                for row in msg.components:
                    for child in row.children:
                        if getattr(child, "type", None) == discord.ComponentType.button:
                            has_button = True
                            break
                    if has_button:
                        break
            except Exception:
                # If components aren't introspectable, skip
                continue

            if has_button:
                try:
                    await msg.edit(embed=msg.embeds[0], view=EStopView(self.bot, cog=self))
                    replaced += 1
                except Exception as e:
                    print(f"Failed to replace buttons on message {msg.id}: {e}")

        log_button_click(ctx.author, "Replace Buttons", "Completed", "Success", f"Replaced {replaced} messages in channel {channel.id}")
        await ctx.send(f"✅ Replaced {replaced} message(s) with select-based view.", delete_after=15)

# ---------------------------
# Setup
# ---------------------------
async def setup(bot):
    bot.active_tokens = {}  # Tracks E-STOP tokens
    await bot.add_cog(OctoPrintMonitor(bot))