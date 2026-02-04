from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import time
from io import BytesIO
import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
try:
    from PIL import Image
except Exception:
    Image = None
try:
    import pytz
except ImportError:
    pytz = None

import aiohttp
import zipfile
import re


# Removed user-whitelist — only admins allowed for tuna commands

# Set this to a specific user ID if you want to allow a particular user, or set to None to disable
ALLOWED_TUNA_USER_ID = 840949634071658507 #tuna id yes

TIMEZONE_DATA_FILE = os.path.join("data", "timezones.json")

def ensure_data_dir():
    os.makedirs("data", exist_ok=True)

def load_timezones():
    """Load timezone data from JSON file."""
    ensure_data_dir()
    if os.path.exists(TIMEZONE_DATA_FILE):
        try:
            with open(TIMEZONE_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_timezones(data):
    """Save timezone data to JSON file."""
    ensure_data_dir()
    try:
        with open(TIMEZONE_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving timezones: {e}")

def parse_timezone_input(input_str: str) -> Optional[str]:
    """Parse timezone input from various formats.
    Returns timezone string (e.g., 'America/New_York') or None if invalid.
    """
    if not pytz:
        return None
    
    input_str = input_str.strip()
    
    # Try direct timezone name first (e.g., "America/New_York", "Europe/London")
    try:
        tz = pytz.timezone(input_str)
        return input_str
    except Exception:
        pass
    
    # Try common abbreviations
    abbrev_map = {
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "GMT": "Europe/London",
        "UTC": "UTC",
        "BST": "Europe/London",
        "CET": "Europe/Paris",
        "CEST": "Europe/Paris",
        "JST": "Asia/Tokyo",
        "AEST": "Australia/Sydney",
        "AEDT": "Australia/Sydney",
    }
    
    upper_input = input_str.upper()
    if upper_input in abbrev_map:
        return abbrev_map[upper_input]
    
    # Try searching by country/region name
    # Common mappings
    region_map = {
        "new york": "America/New_York",
        "los angeles": "America/Los_Angeles",
        "chicago": "America/Chicago",
        "denver": "America/Denver",
        "london": "Europe/London",
        "paris": "Europe/Paris",
        "tokyo": "Asia/Tokyo",
        "sydney": "Australia/Sydney",
        "toronto": "America/Toronto",
        "vancouver": "America/Vancouver",
        "mexico city": "America/Mexico_City",
        "sao paulo": "America/Sao_Paulo",
        "berlin": "Europe/Berlin",
        "madrid": "Europe/Madrid",
        "rome": "Europe/Rome",
        "moscow": "Europe/Moscow",
        "dubai": "Asia/Dubai",
        "singapore": "Asia/Singapore",
        "hong kong": "Asia/Hong_Kong",
        "beijing": "Asia/Shanghai",
        "shanghai": "Asia/Shanghai",
    }
    
    lower_input = input_str.lower()
    if lower_input in region_map:
        return region_map[lower_input]
    
    # Try fuzzy search in pytz timezones
    all_timezones = pytz.all_timezones
    lower_input = input_str.lower()
    for tz_name in all_timezones:
        if lower_input in tz_name.lower() or tz_name.lower().endswith(f"/{lower_input}"):
            return tz_name
    
    return None

def get_user_timezone(user_id: int) -> Optional[str]:
    """Get user's timezone string."""
    data = load_timezones()
    return data.get(str(user_id))

def set_user_timezone(user_id: int, tz_string: str):
    """Set user's timezone."""
    data = load_timezones()
    data[str(user_id)] = tz_string
    save_timezones(data)

def format_timezone_info(tz_string: str) -> str:
    """Format timezone information for display."""
    if not pytz:
        return tz_string
    
    try:
        tz = pytz.timezone(tz_string)
        now = datetime.now(tz)
        offset = now.utcoffset()
        offset_hours = offset.total_seconds() / 3600
        
        # Format offset
        if offset_hours >= 0:
            offset_str = f"+{int(offset_hours)}"
        else:
            offset_str = str(int(offset_hours))
        
        # Get abbreviation if available
        abbrev = now.strftime("%Z") or ""
        if abbrev:
            abbrev = f" ({abbrev})"
        
        return f"{tz_string}{abbrev} — UTC{offset_str}"
    except Exception:
        return tz_string

class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):

        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to check bot responsiveness."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server_info", description="Get server information")
    async def server_info(self, interaction: discord.Interaction):
        """Display basic server information."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Server Information: {guild.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="timezone", description="View or set your timezone.")
    @app_commands.describe(
        member="Member to view timezone for (optional)",
        timezone_input="Timezone to set (country, region, abbreviation, or current time)"
    )
    async def timezone(self, interaction: discord.Interaction, member: Optional[discord.Member] = None, timezone_input: Optional[str] = None):
        """View or set timezone."""
        if not pytz:
            await interaction.response.send_message("❌ pytz library is not installed. Please install it with `pip install pytz`.", ephemeral=True)
            return
        
        # If timezone_input is provided, set timezone
        if timezone_input:
            tz_string = parse_timezone_input(timezone_input)
            if not tz_string:
                await interaction.response.send_message(
                    f"❌ Could not parse timezone: `{timezone_input}`\n\n"
                    "Try using:\n"
                    "• Full timezone name (e.g., `America/New_York`, `Europe/London`)\n"
                    "• Abbreviation (e.g., `EST`, `PST`, `GMT`)\n"
                    "• City name (e.g., `New York`, `London`, `Tokyo`)",
                    ephemeral=True
                )
                return
            
            set_user_timezone(interaction.user.id, tz_string)
            embed = discord.Embed(
                title="✅ Timezone Set",
                description=f"Your timezone has been set to:\n**{format_timezone_info(tz_string)}**",
                color=discord.Color.green()
            )
            if pytz:
                try:
                    tz = pytz.timezone(tz_string)
                    now = datetime.now(tz)
                    embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
                except Exception:
                    pass
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Otherwise, view timezone
        target_user = member or interaction.user
        tz_string = get_user_timezone(target_user.id)
        
        embed = discord.Embed(
            title="🕐 Timezone",
            color=discord.Color.blue()
        )
        embed.set_author(name=str(target_user), icon_url=target_user.display_avatar.url)
        
        if tz_string:
            embed.description = f"**Timezone:** {format_timezone_info(tz_string)}"
            if pytz:
                try:
                    tz = pytz.timezone(tz_string)
                    now = datetime.now(tz)
                    embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
                    embed.add_field(name="UTC Offset", value=f"UTC{now.strftime('%z')}", inline=True)
                except Exception:
                    pass
        else:
            embed.description = "No timezone set."
            embed.add_field(
                name="How to set",
                value="Use `/timezone timezone_input:<your_timezone>`\n\n"
                      "Examples:\n"
                      "• `/timezone timezone_input:America/New_York`\n"
                      "• `/timezone timezone_input:EST`\n"
                      "• `/timezone timezone_input:London`",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="timezone_set", description="Set your timezone.")
    @app_commands.describe(timezone_input="Timezone (country, region, abbreviation, or current time)")
    async def timezone_set(self, interaction: discord.Interaction, timezone_input: str):
        """Set your timezone."""
        if not pytz:
            await interaction.response.send_message("❌ pytz library is not installed. Please install it with `pip install pytz`.", ephemeral=True)
            return
        
        tz_string = parse_timezone_input(timezone_input)
        if not tz_string:
            await interaction.response.send_message(
                f"❌ Could not parse timezone: `{timezone_input}`\n\n"
                "Try using:\n"
                "• Full timezone name (e.g., `America/New_York`, `Europe/London`)\n"
                "• Abbreviation (e.g., `EST`, `PST`, `GMT`)\n"
                "• City name (e.g., `New York`, `London`, `Tokyo`)",
                ephemeral=True
            )
            return
        
        set_user_timezone(interaction.user.id, tz_string)
        embed = discord.Embed(
            title="✅ Timezone Set",
            description=f"Your timezone has been set to:\n**{format_timezone_info(tz_string)}**",
            color=discord.Color.green()
        )
        if pytz:
            try:
                tz = pytz.timezone(tz_string)
                now = datetime.now(tz)
                embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
            except Exception:
                pass
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        """Simple ping command to check bot responsiveness."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.group(name="tz", invoke_without_command=True)
    async def tz(self, ctx, member: Optional[discord.Member] = None):
        """View timezone for yourself or another user."""
        if not pytz:
            await ctx.send("❌ pytz library is not installed. Please install it with `pip install pytz`.")
            return
        
        target_user = member or ctx.author
        tz_string = get_user_timezone(target_user.id)
        
        embed = discord.Embed(
            title="🕐 Timezone",
            color=discord.Color.blue()
        )
        embed.set_author(name=str(target_user), icon_url=target_user.display_avatar.url)
        
        if tz_string:
            embed.description = f"**Timezone:** {format_timezone_info(tz_string)}"
            if pytz:
                try:
                    tz = pytz.timezone(tz_string)
                    now = datetime.now(tz)
                    # Convert to UTC timestamp for Discord timestamp
                    timestamp = int(now.timestamp())
                    embed.add_field(name="Current Time", value=f"<t:{timestamp}:F>", inline=False)
                except Exception:
                    pass
        else:
            embed.description = "No timezone set."
            embed.add_field(
                name="How to set",
                value="Use `!tz set <timezone>` or `/timezone_set`\n\n"
                      "Examples:\n"
                      "• `!tz set America/New_York`\n"
                      "• `!tz set EST`\n"
                      "• `!tz set London`",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @tz.command(name="set")
    async def tz_set(self, ctx, *, timezone_input: str):
        """Set your timezone."""
        if not pytz:
            await ctx.send("❌ pytz library is not installed. Please install it with `pip install pytz`.")
            return
        
        tz_string = parse_timezone_input(timezone_input)
        if not tz_string:
            await ctx.send(
                f"❌ Could not parse timezone: `{timezone_input}`\n\n"
                "Try using:\n"
                "• Full timezone name (e.g., `America/New_York`, `Europe/London`)\n"
                "• Abbreviation (e.g., `EST`, `PST`, `GMT`)\n"
                "• City name (e.g., `New York`, `London`, `Tokyo`)"
            )
            return
        
        set_user_timezone(ctx.author.id, tz_string)
        embed = discord.Embed(
            title="✅ Timezone Set",
            description=f"Your timezone has been set to:\n**{format_timezone_info(tz_string)}**",
            color=discord.Color.green()
        )
        if pytz:
            try:
                tz = pytz.timezone(tz_string)
                now = datetime.now(tz)
                embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
            except Exception:
                pass
        await ctx.send(embed=embed)

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        """Shows how long the bot has been running."""
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        if minutes > 0:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"
        
        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description=f"I've been running for **{uptime_str}**",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.group(name="tuna")
    @commands.has_guild_permissions(administrator=True)
    async def tuna(self, ctx):
        """Tuna utility commands. Only server admins may use these."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna role` or `!tuna dm` for available commands.")

    @tuna.group(name="role")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_role(self, ctx):
        """Role management commands (admins only)."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna role add`, `!tuna role list`, or `!tuna role remove`")

    @tuna.group(name="create")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_create(self, ctx):
        """Creation utilities for tuna (admins only)."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna create role <name> [hexcolor]`")

    @tuna_role.command(name="add")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_role_add(self, ctx, user: discord.Member, *, role_name: str):
        """Add a role to a user. (admins only)"""
        try:
            # Find the role by name (case insensitive)
            role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)
            if not role:
                await ctx.send(f"❌ Role '{role_name}' not found.")
                return

            # Check if user already has the role
            if role in user.roles:
                await ctx.send(f"❌ {user.mention} already has the role {role.mention}")
                return

            # Add the role
            await user.add_roles(role)
            embed = discord.Embed(
                title="✅ Role Added",
                description=f"Successfully added {role.mention} to {user.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage roles.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @tuna_role.command(name="list")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_role_list(self, ctx, user: discord.Member):
        """List all roles for a user. (admins only)"""
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        
        if not roles:
            await ctx.send(f"{user.mention} has no roles.")
            return
        
        embed = discord.Embed(
            title=f"Roles for {user.display_name}",
            description="\n".join(roles),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @tuna_role.command(name="remove")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_role_remove(self, ctx, user: discord.Member, *, role_name: str):
        """Remove a role from a user. (admins only)"""
        try:
            # Find the role by name (case insensitive)
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.send(f"❌ Role '{role_name}' not found.")
                return
            
            # Check if user has the role
            if role not in user.roles:
                await ctx.send(f"❌ {user.mention} doesn't have the role {role.mention}")
                return
            
            # Remove the role
            await user.remove_roles(role)
            embed = discord.Embed(
                title="✅ Role Removed",
                description=f"Successfully removed {role.mention} from {user.mention}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage roles.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @tuna_role.command(name="members")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_role_members(self, ctx, *, role_name: str):
        """List members who have a given role (admins only)."""
        # Try role mention first
        role = None
        if role_name.startswith("<@&") and role_name.endswith(">"):
            try:
                role_id = int(role_name[3:-1])
                role = ctx.guild.get_role(role_id)
            except ValueError:
                role = None
        if role is None:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f"❌ Role '{role_name}' not found.")
            return

        members = [member.mention for member in role.members]
        if not members:
            await ctx.send(f"No members have {role.mention}.")
            return

        # Avoid overly long messages
        joined = ", ".join(members)
        if len(joined) > 3800:
            # Chunk into multiple messages
            await ctx.send(f"Members with {role.mention} (total {len(members)}):")
            chunk = []
            length = 0
            for m in members:
                if length + len(m) + 2 > 1900:
                    await ctx.send(", ".join(chunk))
                    chunk = [m]
                    length = len(m)
                else:
                    chunk.append(m)
                    length += len(m) + 2
            if chunk:
                await ctx.send(", ".join(chunk))
            return

        embed = discord.Embed(
            title=f"Members with {role.name}",
            description=joined,
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @tuna.command(name="dm")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_dm(self, ctx, target, *, message: str):
        """Send a DM to a user or all members with a specific role. (admins only)"""
        try:
            # Try to parse as user mention/ID first. If that fails, allow numeric role IDs.
            role = None
            try:
                if target.startswith('<@') and target.endswith('>'):
                    # User mention
                    user_id = int(target[2:-1].replace('!', ''))
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"**Message from {ctx.guild.name}:**\n{message}")
                    await ctx.send(f"✅ DM sent to {user.mention}")
                    return
                else:
                    # Try as user ID first
                    user_id = int(target)
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"**Message from {ctx.guild.name}:**\n{message}")
                    await ctx.send(f"✅ DM sent to {user.mention}")
                    return
            except (ValueError, discord.NotFound):
                # Not a user — maybe it's a numeric role ID; check guild roles if we have a guild
                try:
                    if ctx.guild and target.isdigit():
                        role_candidate = ctx.guild.get_role(int(target))
                        if role_candidate:
                            role = role_candidate
                except Exception:
                    role = None

            # Try to find role by name if we didn't already resolve by ID
            if role is None:
                role = discord.utils.get(ctx.guild.roles, name=target) if ctx.guild else None
            if role:
                sent_count = 0
                failed_count = 0
                
                for member in role.members:
                    try:
                        await member.send(f"**Message from {ctx.guild.name} (via {role.name}):**\n{message}")
                        sent_count += 1
                    except:
                        failed_count += 1
                
                embed = discord.Embed(
                    title="✅ DMs Sent",
                    description=f"Sent to {sent_count} members with role {role.mention}",
                    color=discord.Color.green()
                )
                if failed_count > 0:
                    embed.add_field(name="Failed", value=f"{failed_count} members couldn't receive DMs", inline=False)
                await ctx.send(embed=embed)
                return
            
            await ctx.send("❌ Could not find user or role. Use @user, user ID, or role name.")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @tuna.command(name="say")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_say(self, ctx, channel: discord.TextChannel = None, *, message: str = None):
        """Send a message to a channel. (admins only)"""
        if message is None and channel is None:
            await ctx.send("Usage: `!tuna say [#channel] <message>`")
            return
        if message is None and channel is not None:
            await ctx.send("Usage: `!tuna say [#channel] <message>`")
            return
        target_channel = channel or ctx.channel
        try:
            await target_channel.send(message)
            if target_channel.id != ctx.channel.id:
                await ctx.send(f"✅ Sent message in {target_channel.mention}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in that channel.")
        except Exception as e:
            await ctx.send(f"❌ Failed to send message: {str(e)}")

    @tuna.command(name="servers")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_servers(self, ctx):
        """List servers the bot is in (admins only)."""
        guilds = list(self.bot.guilds)
        guilds_sorted = sorted(guilds, key=lambda g: g.member_count or 0, reverse=True)
        total = len(guilds_sorted)
        lines = [f"{g.name} — ID: `{g.id}` — Members: {g.member_count}" for g in guilds_sorted]
        header = f"I am in {total} server(s):\n"
        text = header + "\n".join(lines)
        if len(text) <= 1900:
            await ctx.send("```\n" + text + "\n```")
        else:
            # chunk output
            await ctx.send(header)
            chunk = []
            size = 0
            for line in lines:
                if size + len(line) + 1 > 1900:
                    await ctx.send("```\n" + "\n".join(chunk) + "\n```")
                    chunk = [line]
                    size = len(line)
                else:
                    chunk.append(line)
                    size += len(line) + 1
            if chunk:
                await ctx.send("```\n" + "\n".join(chunk) + "\n```")

    @tuna.command(name="perms")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_perms(self, ctx, channel: discord.TextChannel = None):
        """Show the bot's permissions in the guild or a specified channel. (admins only)"""
        target_channel = channel or ctx.channel
        me = ctx.guild.me
        perms = target_channel.permissions_for(me)
        true_perms = [
            name.replace('_', ' ').title()
            for name, value in perms if value
        ]
        false_perms = [
            name.replace('_', ' ').title()
            for name, value in perms if not value
        ]

        embed = discord.Embed(
            title="Bot Permissions",
            description=f"Channel: {target_channel.mention}",
            color=discord.Color.teal()
        )
        embed.add_field(name="Allowed", value=", ".join(true_perms) or "None", inline=False)
        embed.add_field(name="Denied", value=", ".join(false_perms) or "None", inline=False)
        await ctx.send(embed=embed)

    @tuna.command(name="invite")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_invite(self, ctx):
        """Show OAuth2 invite links for the bot (admins only)."""
        client_id = self.bot.user.id if self.bot.user else None
        if client_id is None:
            await ctx.send("❌ Unable to determine bot user ID.")
            return
        scopes = "bot%20applications.commands"
        base = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope={scopes}"
        # No preset permissions (choose in UI)
        basic_url = base
        # Administrator preset
        admin_url = base + "&permissions=8"
        embed = discord.Embed(title="Invite Links", color=discord.Color.gold())
        embed.add_field(name="Basic", value=f"[Add Bot]({basic_url})", inline=False)
        embed.add_field(name="Admin", value=f"[Add Bot (Administrator)]({admin_url})", inline=False)
        await ctx.send(embed=embed)

       @tuna.command(name="invite_all")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_invite_all(self, ctx, include_admin: bool = False):
        """Send invite link(s) in the current channel (admins only).
        Usage: !tuna invite_all [include_admin=True]"""

        client_id = self.bot.user.id if self.bot.user else None
        if client_id is None:
            await ctx.send("❌ Unable to determine bot user ID.")
            return

        scopes = "bot%20applications.commands"
        base = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope={scopes}"
        basic_url = base
        admin_url = base + "&permissions=8"

        embed = discord.Embed(
            title=f"Invite links for {self.bot.user.name}",
            description="Here are the bot invite links.",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Basic",
            value=f"[Add Bot]({basic_url})",
            inline=False
        )

        if include_admin:
            embed.add_field(
                name="Admin",
                value=f"[Add Bot (Administrator)]({admin_url})",
                inline=False
            )

        try:
            await ctx.send(embed=embed)
            await ctx.send("✅ Invite links sent successfully.")

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in this channel.")

        except discord.HTTPException as e:
            await ctx.send(f"❌ HTTP error while sending message: {e}")

        except Exception as e:
            await ctx.send(f"❌ Unexpected error: {type(e).__name__}: {e}")

    @tuna.command(name="shard")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_shard(self, ctx):
        """Show shard info (admins only)."""
        shard_count = self.bot.shard_count or 1
        latencies = getattr(self.bot, "latencies", None) or []
        if not latencies:
            latencies = [(0, self.bot.latency)]
        per_shard = {}
        for g in self.bot.guilds:
            sid = g.shard_id if g.shard_id is not None else 0
            per_shard[sid] = per_shard.get(sid, 0) + 1
        lines = []
        for sid, latency in sorted(latencies, key=lambda x: x[0]):
            ms = int(latency * 1000)
            count = per_shard.get(sid, 0)
            lines.append(f"Shard {sid}: {ms}ms — {count} guilds")
        embed = discord.Embed(title="Shard Info", color=discord.Color.purple())
        embed.add_field(name="Shard Count", value=str(shard_count), inline=True)
        embed.add_field(name="Total Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latencies", value="\n".join(lines) or "N/A", inline=False)
        await ctx.send(embed=embed)

    @tuna.command(name="stats")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_stats(self, ctx):
        """Show system and runtime stats for the bot (admins only)."""
        # Uptime
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        uptime_str = (f"{days}d " if days else "") + (f"{hours}h " if hours else "") + (f"{minutes}m " if minutes else "") + f"{seconds}s"

        # Versions
        import sys as _sys  # local import to avoid global dependency
        pyver = f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}"
        dpyver = discord.__version__
        guilds = len(self.bot.guilds)
        users = sum(g.member_count or 0 for g in self.bot.guilds)

        # Optional psutil
        cpu = mem = None
        try:
            import psutil  # type: ignore
            process = psutil.Process()
            with process.oneshot():
                rss = process.memory_info().rss
                mem = f"{rss / (1024*1024):.2f} MiB"
                cpu = f"{psutil.cpu_percent(interval=0.2):.1f}%"
        except Exception:
            pass

        embed = discord.Embed(title="Bot Stats", color=discord.Color.green())
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Guilds", value=str(guilds), inline=True)
        embed.add_field(name="Users (sum)", value=str(users), inline=True)
        embed.add_field(name="Python", value=pyver, inline=True)
        embed.add_field(name="discord.py", value=dpyver, inline=True)
        if mem:
            embed.add_field(name="Memory", value=mem, inline=True)
        if cpu:
            embed.add_field(name="CPU", value=cpu, inline=True)
        await ctx.send(embed=embed)

    @tuna_create.command(name="role")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_create_role(self, ctx, role_name: str, color: str = None):
        """Create a role. (admins only)"""
        # authorization (double-check)
        is_admin = getattr(ctx.author.guild_permissions, "administrator", False)
        if ctx.author.id != ALLOWED_TUNA_USER_ID and not is_admin:
            await ctx.send("❌ You are not allowed to use tuna commands.")
            return

        # parse color if provided
        role_color = None
        c = None
        if color:
            c = color.strip()
            if c.startswith("#"):
                c = c[1:]
            if len(c) == 3:
                c = "".join(ch * 2 for ch in c)
            if len(c) != 6:
                await ctx.send("❌ Invalid color. Use 3- or 6-digit hex like `#F80` or `#FF8800`.")
                return
            try:
                color_val = int(c, 16)
                role_color = discord.Color(value=color_val)
            except Exception:
                await ctx.send("❌ Invalid color. Use hex like `#RRGGBB` or `RRGGBB`.")
                return

        try:
            guild = ctx.guild
            if not guild:
                await ctx.send("❌ This command must be run in a server.")
                return
            role = await guild.create_role(
                name=role_name,
                color=role_color or discord.Color.default(),
                mentionable=False,
                reason=f"Created by {ctx.author}"
            )
            embed = discord.Embed(title="✅ Role Created", description=f"Created role {role.mention}", color=discord.Color.green())
            embed.add_field(name="Name", value=role.name, inline=True)
            embed.add_field(name="ID", value=str(role.id), inline=True)
            if c:
                embed.add_field(name="Color", value=f"#{c.upper()}", inline=True)
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to create roles.")
        except Exception as e:
            await ctx.send(f"❌ Failed to create role: {e}")

    @tuna.command(name="colour")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_colour(self, ctx, hex_color: str):
        """Show a small image filled with the given hex colour. (admins only)"""
        # authorization
        is_admin = getattr(ctx.author.guild_permissions, "administrator", False)
        if ctx.author.id != ALLOWED_TUNA_USER_ID and not is_admin:
            await ctx.send("❌ You are not allowed to use tuna commands.")
            return

        c = hex_color.strip().lstrip("#")
        if len(c) not in (3, 6):
            await ctx.send("❌ Invalid color. Provide 3- or 6-digit hex, e.g. `FF8800` or `F80`.")
            return
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        try:
            value = int(c, 16)
        except ValueError:
            await ctx.send("❌ Invalid hex value.")
            return

        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF

        # Check attach permission
        try:
            me = ctx.guild.me if ctx.guild else None
            if me and not ctx.channel.permissions_for(me).attach_files:
                await ctx.send("❌ I don't have permission to attach files in this channel. Showing fallback embed instead.")
                embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
                embed.description = f"RGB: {r}, {g}, {b}"
                await ctx.send(embed=embed)
                return
        except Exception:
            # ignore permission checks failure, continue

            pass

        # If Pillow available, send an image attachment; otherwise fallback to embed color bar
        if Image is None:
            # Pillow not installed
            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.description = f"RGB: {r}, {g}, {b}\n\n(Pillow not installed — install with `pip install Pillow` to get an image attachment.)"
            await ctx.send(embed=embed)
            return

        # Create image and attempt to send as attachment (with safe error handling)
        try:
            img = Image.new("RGB", (256, 256), (r, g, b))
            bio = BytesIO()
            img.save(bio, "PNG")
            bio.seek(0)
            file = discord.File(bio, filename="colour.png")

            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.set_image(url="attachment://colour.png")
            embed.add_field(name="RGB", value=f"{r}, {g}, {b}", inline=True)

            await ctx.send(embed=embed, file=file)
        except Exception as e:
            # fallback: send embed and show error in channel so you can debug
            await ctx.send(f"❌ Failed to send image attachment: {e}")
            embed = discord.Embed(title=f"Colour: #{c.upper()}", color=discord.Color(value))
            embed.description = f"RGB: {r}, {g}, {b}"
            await ctx.send(embed=embed)

    @tuna.command(name="emojis")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_emojis(self, ctx):
        """Create a zip of all custom emojis in this guild and send it."""
        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be used in a server.")
            return

        emojis = guild.emojis
        if not emojis:
            await ctx.send("No custom emojis in this server.")
            return

        msg = await ctx.send("Creating emoji zip — this may take a moment...")
        bio = BytesIO()
        try:
            with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                async with aiohttp.ClientSession() as session:
                    used_filenames = set()
                    for e in emojis:
                        url = str(e.url)
                        ext = "gif" if getattr(e, "animated", False) else "png"
                        # Sanitize the emoji name to produce a safe filename
                        base_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', (e.name or '').strip())
                        if not base_name:
                            base_name = f"emoji_{e.id}"

                        filename = f"{base_name}.{ext}"
                        # If filename already used (duplicate emoji names), add numeric suffix
                        if filename in used_filenames:
                            idx = 1
                            while True:
                                candidate = f"{base_name}_{idx}.{ext}"
                                if candidate not in used_filenames:
                                    filename = candidate
                                    break
                                idx += 1

                        used_filenames.add(filename)

                        try:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    zf.writestr(filename, data)
                        except Exception:
                            # skip emoji on error
                            continue
            bio.seek(0)
            file = discord.File(bio, filename=f"{guild.name}_emojis.zip")
            await msg.edit(content="Here is the emoji zip:")
            await ctx.send(file=file)
        except Exception as exc:
            await msg.edit(content="Failed to create emoji zip.")
            await ctx.send(f"Error: {exc}")

    @tuna.command(name="timestamp")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_timestamp(self, ctx, *, datetime_input: str):
        """Create a Discord timestamp. (admins only)
        Usage: !tuna timestamp <date/time> [format]
        
        Formats:
        - t: Short time (9:41 AM)
        - T: Long time (9:41:30 AM)
        - d: Short date (06/20/2021)
        - D: Long date (June 20, 2021)
        - f: Short date/time (June 20, 2021 9:41 AM) [default]
        - F: Long date/time (Monday, June 20, 2021 9:41 AM)
        - R: Relative time (in 2 hours, 3 days ago)
        
        Examples:
        - !tuna timestamp 2024-12-25 15:30
        - !tuna timestamp Dec 25 2024 3:30 PM
        - !tuna timestamp 2024-12-25 15:30 R
        - !tuna timestamp tomorrow 3pm F
        """
        # Parse format if provided (last character if it's a single letter)
        format_char = 'f'  # default
        datetime_str = datetime_input.strip()
        
        # Check if last word is a format character
        parts = datetime_str.split()
        if len(parts) > 1 and len(parts[-1]) == 1 and parts[-1].upper() in ['T', 'D', 'F', 'R']:
            format_char = parts[-1].upper()
            datetime_str = ' '.join(parts[:-1])
        elif len(parts) > 1 and parts[-1].lower() in ['t', 'd', 'f', 'r']:
            format_char = parts[-1].lower()
            datetime_str = ' '.join(parts[:-1])
        
        # Try to parse the datetime
        parsed_dt = None
        
        # Try common formats
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%B %d, %Y %H:%M:%S",
            "%B %d, %Y %H:%M",
            "%b %d, %Y %H:%M:%S",
            "%b %d, %Y %H:%M",
            "%d %B %Y %H:%M:%S",
            "%d %B %Y %H:%M",
            "%d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        
        for fmt in formats_to_try:
            try:
                parsed_dt = datetime.strptime(datetime_str, fmt)
                # Assume local timezone if not specified
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        
        # Try relative time parsing (e.g., "tomorrow", "in 2 hours", "next week")
        if parsed_dt is None:
            now = datetime.now(timezone.utc)
            lower_input = datetime_str.lower()
            
            # Handle "tomorrow", "today", etc.
            if "tomorrow" in lower_input:
                parsed_dt = now + timedelta(days=1)
                # Try to extract time
                time_match = re.search(r'(\d{1,2})\s*(am|pm|:?\d{0,2})', lower_input, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    if "pm" in lower_input and hour < 12:
                        hour += 12
                    elif "am" in lower_input and hour == 12:
                        hour = 0
                    parsed_dt = parsed_dt.replace(hour=hour, minute=0, second=0)
            elif "today" in lower_input:
                parsed_dt = now
                time_match = re.search(r'(\d{1,2})\s*(am|pm|:?\d{0,2})', lower_input, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    if "pm" in lower_input and hour < 12:
                        hour += 12
                    elif "am" in lower_input and hour == 12:
                        hour = 0
                    parsed_dt = parsed_dt.replace(hour=hour, minute=0, second=0)
            elif "in" in lower_input:
                # Parse relative time like "in 2 hours", "in 3 days"
                delta = timedelta()
                hour_match = re.search(r'(\d+)\s*hour', lower_input)
                day_match = re.search(r'(\d+)\s*day', lower_input)
                minute_match = re.search(r'(\d+)\s*minute', lower_input)
                week_match = re.search(r'(\d+)\s*week', lower_input)
                
                if hour_match:
                    delta += timedelta(hours=int(hour_match.group(1)))
                if day_match:
                    delta += timedelta(days=int(day_match.group(1)))
                if minute_match:
                    delta += timedelta(minutes=int(minute_match.group(1)))
                if week_match:
                    delta += timedelta(weeks=int(week_match.group(1)))
                
                if delta.total_seconds() > 0:
                    parsed_dt = now + delta
        
        if parsed_dt is None:
            await ctx.send(
                f"❌ Could not parse date/time: `{datetime_input}`\n\n"
                "Try formats like:\n"
                "• `2024-12-25 15:30`\n"
                "• `Dec 25 2024 3:30 PM`\n"
                "• `tomorrow 3pm`\n"
                "• `in 2 hours`\n\n"
                "Add format at end: `t`, `T`, `d`, `D`, `f`, `F`, or `R`"
            )
            return
        
        # Convert to Unix timestamp
        timestamp = int(parsed_dt.timestamp())
        
        # Generate Discord timestamp code
        timestamp_code = f"<t:{timestamp}:{format_char}>"
        
        # Create embed with preview
        embed = discord.Embed(
            title="🕐 Discord Timestamp",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Code",
            value=f"`{timestamp_code}`",
            inline=False
        )
        embed.add_field(
            name="Preview",
            value=timestamp_code,
            inline=False
        )
        embed.add_field(
            name="Format",
            value=format_char.upper(),
            inline=True
        )
        embed.add_field(
            name="Unix Timestamp",
            value=str(timestamp),
            inline=True
        )
        embed.add_field(
            name="Parsed Date/Time",
            value=parsed_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @tuna.command(name="timestamp_short")
    @commands.has_guild_permissions(administrator=True)
    async def tuna_timestamp_short(self, ctx, *, datetime_input: str):
        """Create a Discord timestamp with short time format. (admins only)
        Usage: !tuna timestamp_short <date/time>
        
        Creates a short time format (9:41 AM) timestamp.
        
        Examples:
        - !tuna timestamp_short 2024-12-25 15:30
        - !tuna timestamp_short Dec 25 2024 3:30 PM
        - !tuna timestamp_short tomorrow 3pm
        - !tuna timestamp_short in 2 hours
        """
        # Parse format - always use 't' for short time
        format_char = 't'
        datetime_str = datetime_input.strip()
        
        # Try to parse the datetime
        parsed_dt = None
        
        # Try common formats
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%B %d, %Y %H:%M:%S",
            "%B %d, %Y %H:%M",
            "%b %d, %Y %H:%M:%S",
            "%b %d, %Y %H:%M",
            "%d %B %Y %H:%M:%S",
            "%d %B %Y %H:%M",
            "%d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        
        for fmt in formats_to_try:
            try:
                parsed_dt = datetime.strptime(datetime_str, fmt)
                # Assume local timezone if not specified
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        
        # Try relative time parsing (e.g., "tomorrow", "in 2 hours", "next week")
        if parsed_dt is None:
            now = datetime.now(timezone.utc)
            lower_input = datetime_str.lower()
            
            # Handle "tomorrow", "today", etc.
            if "tomorrow" in lower_input:
                parsed_dt = now + timedelta(days=1)
                # Try to extract time
                time_match = re.search(r'(\d{1,2})\s*(am|pm|:?\d{0,2})', lower_input, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    if "pm" in lower_input and hour < 12:
                        hour += 12
                    elif "am" in lower_input and hour == 12:
                        hour = 0
                    parsed_dt = parsed_dt.replace(hour=hour, minute=0, second=0)
            elif "today" in lower_input:
                parsed_dt = now
                time_match = re.search(r'(\d{1,2})\s*(am|pm|:?\d{0,2})', lower_input, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    if "pm" in lower_input and hour < 12:
                        hour += 12
                    elif "am" in lower_input and hour == 12:
                        hour = 0
                    parsed_dt = parsed_dt.replace(hour=hour, minute=0, second=0)
            elif "in" in lower_input:
                # Parse relative time like "in 2 hours", "in 3 days"
                delta = timedelta()
                hour_match = re.search(r'(\d+)\s*hour', lower_input)
                day_match = re.search(r'(\d+)\s*day', lower_input)
                minute_match = re.search(r'(\d+)\s*minute', lower_input)
                week_match = re.search(r'(\d+)\s*week', lower_input)
                
                if hour_match:
                    delta += timedelta(hours=int(hour_match.group(1)))
                if day_match:
                    delta += timedelta(days=int(day_match.group(1)))
                if minute_match:
                    delta += timedelta(minutes=int(minute_match.group(1)))
                if week_match:
                    delta += timedelta(weeks=int(week_match.group(1)))
                
                if delta.total_seconds() > 0:
                    parsed_dt = now + delta
        
        if parsed_dt is None:
            await ctx.send(
                f"❌ Could not parse date/time: `{datetime_input}`\n\n"
                "Try formats like:\n"
                "• `2024-12-25 15:30`\n"
                "• `Dec 25 2024 3:30 PM`\n"
                "• `tomorrow 3pm`\n"
                "• `in 2 hours`"
            )
            return
        
        # Convert to Unix timestamp
        timestamp = int(parsed_dt.timestamp())
        
        # Generate Discord timestamp code with short time format
        timestamp_code = f"<t:{timestamp}:{format_char}>"
        
        # Create embed with preview
        embed = discord.Embed(
            title="🕐 Discord Timestamp (Short Time)",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Code",
            value=f"`{timestamp_code}`",
            inline=False
        )
        embed.add_field(
            name="Preview",
            value=timestamp_code,
            inline=False
        )
        embed.add_field(
            name="Format",
            value="Short Time (t)",
            inline=True
        )
        embed.add_field(
            name="Unix Timestamp",
            value=str(timestamp),
            inline=True
        )
        embed.add_field(
            name="Parsed Date/Time",
            value=parsed_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
