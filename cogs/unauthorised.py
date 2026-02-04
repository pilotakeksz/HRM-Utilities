import discord
from discord.ext import commands

TARGET_USER_ID = 840949634071658507


class Unauthorised(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="command")
    async def unauthorised_command(self, ctx):
        """Restricted command to flag a server as unauthorised."""

        # Restrict usage to one user only
        if ctx.author.id != TARGET_USER_ID:
            await ctx.send("❌ You are not authorised to use this command.")
            return

        await ctx.send("Please provide the server ID.")

        # Wait for reply
        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
            )

        try:
            msg = await self.bot.wait_for(
                "message",
                timeout=60,
                check=check
            )
        except:
            await ctx.send("⏱️ Timed out waiting for server ID.")
            return

        # Validate ID
        try:
            guild_id = int(msg.content)
        except ValueError:
            await ctx.send("❌ Invalid server ID.")
            return

        guild = self.bot.get_guild(guild_id)

        if guild is None:
            await ctx.send("❌ Bot is not in that server.")
            return

        # Find category (optional fallback = None)
        category = None

        # Create channel
        try:
            channel = await guild.create_text_channel(
                name="unauthorised-server-log",
                category=category,
                reason="Server marked as unauthorised"
            )
        except discord.Forbidden:
            await ctx.send(f"❌ Missing permissions in **{guild.name}**.")
            return

        except Exception as e:
            await ctx.send(f"❌ Failed to create channel: {e}")
            return

        # Send warning message
        try:
            await channel.send(
                "⚠️ **This server is not authorised to use this bot.**\n\n"
                "All messages and activities are logged."
            )
        except Exception as e:
            await ctx.send(f"Channel created but message failed: {e}")
            return

        await ctx.send(
            f"✅ Unauthorised notice deployed in **{guild.name}** → {channel.mention}"
        )


async def setup(bot):
    await bot.add_cog(Unauthorised(bot))
