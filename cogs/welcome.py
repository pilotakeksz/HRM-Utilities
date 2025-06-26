import discord
from discord.ext import commands
import os

FOOTER_TEXT = "High Rock Military Corps."
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
EMBED_COLOR = 0xd0b47b

ROLE_ID_ON_JOIN = int(os.getenv("ROLE_ID_ON_JOIN"))
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))

class WelcomeView(discord.ui.View):
    def __init__(self, member_count: int):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Regulations",
            url="https://discord.com/channels/1329908357812981882/1364242592887209984",
            style=discord.ButtonStyle.secondary,
            emoji="<:regulations:1343313357121392733>"
        ))
        button = discord.ui.Button(
            label=f"Members: {member_count}",
            style=discord.ButtonStyle.secondary,
            emoji="<:Member:1343945679390904330>",
            disabled=True
        )
        self.add_item(button)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role = member.guild.get_role(ROLE_ID_ON_JOIN)
        if role:
            try:
                await member.add_roles(role, reason="Auto role on join")
            except Exception as e:
                print(f"Failed to add role: {e}")

        member_count = member.guild.member_count
        welcome_text = f"Welcome {member.mention}!"

        embed1 = discord.Embed(
            color=EMBED_COLOR,
            title=f"Welcome to HRMC {member.display_name}!"
        )
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1376647068092858509/1376934098332811315/Welcome.png")


        embed2 = discord.Embed(
            color=EMBED_COLOR,
            description=f"Welcome to the official High Rock Military Corps Discord server!\nYou are member number: **{member_count}**"
        )
        embed2.add_field(
            name="Verify <:check:1343223894412365824>",
            value="- [Verify here](https://discord.com/channels/1329908357812981882/1329910450476945588)",
            inline=True
        )
        embed2.add_field(
            name="Chat <:general:1343223933251358764>",
            value="- [Chat here](https://discord.com/channels/1329908357812981882/1329910472069353566)",
            inline=True
        )
        embed2.add_field(
            name="Apply <:apply:1377014054085984318>",
            value="- [Apply here](https://discord.com/channels/1329908357812981882/1329910467698622494)",
            inline=True
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png")
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID) or member.guild.system_channel

        if channel:
            try:
                await channel.send(content=welcome_text, embeds=[embed1, embed2], view=WelcomeView(member_count))
            except Exception as e:
                print(f"Failed to send welcome message: {e}")
        else:
            print("Welcome channel not found.")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
