import os
import discord
import json
from discord.ext import commands, tasks
from datetime import datetime

OWNER_ID = 840949634071658507
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "../backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

class RestoreMenu(discord.ui.View):
    def __init__(self, ctx, backup_path, data, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.backup_path = backup_path
        self.data = data
        self.cog = cog
        self.value = None

    @discord.ui.button(label="Restore Roles Only", style=discord.ButtonStyle.primary)
    async def roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._do_restore(self.ctx, self.data, restore_roles=True, restore_channels=False)
        await interaction.response.edit_message(content="Restored roles only!", view=None)

    @discord.ui.button(label="Restore Channels Only", style=discord.ButtonStyle.primary)
    async def channels_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._do_restore(self.ctx, self.data, restore_roles=False, restore_channels=True)
        await interaction.response.edit_message(content="Restored channels only!", view=None)

    @discord.ui.button(label="Restore Both", style=discord.ButtonStyle.success)
    async def both_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._do_restore(self.ctx, self.data, restore_roles=True, restore_channels=True)
        await interaction.response.edit_message(content="Restored roles and channels!", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Restore cancelled.", view=None)
        self.stop()

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_task.start()

    def cog_unload(self):
        self.backup_task.cancel()

    @tasks.loop(hours=24)
    async def backup_task(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.create_backup(guild)

    async def create_backup(self, guild):
        # Backup roles
        roles_data = []
        for role in guild.roles:
            if role.is_default():
                continue
            roles_data.append({
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
                "position": role.position
            })

        # Backup channels
        channels_data = []
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                ch_type = "category"
            elif isinstance(channel, discord.TextChannel):
                ch_type = "text"
            elif isinstance(channel, discord.VoiceChannel):
                ch_type = "voice"
            else:
                continue
            overwrites = {}
            for target, perms in channel.overwrites.items():
                overwrites[str(target.id)] = perms.pair()[0].value
            channels_data.append({
                "name": channel.name,
                "type": ch_type,
                "category": channel.category.name if channel.category else None,
                "position": channel.position,
                "overwrites": overwrites,
                "topic": getattr(channel, "topic", None),
                "nsfw": getattr(channel, "nsfw", False),
                "bitrate": getattr(channel, "bitrate", None),
                "user_limit": getattr(channel, "user_limit", None)
            })

        # Backup members and their roles (for logging only)
        members_log = []
        async for member in guild.fetch_members(limit=None):
            members_log.append(
                f"{member} ({member.id}): {[role.name for role in member.roles if not role.is_default()]}"
            )

        # Save backup files
        date_str = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        backup_json = {
            "guild_name": guild.name,
            "guild_id": guild.id,
            "roles": roles_data,
            "channels": channels_data,
            "date": date_str
        }
        backup_path = os.path.join(BACKUP_DIR, f"{guild.id}_backup_{date_str}.json")
        members_path = os.path.join(BACKUP_DIR, f"{guild.id}_members_{date_str}.txt")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_json, f, indent=2)
        with open(members_path, "w", encoding="utf-8") as f:
            f.write("\n".join(members_log))

    @commands.command(name="backup-now")
    @commands.is_owner()
    async def backup_now(self, ctx):
        """Manually trigger a backup."""
        await self.create_backup(ctx.guild)
        await ctx.send("Backup created and saved locally.")

    @commands.command(name="owner-backup-now")
    async def owner_backup_now(self, ctx):
        """Manually trigger a backup (owner only)."""
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return
        await self.create_backup(ctx.guild)
        await ctx.send("Backup created and saved locally (owner only).")

    @commands.command(name="restore-backup")
    async def restore_backup(self, ctx, backup_file: str):
        """Restore server structure from a local backup file. Owner only."""
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return

        backup_path = os.path.join(BACKUP_DIR, backup_file)
        if not os.path.exists(backup_path):
            await ctx.send("Backup file not found.")
            return

        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        view = RestoreMenu(ctx, backup_path, data, self)
        await ctx.send(
            "Select what you want to restore from the backup:",
            view=view
        )

    async def _do_restore(self, ctx, data, restore_roles=True, restore_channels=True):
        # Restore roles (create new roles)
        role_map = {}
        if restore_roles:
            roles_sorted = sorted(data["roles"], key=lambda r: r["position"])
            for role_data in roles_sorted:
                role = await ctx.guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data["color"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    permissions=discord.Permissions(role_data["permissions"])
                )
                role_map[role_data["name"]] = role

        category_map = {}
        if restore_channels:
            # Restore categories first
            for ch in data["channels"]:
                if ch["type"] == "category":
                    cat = await ctx.guild.create_category(
                        name=ch["name"],
                        position=ch["position"]
                    )
                    category_map[ch["name"]] = cat

            # Restore text and voice channels
            for ch in data["channels"]:
                if ch["type"] == "category":
                    continue
                overwrites = {}
                for target_id, perms_value in ch["overwrites"].items():
                    target = ctx.guild.get_role(int(target_id)) or ctx.guild.get_member(int(target_id))
                    if target:
                        overwrites[target] = discord.PermissionOverwrite.from_pair(
                            discord.Permissions(perms_value), discord.Permissions(0)
                        )
                category = category_map.get(ch["category"])
                if ch["type"] == "text":
                    await ctx.guild.create_text_channel(
                        name=ch["name"],
                        category=category,
                        position=ch["position"],
                        topic=ch["topic"],
                        nsfw=ch["nsfw"],
                        overwrites=overwrites
                    )
                elif ch["type"] == "voice":
                    await ctx.guild.create_voice_channel(
                        name=ch["name"],
                        category=category,
                        position=ch["position"],
                        bitrate=ch["bitrate"],
                        user_limit=ch["user_limit"],
                        overwrites=overwrites
                    )

        await ctx.send(
            f"Restore complete! (Roles: {'Yes' if restore_roles else 'No'}, Channels: {'Yes' if restore_channels else 'No'})"
            "\nNote: Members and their roles cannot be restored automatically."
        )

async def setup(bot):
    await bot.add_cog(BackupCog(bot))