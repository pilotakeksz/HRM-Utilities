import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Constants for footer
FOOTER_TEXT = "High Rock Military Corps."
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"

# Role to assign on join
ROLE_ID_ON_JOIN = 1329910383678328922

# Embed color
EMBED_COLOR = 0xd0b47b

# Buttons for welcome message (2 buttons)
class WelcomeView(discord.ui.View):
    def __init__(self, member_count: int):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Regulations",
            url="https://discord.com/channels/1329908357812981882/1364242592887209984",
            style=discord.ButtonStyle.grey if hasattr(discord.ButtonStyle, 'grey') else discord.ButtonStyle.secondary,
            emoji="<:regulations:1343313357121392733>"
        ))
        # Custom disabled button with member count
        button = discord.ui.Button(
            label=f"Members: {member_count}",
            style=discord.ButtonStyle.grey if hasattr(discord.ButtonStyle, 'grey') else discord.ButtonStyle.secondary,
            emoji="<:Member:1343945679390904330>",
            disabled=True
        )
        self.add_item(button)



@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="High Rock"))

    await tree.sync()  # Sync slash commands globally (or specify guild for faster)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member: discord.Member):
    # Assign role
    role = member.guild.get_role(ROLE_ID_ON_JOIN)
    if role:
        try:
            await member.add_roles(role, reason="Auto role on join")
        except Exception as e:
            print(f"Failed to add role: {e}")

    member_count = member.guild.member_count

    # Text ping
    welcome_text = f"Welcome {member.mention}!"

    # First embed
    embed1 = discord.Embed(
        color=EMBED_COLOR,
        title=f"Welcome to HRMC {member.display_name}!"
    )
    embed1.set_image(url="https://cdn.discordapp.com/attachments/1376647068092858509/1376934098332811315/Welcome.png?ex=685c0b4f&is=685ab9cf&hm=e4e0bc567909588bfcf43eb5c92d174fcd6ec2d83867d10d671eea3376f86cc3&")
    embed1.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    # Second embed
    embed2 = discord.Embed(
        color=EMBED_COLOR,
        description=(
            f"Welcome to the official High Rock Military Corps Discord server! \n"
            f"You are member number: **{member_count}**"
        )
    )
    embed2.add_field(
        name="Verify <:check:1343223894412365824>",
        value="- [In order to view channels and apply, verify!](https://discord.com/channels/1329908357812981882/1329910450476945588)",
        inline=True
    )
    embed2.add_field(
        name="Chat <:general:1343223933251358764>",
        value="- [Talk to the friendly personnel of HRMC.](https://discord.com/channels/1329908357812981882/1329910472069353566)",
        inline=True
    )
    embed2.add_field(
        name="Apply <:apply:1377014054085984318>",
        value="- [Become the newest HRMC personnel!](https://discord.com/channels/1329908357812981882/1329910467698622494)",
        inline=True
    )
    embed2.set_image(url="https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=685c0b51&is=685ab9d1&hm=5e11d0d184e9deaf05f415e8cbdadabff8ee94c50ddf438307cd56cf7a3b3d65&")
    embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    try:
        await member.guild.system_channel.send(content=welcome_text, embeds=[embed1, embed2], view=WelcomeView(member_count))
    except Exception as e:
        print(f"Failed to send welcome message: {e}")

# Slash command /send-verification restricted to your user ID
@tree.command(name="send-verification", description="Send the verification embed (admin only)")
async def send_verification(interaction: discord.Interaction):
    if interaction.user.id != 840949634071658507:
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
        return

    channel = bot.get_channel(1329910450476945588)
    if channel is None:
        await interaction.response.send_message("Verification channel not found.", ephemeral=True)
        return

    embed1 = discord.Embed(color=EMBED_COLOR)
    embed1.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376934088841236620/verification.png?ex=685c0b4c&is=685ab9cc&hm=4311361c37e72867793bcd0ef02a1390261b66ad37d125ac25aa69c09daab597&format=webp&quality=lossless&width=1630&height=544&")

    embed2 = discord.Embed(
        title="<:HRMaboutus:1376647782248742993> HRMC Verification",
        description=(
            "Here at *High Rock Military Corps*, we__ ensure the safety of our community members__ "
            "by enforcing strict discord verification, you must verify to gain access to the rest "
            "of our server and to be able to apply."
        ),
        color=EMBED_COLOR
    )
    embed2.set_image(url="https://media.discordapp.net/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=685c0b51&is=685ab9d1&hm=5e11d0d184e9deaf05f415e8cbdadabff8ee94c50ddf438307cd56cf7a3b3d65&format=webp&quality=lossless&width=1163&height=60&")
    embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    await channel.send(embeds=[embed1, embed2])
    await interaction.response.send_message("Verification embed has been sent.", ephemeral=True)


# Run your bot - replace "YOUR_BOT_TOKEN" with your bot token string
bot.run("MTM4NzE3NTY2NDY0OTUwNjg0Nw.Gw2RGv.JP2XLTe3MkyT73ddfkuP62BL5TOnDlI2x5jWec")
