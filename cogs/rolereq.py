import discord
from discord.ext import commands

STAFF_CHANNEL_ID = 1329910558954098701  # Replace with your staff channel ID
REVIEWER_ROLE_ID = 1329910265264869387  # Only reviewers with this role can act

class RoleRequestModal(discord.ui.Modal, title="Role Request"):
    role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="Enter the role you want to request",
        required=True,
        max_length=100
    )
    proof_link = discord.ui.TextInput(
        label="Proof of Eligibility (image link)",
        placeholder="Paste a link to your proof image (Discord, Imgur, etc.)",
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
        embed = discord.Embed(
            title="New Role Request",
            description=f"**User:** {interaction.user.mention}\n"
                        f"**Role Requested:** {self.role_name.value}\n"
                        f"**Proof:** [Link]({self.proof_link.value})",
            color=discord.Color.blue()
        )
        embed.set_image(url=self.proof_link.value)
        # Store requester ID in footer for persistent view
        embed.set_footer(text=f"requester_id:{interaction.user.id}")
        if staff_channel and isinstance(staff_channel, discord.TextChannel):
            await staff_channel.send(embed=embed, view=RoleReviewView())
            await interaction.response.send_message("Your role request has been submitted to staff.", ephemeral=True)
        else:
            await interaction.response.send_message("Staff channel not found. Please contact an admin.", ephemeral=True)

class RoleReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="role_review_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Reviewer check
        if not any(r.id == REVIEWER_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review requests.", ephemeral=True)
            return

        # Get requester_id from embed footer
        requester_id = self._get_requester_id_from_embed(interaction)
        if requester_id is None:
            await interaction.response.send_message("Could not find requester ID.", ephemeral=True)
            return

        # Get decorative roles (no admin/permissions)
        guild = interaction.guild
        decorative_roles = [
            r for r in guild.roles
            if not r.permissions.administrator and not r.permissions.manage_roles and not r.permissions.kick_members and not r.permissions.ban_members and not r.managed and r < guild.me.top_role and r.name != "@everyone"
        ]
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in decorative_roles]

        if not options:
            await interaction.response.send_message("No decorative roles available.", ephemeral=True)
            return

        select = RoleSelect(options, requester_id)
        await interaction.response.send_message("Select a role to approve:", view=select, ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="role_review_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Reviewer check
        if not any(r.id == REVIEWER_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review requests.", ephemeral=True)
            return

        requester_id = self._get_requester_id_from_embed(interaction)
        if requester_id is None:
            await interaction.response.send_message("Could not find requester ID.", ephemeral=True)
            return

        await interaction.response.send_modal(DenyReasonModal(requester_id))

    def _get_requester_id_from_embed(self, interaction: discord.Interaction):
        # Try to get the embed from the message
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            if embed.footer and embed.footer.text and embed.footer.text.startswith("requester_id:"):
                try:
                    return int(embed.footer.text.split("requester_id:")[1])
                except Exception:
                    return None
        return None

class RoleSelect(discord.ui.View):
    def __init__(self, options, requester_id):
        super().__init__(timeout=120)
        self.requester_id = requester_id
        self.add_item(RoleDropdown(options, requester_id))

class RoleDropdown(discord.ui.Select):
    def __init__(self, options, requester_id):
        super().__init__(placeholder="Select a role to approve", options=options)
        self.requester_id = requester_id

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        member = interaction.guild.get_member(self.requester_id)
        role = interaction.guild.get_role(role_id)
        if member and role:
            await member.add_roles(role, reason="Role request approved")
            try:
                await member.send(f"✅ Your role request was approved! You have been given the **{role.name}** role.")
            except Exception:
                pass
            await interaction.response.send_message(f"Approved and added {role.name} to {member.mention}. User notified in DMs.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to add role.", ephemeral=True)

class DenyReasonModal(discord.ui.Modal, title="Deny Role Request"):
    reason = discord.ui.TextInput(
        label="Reason for denial",
        style=discord.TextStyle.paragraph,
        placeholder="Explain why this request is denied.",
        required=True,
        max_length=300
    )

    def __init__(self, requester_id):
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.requester_id)
        if member:
            try:
                await member.send(f"❌ Your role request was denied.\n**Reason:** {self.reason.value}")
            except Exception:
                pass
        await interaction.response.send_message("Denied and user notified in DMs.", ephemeral=True)

class RoleRequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register persistent view for review buttons
        self.bot.add_view(RoleReviewView())

    @discord.app_commands.command(name="role_request", description="Request a role from staff.")
    async def role_request(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RoleRequestModal())

async def setup(bot):
    await bot.add_cog(RoleRequestCog(bot))