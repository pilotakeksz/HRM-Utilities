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
            discord.SelectOption(label="Commissioned Officers", value="commissioned", description="View Commissioned Officers"),
            discord.SelectOption(label="Intermediate Operation Corps", value="intermediate", description="View Intermediate Operation Corps"),
            discord.SelectOption(label="Low Command", value="low", description="View Low Command"),
            discord.SelectOption(label="Warrant Officers", value="warrant", description="View Warrant Officers"),
            discord.SelectOption(label="High Command", value="high", description="View High Command"),
            discord.SelectOption(label="Senior High Command", value="senior", description="View Senior High Command"),
        ]
        super().__init__(placeholder="Rank info", min_values=1, max_values=1, options=options, custom_id="aboutus_rankinfo_select")

    async def callback(self, interaction: discord.Interaction):
        embeds = {
            "senior": discord.Embed(
                title="__Senior High Command__",
                color=EMBED_COLOR,
                description=(
                    "- SHC (Super High Command)\n"
                    "- GOTA (General of The Army)\n"
                    "- GEN (General)\n"
                    "- LG (Lieutenant General)\n"
                    "- MG (Major General)\n"
                    "- BG (Brigadier General)\n"
                    "- SHR (Super High Rank)"
                )
            ),
            "high": discord.Embed(
                title="__High Command__",
                color=EMBED_COLOR,
                description=(
                    "- COL (Colonel)\n"
                    "- LCOL (Lieutenant Colonel)\n"
                    "- MAJ (Major)\n"
                    "- CPT (Captain)\n"
                    "- FL (First Lieutenant)\n"
                    "- SL (Second Lieutenant)"
                )
            ),
            "warrant": discord.Embed(
                title="__Warrant Officers__ *(Middle Command)*",
                color=EMBED_COLOR,
                description=(
                    "- CWO (Chief Warrant Officer)\n"
                    "- HWO (Head Warrant Officer)\n"
                    "- SWO (Senior Warrant Officer)\n"
                    "- WO (Warrant Officer)"
                )
            ),
            "low": discord.Embed(
                title="__Low Command__",
                color=EMBED_COLOR,
                description=(
                    "- MSGT (Master Sergeant)\n"
                    "- SFC (Sergeant First Class)\n"
                    "- SS (Staff Sergeant)\n"
                    "- SGT (Sergeant)\n"
                    "- CPL (Corporal)"
                )
            ),
            "intermediate": discord.Embed(
                title="__Intermediate Operation Corps__",
                color=EMBED_COLOR,
                description=(
                    "- OL (Operations Lieutenant)\n"
                    "- OS (Operations Supervisor)\n"
                    "- OSPT (Operations Specialist)\n"
                    "- SO (Senior Operator)\n"
                    "- JO (Junior Operator)\n"
                    "- OC (Operations Cadet)"
                )
            ),
            "commissioned": discord.Embed(
                title="__Commissioned Officers__",
                color=EMBED_COLOR,
                description=(
                    "- PFC (Private First Class)\n"
                    "- PSC (Private Second Class)\n"
                    "- PVT (Private)"
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

    # For persistent views
    @property
    def persistent(self):
        return True

class AboutUs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register persistent view on cog load
        bot.add_view(RankInfoView())

    @app_commands.command(name="aboutus", description="Send the About Us embed (owner only)")
    async def aboutus(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(ABOUT_US_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("About Us channel not found.", ephemeral=True)
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
        await interaction.response.send_message("About Us sent.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AboutUs(bot))