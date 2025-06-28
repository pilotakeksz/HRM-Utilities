import discord
from discord.ext import commands
from discord import app_commands

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_messages = {}  # user_id: (message, timestamp)

    @commands.command(name="afk")
    async def afk_command(self, ctx, *, text: str = "AFK"):
        """Set your AFK message."""
        self.afk_messages[ctx.author.id] = (text, discord.utils.utcnow())
        embed = discord.Embed(
            title="AFK Set",
            description=f"Your AFK message is now:\n> {text}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="afk", description="Set your AFK message.")
    @app_commands.describe(text="Your AFK message")
    async def afk_slash(self, interaction: discord.Interaction, text: str = "AFK"):
        self.afk_messages[interaction.user.id] = (text, discord.utils.utcnow())
        embed = discord.Embed(
            title="AFK Set",
            description=f"Your AFK message is now:\n> {text}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # If someone is mentioned and is AFK, respond with their AFK message
        mentioned_ids = {user.id for user in message.mentions}
        for user_id in mentioned_ids:
            if user_id in self.afk_messages:
                afk_text, timestamp = self.afk_messages[user_id]
                embed = discord.Embed(
                    title="AFK Notice",
                    description=f"That user is currently AFK:\n> {afk_text}",
                    color=discord.Color.blue()
                )
                await message.channel.send(embed=embed)
        # If the author is AFK and sends a message, remove their AFK
        if message.author.id in self.afk_messages:
            del self.afk_messages[message.author.id]
            embed = discord.Embed(
                title="Welcome Back!",
                description="Your AFK status has been removed.",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AFK(bot))