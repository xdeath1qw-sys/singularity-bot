import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "autorole_config.json"


def load_config(guild_id: int) -> list:
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), [])


def save_config(guild_id: int, roles: list):
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    data[str(guild_id)] = roles
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        roles = load_config(member.guild.id)
        for role_id in roles:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Авто-роль при входе")
                except Exception:
                    pass

    @app_commands.command(name="autorole_add", description="Добавить авто-роль при входе")
    @app_commands.describe(role="Роль которая будет выдаваться при входе")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        roles = load_config(interaction.guild_id)
        if role.id in roles:
            await interaction.response.send_message(f"❌ Роль {role.mention} уже в списке авто-ролей.", ephemeral=True)
            return
        roles.append(role.id)
        save_config(interaction.guild_id, roles)
        await interaction.response.send_message(f"✅ Роль {role.mention} добавлена в авто-роли.", ephemeral=True)

    @app_commands.command(name="autorole_remove", description="Убрать авто-роль")
    @app_commands.describe(role="Роль которую нужно убрать")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        roles = load_config(interaction.guild_id)
        if role.id not in roles:
            await interaction.response.send_message(f"❌ Роль {role.mention} не найдена в авто-ролях.", ephemeral=True)
            return
        roles.remove(role.id)
        save_config(interaction.guild_id, roles)
        await interaction.response.send_message(f"✅ Роль {role.mention} убрана из авто-ролей.", ephemeral=True)

    @app_commands.command(name="autorole_list", description="Показать список авто-ролей")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_list(self, interaction: discord.Interaction):
        roles = load_config(interaction.guild_id)
        if not roles:
            await interaction.response.send_message("Авто-роли не настроены.", ephemeral=True)
            return
        mentions = []
        for role_id in roles:
            role = interaction.guild.get_role(role_id)
            mentions.append(role.mention if role else f"`{role_id}` (удалена)")
        embed = discord.Embed(title="🎭 Авто-роли при входе", color=discord.Color.blurple())
        embed.description = "\n".join(mentions)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
