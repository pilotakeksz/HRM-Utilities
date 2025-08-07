import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1329908357812981882  # Replace with your test server ID
ALLOWED_USER_IDS = [840949634071658507]  # Replace with your Discord user ID(s)

class TokenEditor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="e", description="Update .env with a new DISCORD_BOT_TOKEN line.")
    async def edit_token(self, interaction: discord.Interaction, line: str):
        if interaction.user.id not in ALLOWED_USER_IDS:
            await interaction.response.send_message("❌ You're not authorized to use this command.", ephemeral=True)
            return

        with open(".env", "w") as f:
            f.write(line.strip() + "\n")

        await interaction.response.send_message("✅ `.env` updated. Please restart the bot.", ephemeral=True)

    async def cog_load(self):
        # Use GUILD sync for instant command registration
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.edit_token, guild=guild)
        await self.bot.tree.sync(guild=guild)

async def setup(bot):
    await bot.add_cog(TokenEditor(bot))
