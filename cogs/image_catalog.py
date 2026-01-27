import discord
from discord.ext import commands
import json
from pathlib import Path

OWNER_ID = 840949634071658507
CATALOG_SERVER_ID = 1124324366495260753
CATALOG_CHANNEL_ID = 1465844086480310342
IMAGES_DIR = Path(__file__).parent / "images"


class ImageCatalog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="catalogimages")
    async def catalogimages(self, ctx):
        """Upload uncatalogued images to Discord and store URLs in discord_urls.json"""
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return

        # Get catalog server and channel
        catalog_server = self.bot.get_guild(CATALOG_SERVER_ID)
        if not catalog_server:
            await ctx.send(f"Catalog server {CATALOG_SERVER_ID} not found.")
            return

        catalog_channel = catalog_server.get_channel(CATALOG_CHANNEL_ID)
        if not catalog_channel:
            await ctx.send(f"Catalog channel {CATALOG_CHANNEL_ID} not found in server.")
            return

        # Load existing discord URLs
        discord_urls_file = IMAGES_DIR / "discord_urls.json"
        if discord_urls_file.exists():
            try:
                with open(discord_urls_file, 'r') as f:
                    discord_urls = json.load(f)
            except:
                discord_urls = {}
        else:
            discord_urls = {}

        # Get all image files
        if not IMAGES_DIR.exists():
            await ctx.send(f"Images directory not found at {IMAGES_DIR}")
            return

        image_files = sorted([f for f in IMAGES_DIR.iterdir() if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']])
        
        # Find images not yet catalogued
        uncatalogued = [f for f in image_files if f.name not in discord_urls]
        
        if not uncatalogued:
            await ctx.send(f"All {len(image_files)} images are already catalogued!")
            return

        # Upload uncatalogued images
        status = await ctx.send(f"📤 Uploading {len(uncatalogued)} new images to catalog...")
        
        for img_file in uncatalogued:
            try:
                # Upload to Discord
                msg = await catalog_channel.send(file=discord.File(img_file))
                # Store the attachment URL
                if msg.attachments:
                    discord_urls[img_file.name] = msg.attachments[0].url
                    print(f"✅ Catalogued: {img_file.name}")
            except Exception as e:
                print(f"❌ Failed to upload {img_file.name}: {e}")

        # Save updated URLs
        try:
            with open(discord_urls_file, 'w') as f:
                json.dump(discord_urls, f, indent=2)
        except Exception as e:
            await ctx.send(f"Failed to save discord_urls.json: {e}")
            return

        await status.edit(content=f"✅ Successfully uploaded {len(uncatalogued)} images! All URLs saved to discord_urls.json")


async def setup(bot: commands.Bot):
    await bot.add_cog(ImageCatalog(bot))
