import discord
from discord.ext import commands
from discord import app_commands, ui
import datetime

TRAINING_ROLE_ID = 1329910342301515838
TRAINING_CHANNEL_ID = 1329910495536484374
TRAINING_PING_ROLE = 1329910324002029599
LOG_CHANNEL_ID = 1343686645815181382

TAN = 0xd0b37b
GREEN = 0x2ecc40
RED = 0xe74c3c

TRAINING_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1382412490771533958/training.png?ex=68958c35&is=68943ab5&hm=3ca01df299c7a68fc60d9bb5dc18e9c008a0065ad2eb75f3f5da180d44249ec4&"
BOTTOM_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=68956491&is=68941311&hm=0b21280ebb311d7869b7c2e8b42f70d31202a2acd375cca1b1f0327d8d7e76c2&"
FOOTER_ICON = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=6895b021&is=68945ea1&hm=5efd99410ebe5a372a0bd1f7fb301b916a6a877ec25a1966368713442b794a4f&"
FOOTER_TEXT = "High Rock Militar Corps Trainings"

class TrainingVoteView(ui.View):
    def __init__(self, host_id):
        super().__init__(timeout=None)
        self.voters = set()
        self.host_id = host_id

    @ui.button(label=None, style=discord.ButtonStyle.success, custom_id='training_tick', emoji='<:tick1:1330953719344402584>')
    async def tick_button(self, interaction: discord.Interaction, button: ui.Button):
        self.voters.add(interaction.user.id)
        await interaction.response.send_message('Your vote has been registered!', ephemeral=True)

    @ui.button(label=None, style=discord.ButtonStyle.secondary, custom_id='training_members', emoji='<:Member:1343945679390904330>')
    async def member_button(self, interaction: discord.Interaction, button: ui.Button):
        mentions = [f'<@{uid}>' for uid in self.voters]
        msg = '**Voters:**\n' + ('\n'.join(mentions) if mentions else 'None')
        await interaction.response.send_message(msg, ephemeral=True)

class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="training-vote", description="Start a training session vote.")
    async def training_vote(self, interaction: discord.Interaction):
        # Permission check
        if not any(r.id == TRAINING_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        channel = interaction.client.get_channel(TRAINING_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Training channel not found.", ephemeral=True)
            return
        # Calculate timestamps
        now = datetime.datetime.utcnow()
        ten_min = int((now + datetime.timedelta(minutes=10)).timestamp())
        # Message and embeds
        ping = f"<@&{TRAINING_PING_ROLE}>"
        embed1 = discord.Embed(
            color=TAN,
            title="<:HighRockMilitary:1376605942765977800> // Training Session Vote"
        )
        embed1.set_image(url=TRAINING_IMAGE)
        embed1.description = (
            f"> A training session is being hosted by {interaction.user.mention}. You have <t:{ten_min}:R> left to join the training.\n\n"
            f"<:MIAthumbtack1:1365681465806815282>  Training server code: `AXEGK`.\n\n"
            f"> Once in the training server, please do the following:"
        )
        embed1.add_field(
            name="<:MIAdot:1365679087078604840> Firearms",
            value="**Please equip one of the following:**\n> - M4A1\n> - Glock 17",
            inline=True
        )
        embed1.add_field(
            name="<:MIAdot:1365679087078604840>  Uniforms and vehicles",
            value="**Please equip the following uniform:**\n> - [HRM Standard Kit] \n\n**Please spawn one fo the following vehicles:**\n> - 2015 bullhorn prancer [HRM Patrol]\n> - Falcon Interceptor 2019 [HRM Utility]\n> - Chevlon Camion PPV 2000 [HRM Utility]",
            inline=True
        )
        embed2 = discord.Embed(color=TAN)
        embed2.set_image(url=BOTTOM_IMAGE)
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        view = TrainingVoteView(interaction.user.id)
        await channel.send(content=ping, embeds=[embed1, embed2], view=view)
        await interaction.response.send_message("Training vote started!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Training(bot))
