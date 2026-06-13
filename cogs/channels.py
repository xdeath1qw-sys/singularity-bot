import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "channels_config.json"

# Группы команд
COMMAND_GROUPS = {
    "economy":   ["daily", "balance", "pay", "leaderboard", "shop", "buy", "shop_add", "shop_remove", "give_money", "take_money"],
    "moderation":["kick", "ban", "unban", "mute", "unmute", "clear", "warn", "warns", "warn_remove", "warns_clear", "roleall", "roledown"],
    "profile":   ["me", "userinfo"],
}

GROUP_NAMES = {
    "economy":    "💰 Экономика",
    "moderation": "🛡️ Модерация",
    "profile":    "👤 Профиль",
}

_config_cache: dict = {}

def _load_file(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_file(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_config(guild_id: int) -> dict:
    if not _config_cache:
        _config_cache.update(_load_file(CONFIG_FILE))
    return _config_cache.get(str(guild_id), {})

def save_config(guild_id: int, config: dict):
    if not _config_cache:
        _config_cache.update(_load_file(CONFIG_FILE))
    _config_cache[str(guild_id)] = config
    _save_file(CONFIG_FILE, _config_cache)


def get_allowed_channel(guild_id: int, command_name: str):
    """Возвращает channel_id если для команды задан канал, иначе None (разрешено везде)"""
    config = load_config(guild_id)
    for group, commands_list in COMMAND_GROUPS.items():
        if command_name in commands_list:
            return config.get(group)
    return None


class ChannelRestrict(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Вешаем глобальную проверку на все slash-команды
        bot.tree.error(self.on_app_command_error)

    async def interaction_check_channel(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return True

        cmd_name = interaction.command.name if interaction.command else None
        if not cmd_name:
            return True

        allowed_channel_id = get_allowed_channel(interaction.guild_id, cmd_name)
        if not allowed_channel_id:
            return True  # Канал не задан — разрешено везде

        if interaction.channel_id != allowed_channel_id:
            channel = interaction.guild.get_channel(allowed_channel_id)
            mention = channel.mention if channel else "специальном канале"
            await interaction.response.send_message(
                f"❌ Эту команду можно использовать только в {mention}",
                ephemeral=True
            )
            return False
        return True

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        pass  # Не перехватываем другие ошибки

    @app_commands.command(name="channel_set", description="Задать канал для группы команд")
    @app_commands.describe(
        group="Группа команд",
        channel="Канал где будут работать эти команды"
    )
    @app_commands.choices(group=[
        app_commands.Choice(name=name, value=key)
        for key, name in GROUP_NAMES.items()
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def channel_set(self, interaction: discord.Interaction, group: str, channel: discord.TextChannel):
        config = load_config(interaction.guild_id)
        config[group] = channel.id
        save_config(interaction.guild_id, config)

        cmds = ", ".join(f"`/{c}`" for c in COMMAND_GROUPS[group])
        embed = discord.Embed(
            title=f"✅ Канал для {GROUP_NAMES[group]} установлен",
            color=discord.Color.green()
        )
        embed.add_field(name="Канал", value=channel.mention)
        embed.add_field(name="Команды", value=cmds, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="channel_remove", description="Убрать ограничение канала для группы команд")
    @app_commands.describe(group="Группа команд")
    @app_commands.choices(group=[
        app_commands.Choice(name=name, value=key)
        for key, name in GROUP_NAMES.items()
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def channel_remove(self, interaction: discord.Interaction, group: str):
        config = load_config(interaction.guild_id)
        config.pop(group, None)
        save_config(interaction.guild_id, config)
        await interaction.response.send_message(
            f"✅ Ограничение канала для **{GROUP_NAMES[group]}** снято — команды работают везде.",
            ephemeral=True
        )

    @app_commands.command(name="channel_info", description="Показать настройки каналов команд")
    @app_commands.checks.has_permissions(administrator=True)
    async def channel_info(self, interaction: discord.Interaction):
        config = load_config(interaction.guild_id)
        embed = discord.Embed(title="📋 Каналы команд", color=discord.Color.blurple())

        for group, name in GROUP_NAMES.items():
            ch_id = config.get(group)
            ch = interaction.guild.get_channel(ch_id) if ch_id else None
            embed.add_field(
                name=name,
                value=ch.mention if ch else "Везде",
                inline=True
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ChannelRestrict(bot))
