from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import time

# User allowed to run !tuna (in addition to server admins)
ALLOWED_TUNA_USER_ID = 735167992966676530

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
    async def tuna(self, ctx):
        """Tuna utility commands."""
        # Authorization gate: allow specified user or server admins
        is_admin = getattr(ctx.author.guild_permissions, "administrator", False)
        if ctx.author.id != ALLOWED_TUNA_USER_ID and not is_admin:
            await ctx.send("❌ You are not allowed to use tuna commands.")
            return
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna role` or `!tuna dm` for available commands.")

    @tuna.group(name="role")
    async def tuna_role(self, ctx):
        """Role management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!tuna role add`, `!tuna role list`, or `!tuna role remove`")

    @tuna_role.command(name="add")
    async def tuna_role_add(self, ctx, user: discord.Member, *, role_name: str):
        """Add a role to a user."""
        try:
            # Find the role by name (case insensitive)
            role = discord.utils.get(ctx.guild.roles, name=role_name)
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
    async def tuna_role_list(self, ctx, user: discord.Member):
        """List all roles for a user."""
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
    async def tuna_role_remove(self, ctx, user: discord.Member, *, role_name: str):
        """Remove a role from a user."""
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
    async def tuna_role_members(self, ctx, *, role_name: str):
        """List members who have a given role (by name or mention)."""
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
    async def tuna_dm(self, ctx, target, *, message: str):
        """Send a DM to a user or all members with a specific role."""
        try:
            # Try to parse as user mention/ID first
            try:
                if target.startswith('<@') and target.endswith('>'):
                    # User mention
                    user_id = int(target[2:-1].replace('!', ''))
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"**Message from {ctx.guild.name}:**\n{message}")
                    await ctx.send(f"✅ DM sent to {user.mention}")
                    return
                else:
                    # Try as user ID
                    user_id = int(target)
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"**Message from {ctx.guild.name}:**\n{message}")
                    await ctx.send(f"✅ DM sent to {user.mention}")
                    return
            except (ValueError, discord.NotFound):
                pass
            
            # Try to find role by name
            role = discord.utils.get(ctx.guild.roles, name=target)
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
    async def tuna_say(self, ctx, channel: discord.TextChannel = None, *, message: str = None):
        """Send a message to a channel. Usage: !tuna say [#channel] <message>"""
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

async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
