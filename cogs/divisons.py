import discord
from discord.ext import commands
import os

from dotenv import load_dotenv
load_dotenv()

EMBED_COLOUR = int(os.getenv("EMBED_COLOUR", "0xd0b47b"), 16)
EMBED_FOOTER = os.getenv("EMBED_FOOTER", "High Rock Military Corps")
EMBED_ICON = os.getenv("EMBED_ICON")
EMBED1_IMAGE = ""
EMBED2_IMAGE = os.getenv("EMBED2_IMAGE")
DIVISIONS_CHANNEL = int(os.getenv("DIVISIONS_CHANNEL", "1332065491266834493"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "840949634071658507"))
DIVISIONS_MSG_ID_FILE = "divisions_message_id.txt"

class DivisionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Military Internal Affairs",
                value="mia",
                emoji="<:MIA:1364309116859715654>"
            ),
            discord.SelectOption(
                label="High Rock National Guard",
                value="ng",
                emoji="<:NationalGuard:1368532752625963048>"
            ),
        ]
        super().__init__(
            placeholder="Select a division:",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="division_select"  # <-- Add this line for persistence!
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "mia":
            await interaction.response.send_message(embeds=get_mia_embeds(), view=MIAButtonView(), ephemeral=True)
        elif self.values[0] == "ng":
            await interaction.response.send_message(embeds=get_ng_embeds(), view=NGButtonView(), ephemeral=True)

class DivisionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view, no timeout
        self.add_item(DivisionSelect())

    @classmethod
    async def send_or_edit(cls, channel, message_id=None):
        embeds = get_main_embeds()
        view = cls()
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embeds=embeds, view=view)
                return msg
            except Exception:
                pass
        return await channel.send(embeds=embeds, view=view)

class MIAButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Join Today!",
                style=discord.ButtonStyle.link,
                emoji="<:MIA:1364309116859715654>",
                url="https://discord.gg/xRashKPAKt"
            )
        )

class NGButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Join Today!",
                style=discord.ButtonStyle.link,
                emoji="<:NationalGuard:1368532752625963048>",
                url="https://discord.gg/QtY2YdkHZK"
            )
        )

def get_main_embeds():
    embed1 = discord.Embed(
        color=EMBED_COLOUR
    )
    if EMBED1_IMAGE:
        embed1.set_image(url=EMBED1_IMAGE)

    embed2 = discord.Embed(
        title="<:termsinfo1:1376649353770434610> HRMC Divisions",
        description=(
            "<:HRMdot:1376648507859144765> **Welcome to the High Rock Military Divisions Hub**\n"
            "> You will be  able to find all our divisions and information about them. All divisions are open and friendly to chat! We recommend you join and experience them!"
        ),
        color=EMBED_COLOUR
    )
    if EMBED2_IMAGE:
        embed2.set_image(url=EMBED2_IMAGE)
    embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
    return [embed1, embed2]

def get_mia_embeds():
    embed1 = discord.Embed(
        color=0xd2d1cf
    )
    embed1.set_image(url="https://media.discordapp.net/attachments/1362507688810119400/1364231491004923944/Assistance.png.png?ex=685df3d5&is=685ca255&hm=5735ab1168a6d86e000bc62b2fcd4b971ce88278c4ea695e61215d30f53417e7&format=webp&quality=lossless&width=1618&height=809&")

    embed2 = discord.Embed(
        title="<:MIA:1364309116859715654>| High Rock Military Internal Affairs",
        description=(
            "> <:MIAdot:1365679087078604840>Military Internal Affairs exists to correct the actions of individuals or sub-departments that violate the Military’s Guidelines. This division ensures accountability and order within the ranks by overseeing disciplinary actions and maintaining standards across the armed forces.\n\n"
            "## <:MIAthumbtack1:1365681465806815282>  Its key responsibilities include:"
        ),
        color=0xd2d1cf
    )
    embed2.add_field(
        name="<:report:1343192037360406550> Reports",
        value=(
            "> <:MIAdot:1365679087078604840>Personnel Reports\n"
            "> <:MIAdot:1365679087078604840>Members Reports\n"
            "> <:MIAdot:1365679087078604840>HRM Sub Departments Reports"
        ),
        inline=True
    )
    embed2.add_field(
        name="<:apply:1377014054085984318> Appeals",
        value=(
            "> <:MIAdot:1365679087078604840>HRM Bans Appeals\n"
            "> <:MIAdot:1365679087078604840>HRM Moderations Appeals\n"
            "> <:MIAdot:1365679087078604840>HRM Disciplines Appeals"
        ),
        inline=True
    )
    embed2.set_image(url="https://media.discordapp.net/attachments/1362507688810119400/1364265524921634888/Untitled_design.png?ex=685e1387&is=685cc207&hm=c25172bb2b9a7dea3de3d42704f165d2614af8b23c747fef8b29b604c45790a8&format=webp&quality=lossless&width=872&height=44&")
    embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
    return [embed1, embed2]

def get_ng_embeds():
    embed1 = discord.Embed(
        color=0x4e7410,
        description=(
            "# <:NationalGuard:1368532752625963048> | HIGH ROCK NATIONAL GUARD\n"
            ">  Ever wanted to take part in protecting our land that we live on?\n"
            ">  Want to take part in 🔥  action?\n\n"
            "**Join the National Guard team today!**\n\n"
            "- We are looking for:\n"
            "> - Ambitus Personnel\n"
            "> - Members that would love to be a part of our community!\n"
            "> - An active team\n"
            "> - Personnel that would love there position here!"
        )
    )
    return [embed1]

class Divisions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(DivisionView())  # Register persistent view

    @commands.command(name="divisions")
    async def divisions_command(self, ctx):
        if ctx.author.id != ADMIN_ID:
            await ctx.send("❌ Only the bot admin can use this command.")
            return
        channel = ctx.guild.get_channel(DIVISIONS_CHANNEL)
        if not channel:
            await ctx.send("❌ Could not find the divisions channel.")
            return
        embeds = get_main_embeds()
        msg = await channel.send(embeds=embeds, view=DivisionView())
        # Save the message ID for persistence
        with open(DIVISIONS_MSG_ID_FILE, "w") as f:
            f.write(str(msg.id))
        await ctx.send("✅ Divisions embed sent in the divisions channel!", delete_after=10)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(DivisionView())  # Register persistent view
        # Try to re-attach the view to the existing message after restart
        try:
            with open(DIVISIONS_MSG_ID_FILE, "r") as f:
                msg_id = int(f.read().strip())
            channel = self.bot.get_channel(DIVISIONS_CHANNEL)
            if channel:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(view=DivisionView())
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(Divisions(bot))