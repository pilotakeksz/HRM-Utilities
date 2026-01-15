import discord
from discord.ext import commands
import os
import datetime
import json

FOOTER_TEXT = "Maplecliff National Guard"  
FOOTER_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"
EMBED_COLOR = 0xd0b47b
MILESTONE_ROLE_ID = 1331667130000605278
MILESTONE_MEMBER_COUNT = 600
MILESTONE_COOLDOWN_HOURS = 48
MILESTONE_DATA_FILE = os.path.join("data", "milestone_data.json")

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

# Users automatically blacklisted: the bot will DM and ban these user IDs on join
# Add user IDs (integers) to this list to have them auto-banned when they join.
BLACKLISTED_USER_IDS = [
    # Example: 1163179403954618469,
]
 
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
        self.last_milestone_time = {}  # Track when last milestone was sent per guild (guild_id -> timestamp)
        self.load_milestone_data()

    def load_milestone_data(self):
        """Load milestone data from JSON file."""
        if os.path.exists(MILESTONE_DATA_FILE):
            try:
                with open(MILESTONE_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert string keys to int keys and ISO strings to datetime objects
                    self.last_milestone_time = {
                        int(guild_id): datetime.datetime.fromisoformat(timestamp_str)
                        for guild_id, timestamp_str in data.items()
                    }
            except Exception as e:
                print(f"Error loading milestone data: {e}")
                self.last_milestone_time = {}
        else:
            self.last_milestone_time = {}

    def save_milestone_data(self):
        """Save milestone data to JSON file."""
        try:
            os.makedirs("data", exist_ok=True)
            # Convert datetime objects to ISO strings for JSON
            data = {
                str(guild_id): timestamp.isoformat()
                for guild_id, timestamp in self.last_milestone_time.items()
            }
            with open(MILESTONE_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving milestone data: {e}")

    def can_send_milestone(self, guild_id: int) -> bool:
        """Check if enough time has passed since last milestone (48 hours)."""
        if guild_id not in self.last_milestone_time:
            return True  # Never sent before, can send
        
        last_time = self.last_milestone_time[guild_id]
        now = datetime.datetime.utcnow()
        time_diff = now - last_time
        
        # Check if 48 hours have passed
        return time_diff.total_seconds() >= (MILESTONE_COOLDOWN_HOURS * 3600)

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
        # Auto-ban blacklisted users: DM then ban on join
        try:
            if member.id in BLACKLISTED_USER_IDS:
                try:
                    await member.send("You have been blacklisted from the Maplecliff National Guard server and will be banned upon joining.")
                except Exception:
                    # DM may fail if user has DMs closed
                    pass
                try:
                    await member.ban(reason="Auto-ban: blacklisted user")
                    print(f"Banned blacklisted user {member} ({member.id}) on join.")
                except Exception as e:
                    print(f"Failed to ban blacklisted user {member.id}: {e}")
                return
        except Exception as e:
            print(f"Error checking blacklist for {member.id}: {e}")

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

        # Check for 600 member milestone (only if 48 hours have passed since last milestone)
        if member_count == MILESTONE_MEMBER_COUNT and self.can_send_milestone(member.guild.id):
            await self.send_milestone_message(member.guild, member_count, is_test=False)
            # Update the timestamp for this guild
            self.last_milestone_time[member.guild.id] = datetime.datetime.utcnow()
            self.save_milestone_data()

    async def send_milestone_message(self, guild: discord.Guild, member_count: int, is_test: bool = False):
        """Send a special message when the server hits exactly 600 members.
        
        Args:
            guild: The Discord guild
            member_count: The member count to display
            is_test: If True, this is a test run and won't update the cooldown timestamp
        """
        try:
            role = guild.get_role(MILESTONE_ROLE_ID)
            if not role:
                print(f"Milestone role {MILESTONE_ROLE_ID} not found in guild {guild.id}")
                return

            # Try to send in welcome channel, fallback to system channel
            channel = guild.get_channel(WELCOME_CHANNEL_ID) or guild.system_channel
            if not channel:
                print(f"No channel found to send milestone message in guild {guild.id}")
                return

            # Create special milestone embed
            embed = discord.Embed(
                title="🎉 MILESTONE ACHIEVED! 🎉",
                description=f"# **WE'VE HIT {member_count} MEMBERS!**\n\n"
                           f"🎊 **Congratulations to everyone!** 🎊\n\n"
                           f"This is an incredible achievement for the Maplecliff National Guard!\n"
                           f"Thank you to all our members and personnel for making this server what it is today!",
                color=0xFFD700  # Gold color for celebration
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
            embed.timestamp = datetime.datetime.utcnow()

            # Only ping the role if it's not a test run
            if is_test:
                content = f"**WE'VE REACHED {member_count} MEMBERS!** 🎉🎊🎉"
            else:
                content = f"{role.mention} **WE'VE REACHED {member_count} MEMBERS!** 🎉🎊🎉"
            
            await channel.send(content=content, embed=embed)
            print(f"Sent milestone message for {member_count} members in guild {guild.id}")
        except Exception as e:
            print(f"Failed to send milestone message: {e}")

    @commands.command(name="test600")
    @commands.has_guild_permissions(administrator=True)
    async def test_milestone(self, ctx):
        """Test command to send the 600 member milestone message (admin only).
        Test runs do not count towards the 48-hour cooldown."""
        await self.send_milestone_message(ctx.guild, MILESTONE_MEMBER_COUNT, is_test=True)
        await ctx.send("✅ Milestone test message sent! (This does not affect the 48-hour cooldown)", delete_after=5)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
