import discord
from discord.ext import commands
import asyncio
import gtts
import os
from tempfile import NamedTemporaryFile

class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@commands.hybrid_command(name="tts", description="Speak a message in your current voice channel.")
async def tts(self, ctx, *, message: str):
    """Generate TTS and play it in the user's voice channel."""
    # Acknowledge immediately
    await ctx.defer()

    if not ctx.author.voice:
        return await ctx.reply("You must be in a voice channel to use TTS.")

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

    if not voice_client or not voice_client.is_connected():
        voice_client = await voice_channel.connect()

    try:
        from gtts import gTTS
        import os, asyncio
        from tempfile import NamedTemporaryFile

        tts = gTTS(message, lang="en")
        with NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
            tts.save(tmpfile.name)
            audio_path = tmpfile.name

        audio_source = discord.FFmpegPCMAudio(audio_path)
        voice_client.stop()
        voice_client.play(audio_source)

        await ctx.followup.send(f"🗣️ Speaking: `{message}`")

        while voice_client.is_playing():
            await asyncio.sleep(0.5)

    finally:
        if 'audio_path' in locals() and os.path.exists(audio_path):
            os.remove(audio_path)
        await voice_client.disconnect()

async def setup(bot):
    await bot.add_cog(TTSCog(bot))
