import discord
import os
from datetime import datetime, timedelta
from discord.ext import commands

AUTOMOD_LOG_FILE = os.path.join("logs", "automod_protection.log")

LOG_CHANNEL_ID = 1329910577375482068
TIMEOUT_MINUTES = 10

phrases = ["Fuck","Asshat","Asshole","bitch","addhat","kys","cunt","belkend","bellen","bellend","nigger","nigga","wanker","goon","Dickhead","Gooner","hoe","dick","Twat","Mother fucker","shit head","Piss","Twit","Prat","Knob","Tosset","Butthead","Prick","Arse","Bastard","Tosser","Bullshit","Pussy","Dipshit","Fag","Whore","Bollocks","Bonehead","Bimbo","Airhead","Knobhead","faggot","Cumdumpster","Tit","Tits","Shitpouch","Pish","Juzzstain","Nonce","Cumwipe","Fanny","Zizzstain","Pisswizard","Duckweasle","DickWeasel","BAWBAG","Fuckwit","Fucka","Fuck00","Fuck22","Fuckq","Fucku","Cockwomble","Fucki","Cocka","Dicka"]

automodbypass = [911072161349918720, 840949634071658507, 735167992966676530]
bypassrole = 1329910230066401361

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.author.id in automodbypass:
            return

        if (message.author.id in automodbypass or any(role.id == bypassrole for role in message.author.roles)):
            return

        content = message.content.lower()
        
        if any(p in content for p in phrases):
            await message.delete()

            timeout_until = discord.utils.utcnow() + timedelta(minutes=TIMEOUT_MINUTES)

            await message.author.timeout(
                timeout_until,
                reason="MCNG utils automoderation"
            )

            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)

            embed = discord.Embed(
                title="Automod Triggered",
                description="User has been automatically muted.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="User",
                value=f"{message.author} ({message.author.id})",
                inline=False
            )
            embed.add_field(
                name="Channel",
                value=message.channel.mention,
                inline=False
            )
            embed.add_field(
                name="Timeout",
                value=f"{TIMEOUT_MINUTES} minutes",
                inline=False
            )
            embed.add_field(
                name="Message Content",
                value=message.content[:1000],
                inline=False
            )

            if log_channel:
                await log_channel.send(embed=embed)
                
async def setup(bot):
    await bot.add_cog(Automod(bot))
