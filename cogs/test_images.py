import discord
from discord.ext import commands
from discord import app_commands
import os

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

class TestImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="test-images", description="Test different image embedding methods")
    async def test_images(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        results = []
        
        # Test 1: Local file attachment with attachment:// URL
        try:
            embed1 = discord.Embed(title="Test 1: Local File Attachment", description="Using discord.File + attachment:// URL", color=0x00ff00)
            embed1.set_image(url="attachment://bottom.png")
            file1 = discord.File(os.path.join(IMAGES_DIR, "bottom.png"), filename="bottom.png")
            await interaction.channel.send(embed=embed1, file=file1)
            results.append("✅ Test 1 (Local file): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 1 (Local file): {e}")

        # Test 2: CDN URL with signed params
        try:
            embed2 = discord.Embed(title="Test 2: CDN URL (signed)", description="Using Discord CDN URL with ex/is/hm params", color=0xffff00)
            embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68e8e4dc&is=68e7935c&hm=87d1062f2383b32fc32cdc397b1021296f29aa8caf549b38d3b7137ea8281262&")
            await interaction.channel.send(embed=embed2)
            results.append("✅ Test 2 (CDN signed): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 2 (CDN signed): {e}")

        # Test 3: CDN URL without signed params
        try:
            embed3 = discord.Embed(title="Test 3: CDN URL (unsigned)", description="Using Discord CDN URL without params", color=0xff0000)
            embed3.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png")
            await interaction.channel.send(embed=embed3)
            results.append("✅ Test 3 (CDN unsigned): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 3 (CDN unsigned): {e}")

        # Test 4: Image-only embed (no title/description) with local file
        try:
            embed4 = discord.Embed(color=0x0000ff)
            embed4.set_image(url="attachment://logo.png")
            file4 = discord.File(os.path.join(IMAGES_DIR, "logo.png"), filename="logo.png")
            await interaction.channel.send(embed=embed4, file=file4)
            results.append("✅ Test 4 (Image-only embed): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 4 (Image-only embed): {e}")

        # Test 5: Image-only embed with zero-width space
        try:
            embed5 = discord.Embed(color=0xff00ff, description="\u200b")
            embed5.set_image(url="attachment://ASSISTANCE.png")
            file5 = discord.File(os.path.join(IMAGES_DIR, "ASSISTANCE.png"), filename="ASSISTANCE.png")
            await interaction.channel.send(embed=embed5, file=file5)
            results.append("✅ Test 5 (Image + zero-width space): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 5 (Image + zero-width space): {e}")

        # Test 6: Multiple embeds with multiple files
        try:
            embed6a = discord.Embed(title="Test 6a", description="First embed", color=0x00ffff)
            embed6a.set_image(url="attachment://PASS.png")
            embed6b = discord.Embed(title="Test 6b", description="Second embed", color=0x00ffff)
            embed6b.set_image(url="attachment://FAIL.png")
            file6a = discord.File(os.path.join(IMAGES_DIR, "PASS.png"), filename="PASS.png")
            file6b = discord.File(os.path.join(IMAGES_DIR, "FAIL.png"), filename="FAIL.png")
            await interaction.channel.send(embeds=[embed6a, embed6b], files=[file6a, file6b])
            results.append("✅ Test 6 (Multiple embeds+files): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 6 (Multiple embeds+files): {e}")

        # Test 7: External URL (imgur or similar)
        try:
            embed7 = discord.Embed(title="Test 7: External URL", description="Using external image host", color=0xffa500)
            embed7.set_image(url="https://i.imgur.com/ExdKOOz.png")
            await interaction.channel.send(embed=embed7)
            results.append("✅ Test 7 (External URL): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 7 (External URL): {e}")

        # Test 8: Just send an image file without embed
        try:
            file8 = discord.File(os.path.join(IMAGES_DIR, "logo.png"), filename="test_logo.png")
            await interaction.channel.send(content="Test 8: Direct file upload (no embed)", file=file8)
            results.append("✅ Test 8 (Direct file): Sent successfully")
        except Exception as e:
            results.append(f"❌ Test 8 (Direct file): {e}")

        # Send summary
        summary = "\n".join(results)
        summary += "\n\n**Note:** 'Sent successfully' means no error occurred. Check above messages to see if images actually rendered."
        await interaction.followup.send(f"**Image Test Results:**\n{summary}", ephemeral=True)

    @app_commands.command(name="test-image-simple", description="Simple image test")
    async def test_image_simple(self, interaction: discord.Interaction):
        """Simplest possible image test"""
        try:
            file = discord.File(os.path.join(IMAGES_DIR, "bottom.png"), filename="test.png")
            embed = discord.Embed(title="Simple Test", description="If you see an image below, it works!", color=0x00ff00)
            embed.set_image(url="attachment://test.png")
            await interaction.response.send_message(embed=embed, file=file)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TestImages(bot))
