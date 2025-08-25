import discord
from discord.ext import commands
import os

EMBED_COLOR = 0xd0b47b
FOOTER_TEXT = "Maplecliff National Guard"
FOOTER_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"

VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID"))

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="verification")
    async def verification_command(self, ctx: commands.Context):
        # Replace with your admin ID(s) or better permission checking
        if ctx.author.id != 840949634071658507:
            await ctx.reply("You do not have permission to run this command.", delete_after=10)
            return

        channel = self.bot.get_channel(VERIFICATION_CHANNEL_ID)
        if channel is None:
            await ctx.reply("Verification channel not found.", delete_after=10)
            return

        embed1 = discord.Embed(color=EMBED_COLOR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314377718435921/VERIFICATION.png?ex=68acedcb&is=68ab9c4b&hm=012cadf60e26d32d668f8ea57909c1e69171bc86f3965a5013ec083aec580dad&=&format=webp&quality=lossless&width=2576&height=862")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> MCNG Verification",
            description=(
                "Here at *Maplecliff National Guard*, we__ ensure the safety of our community members__ "
                "by enforcing strict discord verification, you must verify to gain access to the rest "
                "of our server and to be able to apply."
            ),
            color=EMBED_COLOR
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        await channel.send(embeds=[embed1, embed2])
        await ctx.reply("Verification embed has been sent.", delete_after=10)

async def setup(bot):
    await bot.add_cog(Verification(bot))
