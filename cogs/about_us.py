import discord
from discord.ext import commands
from discord import app_commands

EMBED_COLOR = 0xd0b47b
ABOUT_US_CHANNEL_ID = 1329910454059008101
OWNER_ID = 840949634071658507

FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
FOOTER_TEXT = "High Rock Military Corps"

class RankInfoSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Junior Enlisted", value="commissioned", description="View Junior Enlisted ranks"),
            discord.SelectOption(label="Non-commissioned Officers", value="intermediate", description="View NCOs"),
            discord.SelectOption(label="Senior Non-commissioned Officers", value="low", description="View Senior NCOs"),
            discord.SelectOption(label="Warrant Officers", value="warrant", description="View Warrant Officers"),
            discord.SelectOption(label="Junior Officers", value="junior", description="View Junior Officers"),
            discord.SelectOption(label="Senior Officers", value="high", description="View Senior Officers"),
        discord.SelectOption(label="General Officers", value="senior", description="View General Officers"),
        ]
        super().__init__(
            placeholder="Rank info",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="aboutus_rankinfo_select"
        )

    async def callback(self, interaction: discord.Interaction):
        embeds = {
            "senior": discord.Embed(
                title="__General officers__",
                color=EMBED_COLOR,
                description=(
                    "- [GA] - General of the Army\n"
                    "- [GEN] - General\n"
                    "- [LTG] - Lieutenant General\n"
                    "- [MG] - Major General\n"
                    "- [BG] - Brigadier General\n"

                )
            ),
            "high": discord.Embed(
                title="__Senior Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [COL] - Colonel\n"
                    "- [LTC] - Lieutenant Colonel\n"
                    "- [MAJ] - Major\n"
                )    

            ),
            "junior": discord.Embed(
                title="__Junior Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [CPT] - Captain\n"
                    "- [1LT] - First Lieutenant\n"
                    "- [2LT] - Second Lieutenant\n"
                )    

            ),
            "warrant": discord.Embed(
                title="__Warrant Officers__ *(Middle Command)*",
                color=EMBED_COLOR,
                description=(
                    "- [CW5] - Chief Warrant Officer 5\n"
                    "- [CW4] - Chief Warrant Officer 4\n"
                    "- [CW3] - Chief Warrant Officer 3\n"
                    "- [CW2] - Chief Warrant Officer 2\n"
                    "- [WO1] - Warrant Officer 1\n"
                )
            ),
            "low": discord.Embed(
                title="__Senior Non-commissioned Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [SMA] - Sergeant Major of the Army\n"
                    "- [CSM] - Command Sergeant Major\n"
                    "- [SGM] - Sergeant Major\n"
                    "- [1SG] - First Sergeant\n"
                    "- [MSG] - Master Sergeant\n"
                    "- [SFC] - Sergeant First Class\n"
                )
            ),
            "intermediate": discord.Embed(
                title="__Non-commissioned Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [SSG] - Staff Sergeant\n"
                    "- [SGT] - Sergeant\n"
                    "- [CPL] - Corporal\n"
                )
            ),
            "commissioned": discord.Embed(
                title="__Junior Enlisted Ranks__",
                color=EMBED_COLOR,
                description=(
                    "- [SPC] - Specialist\n"
                    "- [PFC] - Private First Class\n"
                    "- [PV2] - Private\n"
                    "- [PVT] - Private\n"
                )
            ),
        }
        embed = embeds[self.values[0]]
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RankInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RankInfoSelect())

class AboutUs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="aboutus")
    async def aboutus(self, ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return

        channel = ctx.guild.get_channel(ABOUT_US_CHANNEL_ID)
        if not channel:
            await ctx.send("About Us channel not found.")
            return

        embed1 = discord.Embed(color=EMBED_COLOR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376933929264742500/about_us.png?ex=685d5ca6&is=685c0b26&hm=04b552a8d85bb04427b330898d4e020a05b7aab029425abd828fcac7e4555e52&format=webp&quality=lossless&width=1630&height=544&")

        embed2 = discord.Embed(
            title="<:HRMaboutus:1376647782248742993> About Us",
            description="Welcome to the **High Rock Military Corps!** Our mission is to ensure security, conduct strategic operations, and provide rapid emergency response, protect High Rock's border, and assist the police force.",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="<:HRMlink:1376648059525791784> Useful Links",
            value=(
                "> [Server shouts](https://discord.com/channels/1329908357812981882/1329910463307448322)\n"
                "> [HRMC Application](https://discord.com/channels/1329908357812981882/1329910467698622494)\n"
                "> [HRMC Internal Affairs](https://discord.gg/CbwwbHgPUr)\n"
                "> [Assistance](https://discord.com/channels/1329908357812981882/1329910457409994772)"
            ),
            inline=True
        )
        embed2.add_field(
            name="<:termsinfo1:1376649353770434610> Useful Channels",
            value=(
                "> <#1329910450476945588>\n"
                "> <#1364242592887209984>\n"
                "> <#1329910457409994772>\n"
                "> <#1329910467698622494>"
            ),
            inline=True
        )
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        embed2.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=685d5cd1&is=685c0b51&hm=0566c14b0d954d69f196e494335df276efa559439b55c9f7eac98e59cec0b259&format=webp&quality=lossless&width=1163&height=60&")

        view = RankInfoView()
        await channel.send(embed=embed1)
        await channel.send(embed=embed2, view=view)
        await ctx.send("About Us sent.", delete_after=10)

async def setup(bot: commands.Bot):
    bot.add_view(RankInfoView())  # Register persistent view for rank info select
    await bot.add_cog(AboutUs(bot))

# To enable persistent views, add this to your main bot.py after creating the bot:
# from cogs.about_us import RankInfoView
# bot.add_view(RankInfoView())