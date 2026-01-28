#!/usr/bin/env python3
"""
Image Upload Cog - Uploads images to Discord and stores their CDN URLs
This allows embeds to use Discord's CDN URLs instead of private network IPs

Usage:
    !upload_image <image_filename>  - Upload image from cogs/images/ to Discord
    !upload_all_images             - Upload all images at once
    !image_urls                    - Show all registered Discord URLs
    !get_image_url <image_name>    - Get the Discord URL for an image
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
import os

class ImageUpload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.images_dir = Path(__file__).parent / "images"
        self.discord_urls_file = self.images_dir / "discord_urls.json"
        self.images_dir.mkdir(exist_ok=True)
    
    def load_discord_urls(self):
        """Load Discord URLs from file"""
        if self.discord_urls_file.exists():
            try:
                with open(self.discord_urls_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_discord_urls(self, urls):
        """Save Discord URLs to file"""
        with open(self.discord_urls_file, 'w') as f:
            json.dump(urls, f, indent=2)
    
    def get_image_path(self, filename):
        """Get full path to image file"""
        path = self.images_dir / filename
        if not path.exists():
            return None
        return path
    
    @commands.command(name="upload_image")
    @commands.is_owner()
    async def upload_image(self, ctx, filename: str):
        """Upload a single image to Discord and store its CDN URL"""
        image_path = self.get_image_path(filename)
        
        if not image_path:
            await ctx.send(f"❌ Image not found: {filename}")
            return
        
        try:
            # Send image to Discord and get URL
            with open(image_path, 'rb') as f:
                file = discord.File(f, filename=filename)
                msg = await ctx.send(file=file)
            
            # Extract the attachment URL
            if msg.attachments:
                discord_url = msg.attachments[0].url
                
                # Save to registry
                urls = self.load_discord_urls()
                urls[filename] = discord_url
                self.save_discord_urls(urls)
                
                # Delete the message (we don't need it anymore)
                await msg.delete()
                
                await ctx.send(f"✅ Uploaded: {filename}\n```{discord_url}```")
            else:
                await ctx.send(f"❌ Failed to upload {filename}")
        
        except Exception as e:
            await ctx.send(f"❌ Error uploading {filename}: {e}")
    
    @commands.command(name="upload_all_images")
    @commands.is_owner()
    async def upload_all_images(self, ctx):
        """Upload all images from cogs/images/ to Discord"""
        if not self.images_dir.exists():
            await ctx.send("❌ Images directory not found")
            return
        
        # Get all image files
        image_files = [f for f in self.images_dir.iterdir() 
                      if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']]
        
        if not image_files:
            await ctx.send("❌ No images found in cogs/images/")
            return
        
        await ctx.send(f"📤 Uploading {len(image_files)} images...")
        
        urls = self.load_discord_urls()
        success_count = 0
        
        for image_path in image_files:
            try:
                with open(image_path, 'rb') as f:
                    file = discord.File(f, filename=image_path.name)
                    msg = await ctx.send(file=file)
                
                if msg.attachments:
                    discord_url = msg.attachments[0].url
                    urls[image_path.name] = discord_url
                    await msg.delete()
                    success_count += 1
                    await ctx.send(f"✅ {image_path.name}")
            
            except Exception as e:
                await ctx.send(f"❌ {image_path.name}: {e}")
        
        self.save_discord_urls(urls)
        await ctx.send(f"\n✅ Successfully uploaded {success_count}/{len(image_files)} images!")
    
    @commands.command(name="image_urls")
    @commands.is_owner()
    async def image_urls(self, ctx):
        """Show all registered Discord URLs"""
        urls = self.load_discord_urls()
        
        if not urls:
            await ctx.send("❌ No Discord URLs registered yet.\nUse `!upload_all_images` to upload images.")
            return
        
        embed = discord.Embed(
            title="📷 Registered Discord Image URLs",
            color=discord.Color.blue(),
            description="Use these URLs in embeds to display images"
        )
        
        for filename, url in sorted(urls.items()):
            # Truncate URL for display
            short_url = url[:70] + "..." if len(url) > 70 else url
            embed.add_field(name=filename, value=f"```{short_url}```", inline=False)
        
        embed.set_footer(text=f"Total: {len(urls)} images")
        await ctx.send(embed=embed)
    
    @commands.command(name="get_image_url")
    async def get_image_url(self, ctx, image_name: str):
        """Get the Discord URL for an image
        
        Usage: !get_image_url bottom_banner.png
        """
        urls = self.load_discord_urls()
        
        if image_name in urls:
            url = urls[image_name]
            await ctx.send(f"🖼️ **{image_name}**\n```{url}```")
        else:
            await ctx.send(f"❌ No Discord URL found for: {image_name}\n"
                         f"Upload it with: `!upload_image {image_name}`")
    
    @app_commands.command(name="image_url", description="Get Discord URL for an image")
    async def slash_get_image_url(self, interaction: discord.Interaction, image_name: str):
        """Slash command version of get_image_url"""
        urls = self.load_discord_urls()
        
        if image_name in urls:
            url = urls[image_name]
            embed = discord.Embed(
                title=f"🖼️ {image_name}",
                description=f"```{url}```",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ No Discord URL found for: {image_name}",
                ephemeral=True
            )

# Image URL helper function for use in other cogs
def get_discord_image_url(image_filename):
    """
    Get the Discord CDN URL for an image
    
    Usage in other cogs:
        from cogs.image_upload import get_discord_image_url
        url = get_discord_image_url('bottom_banner.png')
        embed.set_image(url=url)
    """
    images_dir = Path(__file__).parent / "images"
    discord_urls_file = images_dir / "discord_urls.json"
    
    if discord_urls_file.exists():
        try:
            with open(discord_urls_file, 'r') as f:
                urls = json.load(f)
                if image_filename in urls:
                    return urls[image_filename]
        except:
            pass
    
    # Return None if not found - cog should handle gracefully
    return None

async def setup(bot):
    """Setup the cog"""
    await bot.add_cog(ImageUpload(bot))
