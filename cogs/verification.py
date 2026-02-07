import discord
from discord.ext import commands
import os

EMBED_COLOR = 0xd0b47b
FOOTER_TEXT = "Maplecliff National Guard"
FOOTER_ICON = "https://cdn.discordapp.com/attachments/1465844086480310342/1465854196673679545/logo.png?ex=697a9e9a&is=69794d1a&hm=9e44326e792f3092e3647f1cfce191c4b1d3264aa8eae50cd5c443bcb5b09ee1&"

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
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1465844086480310342/1466110718037459277/VERIFICATION.png?ex=697b8d82&is=697a3c02&hm=e8e19c7190822af7cdc39a74a80904f975f38fd0c13c26a35eeb8042a4342556&")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> MCNG Verification",
            description=(
                "Here at *Maplecliff National Guard*, we__ ensure the safety of our community members__ "
                "by enforcing strict discord verification, you must verify to gain access to the rest "
                "of our server and to be able to apply."
            ),
            color=EMBED_COLOR
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1465844086480310342/1466110649137627452/bottom.png?ex=697b8d71&is=697a3bf1&hm=72e7b90e8ac56d236c78f02471543e80cb2f9273d670b90f7b4f6b12c0138187&s")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        await channel.send(embeds=[embed1, embed2])
        await ctx.reply("Verification embed has been sent.", delete_after=10)

async def setup(bot):
    await bot.add_cog(Verification(bot))
