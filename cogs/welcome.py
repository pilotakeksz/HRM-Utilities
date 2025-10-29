import discord
from discord.ext import commands
import os

FOOTER_TEXT = "Maplecliff National Guard"  
FOOTER_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"
EMBED_COLOR = 0xd0b47b

# Read env vars with safe fallbacks. If ROLE_ID_ON_JOIN isn't set, fall back to the
# commonly used role for new members (1329910383678328922).
DEFAULT_ROLE_ON_JOIN = 1329910383678328922
DEFAULT_WELCOME_CHANNEL = None

role_env = os.getenv("ROLE_ID_ON_JOIN")
try:
    ROLE_ID_ON_JOIN = int(role_env) if role_env else DEFAULT_ROLE_ON_JOIN
except Exception:
    ROLE_ID_ON_JOIN = DEFAULT_ROLE_ON_JOIN

chan_env = os.getenv("WELCOME_CHANNEL_ID")
try:
    WELCOME_CHANNEL_ID = int(chan_env) if chan_env else DEFAULT_WELCOME_CHANNEL
except Exception:
    WELCOME_CHANNEL_ID = DEFAULT_WELCOME_CHANNEL

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

    @commands.command(name="welcome")
    async def test_welcome(self, ctx): #test command
        
        member_count = ctx.guild.member_count
        welcome_text = f"Welcome {ctx.author.mention}!"

        embed = discord.Embed(
            color=EMBED_COLOR,
            description=f"Welcome to the official Maplecliff National Guard Discord server!\nYou are member number: **{member_count}**"
        )
        embed.add_field(
            name="Verify <:check:1343223894412365824>",
            value="- [Verify here](https://discord.com/channels/1329908357812981882/1329910450476945588)",
            inline=True
        )
        embed.add_field(
            name="Chat <:general:1343223933251358764>",
            value="- [Chat here](https://discord.com/channels/1329908357812981882/1329910472069353566)",
            inline=True
        )
        embed.add_field(
            name="Apply <:apply:1377014054085984318>",
            value="- [Apply here](https://discord.com/channels/1329908357812981882/1329910467698622494)",
            inline=True
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        await ctx.send(content=welcome_text, embed=embed, view=WelcomeView(member_count))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Try to assign the default role on join (if available)
        try:
            role = member.guild.get_role(ROLE_ID_ON_JOIN)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Auto role on join")
                except Exception as e:
                    print(f"Failed to assign role {ROLE_ID_ON_JOIN} to {member.id}: {e}")
        except Exception as e:
            print(f"Error while resolving role {ROLE_ID_ON_JOIN}: {e}")

        member_count = member.guild.member_count
        welcome_text = f"Welcome {member.mention}!"

        embed = discord.Embed(
            color=EMBED_COLOR,
            description=f"Welcome to the official Mapplecliff National Guard discord server!\nYou are member number: **{member_count}**"
        )
        embed.add_field(
            name="Verify <:check:1343223894412365824>",
            value="- [Verify here](https://discord.com/channels/1329908357812981882/1329910450476945588)",
            inline=True
        )
        embed.add_field(
            name="Chat <:general:1343223933251358764>",
            value="- [Chat here](https://discord.com/channels/1329908357812981882/1329910472069353566)",
            inline=True
        )
        embed.add_field(
            name="Apply <:apply:1377014054085984318>",
            value="- [Apply here](https://discord.com/channels/1329908357812981882/1329910467698622494)",
            inline=True
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID) or member.guild.system_channel

        if channel:
            try:
                await channel.send(content=welcome_text, embed=embed, view=WelcomeView(member_count))
            except Exception as e:
                print(f"Failed to send welcome message: {e}")
        else:
            print("Welcome channel not found.")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
