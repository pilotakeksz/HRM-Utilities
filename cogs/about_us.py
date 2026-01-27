import discord
from discord.ext import commands
from discord import app_commands

EMBED_COLOR = 0xd0b47b
ABOUT_US_CHANNEL_ID = 1329910454059008101
OWNER_ID = 840949634071658507

FOOTER_ICON = "http://localhost:8889/footer_icon.webp"
FOOTER_TEXT = "Maplecliff National Guard"

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
                    "- [BG] - Brigadier General\n"
                    "- [MG] - Major General\n"
                    "- [LTG] - Lieutenant General\n"
                    "- [GEN] - General\n"
                    "- [GA] - General of the Army\n"

                )
            ),
            "high": discord.Embed(
                title="__Senior Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [MAJ] - Major\n"
                    "- [LTC] - Lieutenant Colonel\n"
                    "- [COL] - Colonel\n"
                )    

            ),
            "junior": discord.Embed(
                title="__Junior Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [2LT] - Second Lieutenant\n"
                    "- [1LT] - First Lieutenant\n"
                    "- [CPT] - Captain\n"
                )    

            ),
            "warrant": discord.Embed(
                title="__Warrant Officers__ *(Middle Command)*",
                color=EMBED_COLOR,
                description=(
                    "- [WO1] - Warrant Officer 1\n"
                    "- [CW2] - Chief Warrant Officer 2\n"
                    "- [CW3] - Chief Warrant Officer 3\n"
                    "- [CW4] - Chief Warrant Officer 4\n"
                    "- [CW5] - Chief Warrant Officer 5\n"
                )
            ),
            "low": discord.Embed(
                title="__Senior Non-commissioned Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [SFC] - Sergeant First Class\n"
                    "- [MSG] - Master Sergeant\n"
                    "- [1SG] - First Sergeant\n"
                    "- [SGM] - Sergeant Major\n"
                    "- [CSM] - Command Sergeant Major\n"
                    "- [SMA] - Sergeant Major of the Army\n"
                )
            ),
            "intermediate": discord.Embed(
                title="__Non-commissioned Officers__",
                color=EMBED_COLOR,
                description=(
                    "- [CPL] - Corporal\n"
                    "- [SGT] - Sergeant\n"
                    "- [SSG] - Staff Sergeant\n"
                )
            ),
            "commissioned": discord.Embed(
                title="__Junior Enlisted Ranks__",
                color=EMBED_COLOR,
                description=(
                    "- [PVT] - Private\n"
                    "- [PV2] - Private Second Class\n"
                    "- [PFC] - Private First Class\n"
                    "- [SPC] - Specialist\n"
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
        embed1.set_image(url="http://localhost:8889/about_us_banner.png")

        embed2 = discord.Embed(
            title="<:general:1343223933251358764> About Us",
            description="Welcome to the **Maplecliff National Guard!** Our mission is to ensure security, conduct strategic operations, and provide rapid emergency response, protect Maplecliff's borders, and assist the police force.",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="<:HRMlink:1376648059525791784> Useful Links",
            value=(
                "> [Server shouts](https://discord.com/channels/1329908357812981882/1329910463307448322)\n"
                "> [MCNG Application](https://discord.com/channels/1329908357812981882/1329910467698622494)\n"
                "> [MCNG Internal Affairs](https://discord.gg/CbwwbHgPUr)\n"
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
        embed2.set_image(url="http://localhost:8889/bottom_banner.png")

        view = RankInfoView()
        await channel.send(embed=embed1)
        await channel.send(embed=embed2, view=view)
        await ctx.send("About Us sent.", delete_after=10)

async def setup(bot: commands.Bot):
    bot.add_view(RankInfoView()) 
    await bot.add_cog(AboutUs(bot))
