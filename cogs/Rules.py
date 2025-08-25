import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select

EMBED_COLOR = 0xd0b37b
REGS_CHANNEL_ID = 1364242592887209984
OWNER_ID = 840949634071658507

FOOTER_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"
FOOTER_TEXT = "Maplecliff National Guard"

class RegulationsSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Discord Regulations", value="discord", description="View Discord regulations"),
            discord.SelectOption(label="In-Game Regulations", value="game", description="View In-Game regulations"),
        ]
        super().__init__(placeholder="Navigate Interface", min_values=1, max_values=1, options=options, custom_id="regulations_select")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "discord":
            embed = discord.Embed(
                title="Discord Regulations",
                color=EMBED_COLOR,
                description=(
                    "**1. Respect all others**\n"
                    "**2. Keep content strictly safe for work**\n"
                    "**3. Use designated channels when possible**\n"
                    "**4. Do not needlessly ping**\n"
                    "**5. Do not attempt to abuse**\n"
                    "**6. No mentioning ongoing or past politics**"
                )
            )
            embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="In-Game Regulations",
                color=EMBED_COLOR,
                description=(
                    "**1. RDM** - Random Death Match\n"
                    "**2. Staff RDM**\n"
                    "**3. Mass RDM**\n"
                    "**4. VDM** - Vehicle Death Match\n"
                    "**5. Staff VDM**\n"
                    "**6. Mass VDM**\n"
                    "**7. Disrespect Player/Staff**\n"
                    "**8. Trolling**\n"
                    "**9. FRP** - Fail Roleplay\n"
                    "**10. NLR** - New Life Rule\n"
                    "**11. FKL** - Full Killing\n"
                    "**12. Cuff Rush & Auto Jail**\n"
                    "**13. Cop Baiting**\n"
                    "**14. Tow Rush**\n"
                    "**15. GTA Driving**\n"
                    "**16. Fear RP**\n"
                    "**17. !mod Abuse**\n"
                    "**18. Tool Abuse**\n"
                    "**19. Mass Tool Abuse**\n"
                    "**20. Safezone Killing**\n"
                    "**21. NITRP**\n"
                    "**22. Staff Evasion**\n"
                    "**23. LTAP**\n"
                    "**24. Breaking ToS PRC/Roblox**\n"
                    "**25. Banned Items**\n"
                    "**26. Banned Weapons**\n"
                    "**27. Unrealistic Avatar**\n"
                    "**28. Whitelisted Vehicles**\n"
                    "**29. Whitelisted Items**"
                )
            )
            embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RegulationsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegulationsSelect())

class Rules(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register persistent view on cog load
        bot.add_view(RegulationsView())

    @app_commands.command(name="send-regulations", description="Send the regulations embed (owner only)")
    async def send_regulations(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(REGS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Regulations channel not found.", ephemeral=True)
            return

        embed1 = discord.Embed(color=EMBED_COLOR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314376019738664/REGULATIONS.png?ex=68acedcb&is=68ab9c4b&hm=9c0653b7ca7421ec9ff37a6c3f37a86784a44b20e2a6a417d7b5d07772b69272&=&format=webp&quality=lossless&width=2576&height=862")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> MCNG Regulations",
            description="<:HRMdot:1376648507859144765>Here at *Maplecliff National Guard,* we __ensure the safety of our community members__ by enforcing strict discord regulations to keep members safe from harmful users. Not adhering to the rules posted can result in a warning, kick, or ban based on the rule violated.",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="<:termsinfo1:1376649353770434610> Terms of Service",
            value="<:HRMdot:1376648507859144765> [Discord ToS](https://discord.com/terms)\n<:HRMdot:1376648507859144765> [Roblox ToS](https://en.help.roblox.com/hc/en-us/articles/115004647846-Roblox-Terms-of-Use)",
            inline=True
        )
        embed2.add_field(
            name="<:ballot1:1376978622325194915> Index",
            value="<:HRMdot:1376648507859144765> Discord Regulations\n<:HRMdot:1376648507859144765> In-game Regulations",
            inline=True
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        view = RegulationsView()
        await channel.send(embed=embed1)
        await channel.send(embed=embed2, view=view)
        await interaction.response.send_message("Regulations sent.", ephemeral=True)

    @commands.command(name="regulations")
    async def regulations_command(self, ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return

        # Try to fetch the channel globally in case it's not cached
        channel = ctx.guild.get_channel(REGS_CHANNEL_ID)
        if not channel:
            try:
                channel = await ctx.bot.fetch_channel(REGS_CHANNEL_ID)
            except Exception:
                channel = None

        if not channel:
            await ctx.send("Regulations channel not found or I don't have access.")
            return

        embed1 = discord.Embed(color=EMBED_COLOR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314376019738664/REGULATIONS.png?ex=68acedcb&is=68ab9c4b&hm=9c0653b7ca7421ec9ff37a6c3f37a86784a44b20e2a6a417d7b5d07772b69272&=&format=webp&quality=lossless&width=2576&height=862")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> MCNG Regulations",
            description="<:HRMdot:1376648507859144765>Here at *Maplecliff National Guard,* we __ensure the safety of our community members__ by enforcing strict discord regulations to keep members safe from harmful users. Not adhering to the rules posted can result in a warning, kick, or ban based on the rule violated.",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="<:termsinfo1:1376649353770434610> Terms of Service",
            value="<:HRMdot:1376648507859144765> [Discord ToS](https://discord.com/terms)\n<:HRMdot:1376648507859144765> [Roblox ToS](https://en.help.roblox.com/hc/en-us/articles/115004647846-Roblox-Terms-of-Use)",
            inline=True
        )
        embed2.add_field(
            name="<:ballot1:1376978622325194915> Index",
            value="<:HRMdot:1376648507859144765> Discord Regulations\n<:HRMdot:1376648507859144765> In-game Regulations",
            inline=True
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        view = RegulationsView()
        await channel.send(embed=embed1)
        await channel.send(embed=embed2, view=view)
        await ctx.send("Regulations sent.", delete_after=10)

async def setup(bot: commands.Bot):
    bot.add_view(RegulationsView())  # Register persistent view for regulations select
    await bot.add_cog(Rules(bot))