import discord
from discord.ext import commands
import os

EMBED_COLOR = 0xd0b47b
FOOTER_TEXT = "High Rock Military Corps."
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"

VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID"))

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="send-verification", description="Send the verification embed (admin only)")
    async def send_verification(self, ctx: commands.Context):
        # Replace with your admin ID(s) or better permission checking
        if ctx.author.id != 840949634071658507:
            await ctx.reply("You do not have permission to run this command.", ephemeral=True)
            return

        channel = self.bot.get_channel(VERIFICATION_CHANNEL_ID)
        if channel is None:
            await ctx.reply("Verification channel not found.", ephemeral=True)
            return

        embed1 = discord.Embed(color=EMBED_COLOR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376934088841236620/verification.png")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> HRMC Verification",
            description=(
                "Here at *High Rock Military Corps*, we__ ensure the safety of our community members__ "
                "by enforcing strict discord verification, you must verify to gain access to the rest "
                "of our server and to be able to apply."
            ),
            color=EMBED_COLOR
        )
        embed2.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376934109665824828/bottom.png")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        await channel.send(embeds=[embed1, embed2])
        await ctx.reply("Verification embed has been sent.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Verification(bot))
