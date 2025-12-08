import discord
from discord.ext import commands
import os
import json
from typing import Optional

# Configuration file path
BIRTHDAY_CONFIG_FILE = os.path.join("data", "birthday_config.json")

# Default GIF URL (from the Tenor link provided)
# This should be a direct image/GIF URL that Discord can display in embeds
# You can get the direct URL by right-clicking the GIF on Tenor and selecting "Copy image address"
# Or use a service like tenor.com's API to get the direct URL
DEFAULT_GIF_URL = "https://media.tenor.com/17432195706192679199/tenor.gif"

class HappyBirthday(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        """Load configuration from JSON file."""
        default_config = {
            "target_user_id": None,  # Set this to the user ID who should receive the DM
            "gif_url": DEFAULT_GIF_URL,
            "enabled": True
        }
        
        if os.path.exists(BIRTHDAY_CONFIG_FILE):
            try:
                with open(BIRTHDAY_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    default_config.update(config)
                    return default_config
            except Exception as e:
                print(f"Error loading birthday config: {e}")
                return default_config
        else:
            # Create default config file
            os.makedirs("data", exist_ok=True)
            try:
                with open(BIRTHDAY_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
            except Exception as e:
                print(f"Error creating birthday config: {e}")
            return default_config
    
    def save_config(self):
        """Save configuration to JSON file."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(BIRTHDAY_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving birthday config: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Send birthday DM whenever someone sends a message."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if feature is enabled
        if not self.config.get("enabled", True):
            return
        
        # Check if target user ID is configured
        target_user_id = self.config.get("target_user_id")
        if not target_user_id:
            return
        
        try:
            # Fetch the target user
            target_user = await self.bot.fetch_user(target_user_id)
            
            # Create embed with GIF and message
            embed = discord.Embed(
                title="🎉 HAPPY BIRTHDAY ALARM TRIGGERED 🎉",
                color=discord.Color.gold()
            )
            embed.set_image(url=self.config.get("gif_url", DEFAULT_GIF_URL))
            embed.set_footer(text="This message was triggered by a message in the server")
            
            # Send DM
            await target_user.send(embed=embed)
        except discord.NotFound:
            print(f"Target user ID {target_user_id} not found")
        except discord.Forbidden:
            print(f"Cannot send DM to user ID {target_user_id} (DMs disabled or blocked)")
        except Exception as e:
            print(f"Error sending birthday DM: {e}")
    
    @discord.app_commands.command(name="birthday-set-user", description="Set the user ID to receive birthday DMs (admin only)")
    @discord.app_commands.describe(user_id="The Discord user ID to send birthday DMs to")
    async def birthday_set_user(self, interaction: discord.Interaction, user_id: str):
        """Set the target user ID for birthday DMs."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        try:
            user_id_int = int(user_id)
            self.config["target_user_id"] = user_id_int
            self.save_config()
            
            # Try to fetch the user to verify it's valid
            try:
                user = await self.bot.fetch_user(user_id_int)
                await interaction.response.send_message(
                    f"✅ Birthday target user set to: {user.mention} ({user_id_int})",
                    ephemeral=True
                )
            except discord.NotFound:
                await interaction.response.send_message(
                    f"⚠️ User ID {user_id_int} set, but user not found. Make sure the ID is correct.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please provide a valid numeric user ID.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
    
    @discord.app_commands.command(name="birthday-toggle", description="Enable or disable birthday DMs (admin only)")
    async def birthday_toggle(self, interaction: discord.Interaction):
        """Toggle birthday DMs on/off."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        self.config["enabled"] = not self.config.get("enabled", True)
        self.save_config()
        
        status = "enabled" if self.config["enabled"] else "disabled"
        await interaction.response.send_message(
            f"✅ Birthday DMs are now **{status}**.",
            ephemeral=True
        )
    
    @discord.app_commands.command(name="birthday-set-gif", description="Set the GIF URL for birthday DMs (admin only)")
    @discord.app_commands.describe(gif_url="The direct URL to the GIF/image to send")
    async def birthday_set_gif(self, interaction: discord.Interaction, gif_url: str):
        """Set the GIF URL for birthday DMs."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        self.config["gif_url"] = gif_url
        self.save_config()
        
        await interaction.response.send_message(
            f"✅ Birthday GIF URL updated!\n**Note:** Make sure this is a direct image/GIF URL that Discord can display in embeds.",
            ephemeral=True
        )
    
    @discord.app_commands.command(name="birthday-status", description="Check birthday DM configuration (admin only)")
    async def birthday_status(self, interaction: discord.Interaction):
        """Show current birthday DM configuration."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        target_user_id = self.config.get("target_user_id")
        enabled = self.config.get("enabled", True)
        
        embed = discord.Embed(
            title="🎉 Birthday DM Configuration",
            color=discord.Color.gold()
        )
        
        if target_user_id:
            try:
                user = await self.bot.fetch_user(target_user_id)
                embed.add_field(name="Target User", value=f"{user.mention} ({target_user_id})", inline=False)
            except discord.NotFound:
                embed.add_field(name="Target User", value=f"User ID: {target_user_id} (not found)", inline=False)
        else:
            embed.add_field(name="Target User", value="Not set", inline=False)
        
        embed.add_field(name="Status", value="✅ Enabled" if enabled else "❌ Disabled", inline=False)
        gif_url = self.config.get("gif_url", DEFAULT_GIF_URL)
        embed.add_field(name="GIF URL", value=gif_url[:100] + ("..." if len(gif_url) > 100 else ""), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HappyBirthday(bot))

