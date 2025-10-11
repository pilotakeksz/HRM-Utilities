import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import pyttsx3
import tempfile
import os
import json

LOG_CHANNEL_ID = 1343686645815181382
YOUR_GUILD_ID = 1329908357812981882  # <-- Replace with your actual server ID!
LOGS_DIR = "logs"
DATA_DIR = "data"
NICKNAMES_FILE = os.path.join(DATA_DIR, "tts_nicknames.json")
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def log_action(bot, msg):
    # Log to file
    with open(os.path.join(LOGS_DIR, "tts.log"), "a", encoding="utf-8") as f:
        f.write(f"{msg}\n")
    # Log to Discord channel if available
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        asyncio.create_task(channel.send(msg))

def load_nicknames():
    if not os.path.exists(NICKNAMES_FILE):
        with open(NICKNAMES_FILE, "w") as f:
            json.dump({}, f)
    with open(NICKNAMES_FILE, "r") as f:
        return json.load(f)

def save_nicknames(nicks):
    with open(NICKNAMES_FILE, "w") as f:
        json.dump(nicks, f)

def tts_generate(text, filename):
    engine = pyttsx3.init()
    engine.save_to_file(text, filename)
    engine.runAndWait()

class TTSVoiceState:
    def __init__(self):
        self.voice_client: discord.VoiceClient = None
        self.text_channel: discord.TextChannel = None
        self.guild_id: int = None
        self.queue = asyncio.Queue()
        self.reading_task = None

class TextToSpeech(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}  # guild_id: TTSVoiceState
        self.nicknames = load_nicknames()

    @app_commands.command(name="join", description="Bot joins your voice channel and reads messages from this text channel.")
    @app_commands.guilds(discord.Object(id=YOUR_GUILD_ID))  # <-- Replace with your server ID!
    async def tts_join(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel.", ephemeral=True)
            log_action(self.bot, f"{interaction.user} tried /join but not in voice.")
            return
        voice_channel = interaction.user.voice.channel
        text_channel = interaction.channel

        guild_id = interaction.guild.id
        state = self.voice_states.get(guild_id)
        if state and state.voice_client and state.voice_client.is_connected():
            await interaction.response.send_message("Already connected in this server.", ephemeral=True)
            log_action(self.bot, f"{interaction.user} tried /join but already connected.")
            return

        vc = await voice_channel.connect()
        state = TTSVoiceState()
        state.voice_client = vc
        state.text_channel = text_channel
        state.guild_id = guild_id
        self.voice_states[guild_id] = state

        state.reading_task = self.bot.loop.create_task(self.tts_reader(state))
        await interaction.response.send_message(f"Joined {voice_channel.mention} and will read messages from {text_channel.mention}.", ephemeral=True)
        log_action(self.bot, f"Bot joined {voice_channel.name} for TTS in {text_channel.name}.")

    async def tts_reader(self, state: TTSVoiceState):
        while True:
            try:
                msg: discord.Message = await state.queue.get()
                nickname = self.nicknames.get(str(msg.author.id), msg.author.display_name)
                text = f"{nickname} says: {msg.content}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
                    tts_generate(text, tf.name)
                    audio_source = discord.FFmpegPCMAudio(tf.name)
                    state.voice_client.play(audio_source)
                    while state.voice_client.is_playing():
                        await asyncio.sleep(0.5)
                    os.unlink(tf.name)
                # Leave if alone
                if len(state.voice_client.channel.members) == 1:
                    await state.voice_client.disconnect()
                    log_action(self.bot, f"Bot left {state.voice_client.channel.name} (alone).")
                    break
            except Exception as e:
                log_action(self.bot, f"TTS error: {e}")
                continue

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        guild_id = getattr(message.guild, "id", None)
        if not guild_id or guild_id not in self.voice_states:
            return
        state = self.voice_states[guild_id]
        if state.text_channel and message.channel.id == state.text_channel.id:
            await state.queue.put(message)

    @app_commands.command(name="set_nickname", description="Set your TTS nickname.")
    @app_commands.guilds(discord.Object(id=YOUR_GUILD_ID))  # <-- Replace with your server ID!
    async def tts_set_nickname(self, interaction: discord.Interaction, nickname: str):
        self.nicknames[str(interaction.user.id)] = nickname
        save_nicknames(self.nicknames)
        await interaction.response.send_message(f"Your TTS nickname is now '{nickname}'.", ephemeral=True)
        log_action(self.bot, f"{interaction.user} set TTS nickname to '{nickname}'.")

    @app_commands.command(name="admin_set_nickname", description="Set TTS nickname for a user (admin only).")
    @app_commands.guilds(discord.Object(id=YOUR_GUILD_ID))  # <-- Replace with your server ID!
    async def tts_admin_set_nickname(self, interaction: discord.Interaction, user: discord.Member, nickname: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
            log_action(self.bot, f"{interaction.user} tried admin_set_nickname without permission.")
            return
        self.nicknames[str(user.id)] = nickname
        save_nicknames(self.nicknames)
        await interaction.response.send_message(f"Set TTS nickname for {user.mention} to '{nickname}'.", ephemeral=True)
        log_action(self.bot, f"{interaction.user} set TTS nickname for {user} to '{nickname}'.")

    @app_commands.command(name="admin_clear_nickname", description="Clear TTS nickname for a user (admin only).")
    @app_commands.guilds(discord.Object(id=YOUR_GUILD_ID))  # <-- Replace with your server ID!
    async def tts_admin_clear_nickname(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
            log_action(self.bot, f"{interaction.user} tried admin_clear_nickname without permission.")
            return
        self.nicknames.pop(str(user.id), None)
        save_nicknames(self.nicknames)
        await interaction.response.send_message(f"Cleared TTS nickname for {user.mention}.", ephemeral=True)
        log_action(self.bot, f"{interaction.user} cleared TTS nickname for {user}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(TextToSpeech(bot))