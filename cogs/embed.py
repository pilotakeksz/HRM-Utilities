import discord
from discord.ext import commands
from discord import app_commands

EMBED_CREATOR_ROLE = 1365703451220377642  # Replace with your role ID

class EmbedBuilderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.embed = discord.Embed(title="", description="", color=0x2f3136)
        self.add_item(SetTitleButton(self.embed))
        self.add_item(SetDescriptionButton(self.embed))
        self.add_item(SendEmbedButton(self.embed))

class SetTitleButton(discord.ui.Button):
    def __init__(self, embed):
        super().__init__(label="Set Title", style=discord.ButtonStyle.primary)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetTitleModal(self.embed, interaction.message))

class SetTitleModal(discord.ui.Modal, title="Set Embed Title"):
    title = discord.ui.TextInput(label="Title", required=True)

    def __init__(self, embed, message):
        super().__init__()
        self.embed = embed
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.title = self.title.value
        await self.message.edit(embed=self.embed, view=self.view)
        await interaction.response.defer()

class SetDescriptionButton(discord.ui.Button):
    def __init__(self, embed):
        super().__init__(label="Set Description", style=discord.ButtonStyle.primary)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetDescriptionModal(self.embed, interaction.message))

class SetDescriptionModal(discord.ui.Modal, title="Set Embed Description"):
    description = discord.ui.TextInput(label="Description", required=True)

    def __init__(self, embed, message):
        super().__init__()
        self.embed = embed
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.description = self.description.value
        await self.message.edit(embed=self.embed, view=self.view)
        await interaction.response.defer()

class SendEmbedButton(discord.ui.Button):
    def __init__(self, embed):
        super().__init__(label="Send Embed", style=discord.ButtonStyle.success)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.send(embed=self.embed)
        await interaction.response.send_message("Embed sent!", ephemeral=True)

class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Start the embed builder")
    async def embed(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(interaction.user.id)
        if not member or EMBED_CREATOR_ROLE not in [role.id for role in member.roles]:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        embed = discord.Embed(title="", description="", color=0x2f3136)
        view = EmbedBuilderView()
        await interaction.response.send_message("Embed builder", embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))
