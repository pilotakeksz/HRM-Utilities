import discord
from discord.ext import commands, tasks

PING_USER_ID = 735167992966676530
PING_CHANNEL_ID = 735167992966676530
PING_CHANNEL_MESSAGE = "https://tenor.com/view/borzoi-siren-dawg-with-the-light-on-him-sailorzoop-dog-gif-2844905554045249724"

class PingLoop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ping_task.start()

    def cog_unload(self):
        self.ping_task.cancel()

    @tasks.loop(seconds=5)
    async def ping_task(self):
        await self.bot.wait_until_ready()
        user = self.bot.get_user(PING_USER_ID)
        if not user:
            # If the user isn't cached, fetch them
            try:
                user = await self.bot.fetch_user(PING_USER_ID)
            except Exception:
                return
        
        if user:
            try:
                await user.send("""CONSTITUTION

du

GRAND-DUCHÉ DE LUXEMBOURG


Chapitre Ier.
Du Territoire et du Roi Grand-Duc.

Art. 1er.

Le Grand-Duché de Luxembourg forme un État indépendant, indivisible et inaliénable et perpétuellement neutre.


Art. 2.

Les limites et chefs-lieux des arrondissements judiciaires ou administratifs, des cantons et des communes ne peuvent être changés qu’en vertu d’une loi.


Art. 3.

La Couronne du Grand-Duché est héréditaire dans la famille de Nassau, conformément au pacte du 30 juin 1783, à l’art. 71 du traité de Vienne du 9 juin 1815 et à l’art. 1er du traité de Londres du 11 mai 1867.


Art. 4.

La personne du Roi Grand-Duc est sacrée et inviolable.


Art. 5.

Le Grand-Duc de Luxembourg est majeur à l’âge de dix-huit ans accomplis. Lorsqu’il prend les rênes du Gouvernement, il prête, aussitôt que possible, en présence de la Chambre des Députés ou d’une députation nommée par elle, le serment suivant :

« Je jure d’observer la Constitution et les lois du Grand-Duché de Luxembourg, de maintenir l’indépendance nationale et l’intégrité du territoire, ainsi que la liberté publique et individuelle, comme aussi les droits de tous et de chacun de Mes sujets, et d’employer à la conservation et à l’accroissement de la prospérité générale et particulière, ainsi que le doit un bon Souverain, tous les moyens que les lois mettent à Ma disposition.

Ainsi Dieu me soit en aide ! »""")
            except Exception:
                pass

        # Send message in the specified channel
        channel = self.bot.get_channel(PING_CHANNEL_ID)
        if channel:
            try:
                msg = await channel.send(PING_CHANNEL_MESSAGE)
                await msg.delete()
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(PingLoop(bot))