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
                channel = await self.cog._get_notify_channel()
                if channel:
                    data = self.cog._get_status()
                    ok = await self.cog._send_update(channel, data, update_existing=True)
                    if not ok:
                        print("Failed to update status embed after LCD message: _send_update returned False")
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

    @discord.ui.button(label="EMERGENCY STOP", style=discord.ButtonStyle.danger, custom_id="estop_btn")
    async def estop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    @discord.ui.button(label="Update Image", style=discord.ButtonStyle.secondary, custom_id="update_image_btn")
    async def update_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_button_click(interaction.user, "Update Image", "Button clicked")
        await interaction.response.defer()
        
        if not self.cog:
            log_button_click(interaction.user, "Update Image", "Error", "Cog reference not available")
            await interaction.followup.send("Error: Cog reference not available.", ephemeral=True)
            return
        
        # Get current status
        data = self.cog._get_status()
        connected = data.get("connected", False)
        
        if not connected:
            log_button_click(interaction.user, "Update Image", "Printer offline", "Failed")
            await interaction.followup.send("Printer is offline. Cannot update image.", ephemeral=True)
            return
        
        # Get snapshot
        snapshot_file = None
        if self.cog.snapshot_url:
            try:
                headers = {"X-Api-Key": self.cog.api_key} if self.cog.api_key else {}
                r = requests.get(self.cog.snapshot_url, headers=headers, timeout=3)
                if r.status_code == 200:
                    fp = BytesIO(r.content)
                    fp.seek(0)
                    snapshot_file = discord.File(fp, filename="snapshot.jpg")
            except Exception as e:
                log_button_click(interaction.user, "Update Image", "Snapshot fetch failed", "Error", str(e))
                await interaction.followup.send(f"Failed to fetch snapshot: {e}", ephemeral=True)
                return
        
        # Update the message
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

    @discord.ui.button(label="Send LCD Message", style=discord.ButtonStyle.primary, custom_id="lcd_message_btn")
    async def lcd_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_button_click(interaction.user, "Send LCD Message", "Button clicked")
        
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
        
        # Show modal to get message
        modal = LCDMessageModal(self.cog)
        await interaction.response.send_modal(modal)

# ---------------------------
# OctoPrint Monitoring Cog
# ---------------------------
class OctoPrintMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Read OctoPrint API URL (may be missing in some environments)
        api_env = os.getenv("OCTOPRINT_URL")
        if api_env:
            self.api = api_env.rstrip("/")
        else:
            # Keep empty string to allow cog to load; calls to _get_status will return disconnected
            print("⚠️ Warning: OCTOPRINT_URL not set; OctoPrint monitoring disabled until configured")
            self.api = ""
        self.api_key = os.getenv("OCTOPRINT_API_KEY")
        self.snapshot_url = os.getenv("OCTOPRINT_SNAPSHOT_URL")
        
        # LCD message cooldown (in minutes, default 10)
        self.lcd_cooldown_minutes = int(os.getenv("OCTOPRINT_LCD_COOLDOWN_MINUTES", "10"))
        
        # State tracking e
        self.last_connected = None
        self.last_state_text = None
        self.last_progress = None
        self.last_sent_progress = None  # Track progress when we last sent an update
        
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
        if not self.api:
            return "Error: OCTOPRINT_URL not configured"
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
            # If API URL missing, return disconnected status
            if not self.api:
                return {"connected": False}

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
        if self.snapshot_url:
            try:
                headers = {"X-Api-Key": self.api_key} if self.api_key else {}
                r = requests.get(self.snapshot_url, headers=headers, timeout=3)
                if r.status_code == 200:
                    fp = BytesIO(r.content)
                    fp.seek(0)
                    snapshot_file = discord.File(fp, filename="snapshot.jpg")
                    embed.set_image(url="attachment://snapshot.jpg")
            except:
                pass

        return embed, snapshot_file

    # ---------------------------
    # Helper: resolve notify channel
    # ---------------------------
    async def _get_notify_channel(self):
        """Return a channel object for OCTO_NOTIFY_CHANNEL_ID or None and print diagnostics."""
        channel_id = os.getenv("OCTO_NOTIFY_CHANNEL_ID")
        if not channel_id:
            print("OCTO_NOTIFY_CHANNEL_ID is not set")
            return None
        try:
            cid = int(channel_id)
        except Exception as e:
            print(f"OCTO_NOTIFY_CHANNEL_ID invalid: {channel_id} ({e})")
            return None
        channel = self.bot.get_channel(cid)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(cid)
            except discord.Forbidden:
                print(f"Forbidden: cannot access channel {cid}")
                return None
            except Exception as e:
                print(f"Failed to fetch channel {cid}: {e}")
                return None
        return channel

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
                    print(f"Updated existing status message (id={self.last_status_message_id}) in channel {getattr(channel, 'id', channel)}")
                    return True
                except (discord.NotFound, discord.HTTPException) as e:
                    # Message not found or can't edit, fall through to send new
                    print(f"Existing message not editable/found: {e}")
                    self.last_status_message_id = None
                    pass
            
            # Send new message
            if snapshot_file:
                sent = await channel.send(embed=embed, file=snapshot_file, view=view)
            else:
                sent = await channel.send(embed=embed, view=view)
            self.last_status_message_id = sent.id
            print(f"Sent new status message (id={sent.id}) to channel {getattr(channel, 'id', channel)}")
            return True
        except Exception as e:
            print(f"Failed to send update: {e}")
            # If sending failed because channel missing/forbidden, print channel id for diagnostics
            try:
                print(f"Channel: {getattr(channel, 'id', channel)}")
            except Exception:
                pass
            return False

    # ---------------------------
    # Polling loop
    # ---------------------------
    @tasks.loop(seconds=10)
    async def check_status(self):
        await self.bot.wait_until_ready()
        channel = await self._get_notify_channel()
        if channel is None:
            # Diagnostic: indicate missing channel or misconfiguration
            print("OctoPrint: No notify channel available (OCTO_NOTIFY_CHANNEL_ID unset or not accessible). Skipping this check iteration.")
            return

        # Get current status
        data = self._get_status()
        connected = data.get("connected", False)
        
        # Get current state and progress
        current_state_text = None
        current_progress = None
        
        if connected:
            if "state" in data and "text" in data["state"]:
                current_state_text = data["state"]["text"]
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

        # Check for connection state change
        if self.last_connected is not None and self.last_connected != connected:
            # Connection state changed!
            if connected:
                ok = await self._send_update(channel, data, "🟢 Printer Connected")
                if not ok:
                    print("Failed to send connection-change (connected) update to channel")
            else:
                ok = await self._send_update(channel, data, "🔴 Printer Disconnected")
                if not ok:
                    print("Failed to send connection-change (disconnected) update to channel")
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
            print(f"=== Poll Check: state='{current_state_text}', progress={current_progress}, last_state='{self.last_state_text}', last_progress={self.last_progress} ===")
            
            state_changed = False
            progress_changed = False
            
            # Check for state change
            if current_state_text and current_state_text != self.last_state_text:
                print(f"State changed: '{self.last_state_text}' -> '{current_state_text}'")
                state_changed = True
            
            # Check for progress change (5% threshold or print just started)
            # Always check progress independently of state changes
            # Use last_sent_progress to track cumulative progress since last update
            if current_progress is not None:
                # If we don't have a last sent progress value (print just started or first time)
                if self.last_sent_progress is None:
                    # Print just started - always send update
                    print(f"Progress started: {current_progress}% (last sent was None)")
                    progress_changed = True
                # If we have a last sent progress value, check cumulative change
                else:
                    progress_diff = abs(current_progress - self.last_sent_progress)
                    print(f"Progress check: last_sent={self.last_sent_progress}%, current={current_progress}%, diff={progress_diff}%")
                    # Send update if we've accumulated 5% or more since last update
                    if progress_diff >= 5:
                        print(f"✓ Progress update triggered: {self.last_sent_progress}% -> {current_progress}% (diff: {progress_diff}%)")
                        progress_changed = True
                    else:
                        print(f"✗ Progress update skipped: diff {progress_diff}% < 5% threshold")
            # If current_progress is None but last_progress wasn't, print finished
            elif self.last_progress is not None:
                # Print finished - progress went from a value to None
                print(f"Print finished: progress went from {self.last_progress}% to None")
                # Reset last_sent_progress when print finishes
                self.last_sent_progress = None
                # Don't send update for this, state change will handle it
            
            # Send update if state OR progress changed
            if state_changed or progress_changed:
                print(f"Sending update: state_changed={state_changed}, progress_changed={progress_changed}")
                ok = await self._send_update(channel, data)
                if not ok:
                    print("Failed to send progress/state update to channel")
                # Update last_sent_progress only when we actually send an update
                if progress_changed and current_progress is not None and ok:
                    self.last_sent_progress = current_progress
            else:
                print(f"No update needed: state_changed={state_changed}, progress_changed={progress_changed}")
            
            # Update last state AFTER checking for changes
            # Always update tracking variables, even if we didn't send an update
            self.last_state_text = current_state_text
            self.last_progress = current_progress
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

    @commands.command(name="octo_debug", help="Admin: debug OctoPrint integration and connectivity")
    async def octo_debug(self, ctx: commands.Context):
        # Restrict to authorized users or server admins
        if not (ctx.author.id in ESTOP_ALLOWED or getattr(ctx.author, "guild_permissions", None) and ctx.author.guild_permissions.administrator):
            await ctx.send("You don't have permission to use this command.")
            return

        log_button_click(ctx.author, "DEBUG", "Requested")

        lines = []
        lines.append(f"API URL: {self.api or '(unset)'}")
        lines.append(f"API Key: {'set' if self.api_key else 'unset'}")
        lines.append(f"Snapshot URL: {self.snapshot_url or '(unset)'}")
        lines.append(f"Last status message id: {self.last_status_message_id}")
        lines.append(f"Last connected: {self.last_connected}")
        lines.append(f"Last state text: {self.last_state_text}")
        lines.append("")

        # Call internal status function
        try:
            st = self._get_status()
            lines.append("_get_status() returned:")
            try:
                # Safe stringify small JSON-like structures
                import json
                st_s = json.dumps(st, default=str, indent=2)
                for ln in st_s.splitlines():
                    lines.append(ln)
            except Exception:
                lines.append(str(st))
        except Exception as e:
            lines.append(f"_get_status() raised: {e}")

        # Try direct HTTP queries if API configured
        if self.api:
            try:
                r = requests.get(f"{self.api}/api/printer", headers={"X-Api-Key": self.api_key} if self.api_key else {}, timeout=5)
                lines.append(f"GET /api/printer: status={r.status_code}")
                try:
                    lines.append(str(r.json())[:1000])
                except Exception:
                    lines.append(r.text[:1000])
            except Exception as e:
                lines.append(f"GET /api/printer failed: {e}")

            try:
                r2 = requests.get(f"{self.api}/api/job", headers={"X-Api-Key": self.api_key} if self.api_key else {}, timeout=5)
                lines.append(f"GET /api/job: status={r2.status_code}")
                try:
                    lines.append(str(r2.json())[:1000])
                except Exception:
                    lines.append(r2.text[:1000])
            except Exception as e:
                lines.append(f"GET /api/job failed: {e}")
        else:
            lines.append("API not configured; skipping live HTTP tests.")

        # Try snapshot fetch
        if self.snapshot_url:
            try:
                rr = requests.get(self.snapshot_url, timeout=5)
                lines.append(f"Snapshot fetch: status={rr.status_code}, content_length={len(rr.content) if rr.content else 0}")
            except Exception as e:
                lines.append(f"Snapshot fetch failed: {e}")
        else:
            lines.append("No snapshot URL configured.")

        out = "\n".join(lines)

        # Send DM to requester with debug output, fallback to channel if DM fails
        sent = False
        try:
            for i in range(0, len(out), 1900):
                chunk = out[i:i+1900]
                await ctx.author.send(f"```\n{chunk}\n```")
            sent = True
        except Exception:
            sent = False

        if sent:
            await ctx.send("Debug info DM'd to you.")
        else:
            # Send in channel as codeblock (may be large)
            try:
                for i in range(0, len(out), 1900):
                    chunk = out[i:i+1900]
                    await ctx.send(f"```\n{chunk}\n```")
            except Exception as e:
                await ctx.send(f"Failed to deliver debug output: {e}")

    @commands.command(name="octo_send_status", help="Admin: force send current status to notify channel (for testing)")
    async def octo_send_status(self, ctx: commands.Context):
        if not (ctx.author.id in ESTOP_ALLOWED or getattr(ctx.author, "guild_permissions", None) and ctx.author.guild_permissions.administrator):
            await ctx.send("You don't have permission to use this command.")
            return
        channel = await self._get_notify_channel()
        if not channel:
            await ctx.send("Notify channel not configured or accessible. Check console logs for diagnostics.")
            return
        data = self._get_status()
        ok = await self._send_update(channel, data)
        if ok:
            await ctx.send(f"Status sent to channel {channel.id}")
        else:
            await ctx.send("Failed to send status update to notify channel. Check console logs for diagnostics.")

# ---------------------------
# Setup
# ---------------------------
async def setup(bot):
    bot.active_tokens = {}  # Tracks E-STOP tokens
    await bot.add_cog(OctoPrintMonitor(bot))
