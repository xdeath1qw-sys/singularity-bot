import discord
from discord.ext import commands
from discord import app_commands
import json
import os

LOGS_CONFIG_FILE = "logs_config.json"

DEFAULT_CONFIG = {
    "channel_id": None,
    "events": {
        "member_join":      False,
        "member_leave":     False,
        "member_ban":       True,
        "member_unban":     True,
        "message_delete":   False,  # выключено
        "message_edit":     True,
        "role_create":      True,
        "role_delete":      True,
        "role_assign":      True,
        "channel_create":   True,
        "channel_delete":   True,
        "voice_join":       False,
        "voice_leave":      False,
        "nickname_change":  False,  # выключено
        "kick":             True,
    }
}

EVENT_NAMES = {
    "member_join":      "👋 Вход участника",
    "member_leave":     "🚪 Выход участника",
    "member_ban":       "🔨 Бан",
    "member_unban":     "✅ Разбан",
    "kick":             "👢 Кик",
    "message_delete":   "🗑️ Удаление сообщения",
    "message_edit":     "✏️ Редактирование сообщения",
    "role_create":      "➕ Создание роли",
    "role_delete":      "❌ Удаление роли",
    "role_assign":      "🎭 Выдача/снятие роли",
    "channel_create":   "📁 Создание канала",
    "channel_delete":   "🗂️ Удаление канала",
    "voice_join":       "🔊 Вход в голосовой канал",
    "voice_leave":      "🔇 Выход из голосового канала",
    "nickname_change":  "📝 Смена ника",
}


def load_config(guild_id: int) -> dict:
    if not os.path.exists(LOGS_CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    with open(LOGS_CONFIG_FILE, "r") as f:
        data = json.load(f)
    guild_data = data.get(str(guild_id), DEFAULT_CONFIG.copy())
    # Добавляем новые события если их нет
    for k, v in DEFAULT_CONFIG["events"].items():
        if k not in guild_data["events"]:
            guild_data["events"][k] = v
    return guild_data


def save_config(guild_id: int, config: dict):
    data = {}
    if os.path.exists(LOGS_CONFIG_FILE):
        with open(LOGS_CONFIG_FILE, "r") as f:
            data = json.load(f)
    data[str(guild_id)] = config
    with open(LOGS_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self, guild_id: int) -> dict:
        return load_config(guild_id)

    async def send_log(self, guild: discord.Guild, event: str, embed: discord.Embed):
        config = self.get_config(guild.id)
        if not config["events"].get(event, True):
            return
        channel_id = config.get("channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════
    # СОБЫТИЯ
    # ══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="👋 Участник зашёл",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Участник", value=f"{member.mention} (`{member}`) ")
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "R"), inline=False)
        embed.set_footer(text=f"Всего участников: {member.guild.member_count}")
        await self.send_log(member.guild, "member_join", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        # Проверяем кик
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                embed = discord.Embed(title="👢 Участник кикнут", color=discord.Color.orange())
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Участник", value=f"{member.mention} (`{member}`)")
                embed.add_field(name="Модератор", value=entry.user.mention)
                embed.add_field(name="Причина", value=entry.reason or "Не указана", inline=False)
                await self.send_log(guild, "kick", embed)
                return

        # Обычный выход
        embed = discord.Embed(title="🚪 Участник вышел", color=discord.Color.light_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Участник", value=f"{member.mention} (`{member}`)")
        embed.add_field(name="ID", value=member.id)
        roles = [r.mention for r in member.roles if r != guild.default_role]
        if roles:
            embed.add_field(name="Роли", value=" ".join(roles), inline=False)
        embed.set_footer(text=f"Всего участников: {guild.member_count}")
        await self.send_log(guild, "member_leave", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title="🔨 Участник забанен", color=discord.Color.red())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Пользователь", value=f"{user.mention} (`{user}`)")
        embed.add_field(name="ID", value=user.id)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            embed.add_field(name="Модератор", value=entry.user.mention)
            embed.add_field(name="Причина", value=entry.reason or "Не указана", inline=False)
        await self.send_log(guild, "member_ban", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title="✅ Участник разбанен", color=discord.Color.green())
        embed.add_field(name="Пользователь", value=f"{user.mention} (`{user}`)")
        embed.add_field(name="ID", value=user.id)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
            embed.add_field(name="Модератор", value=entry.user.mention)
        await self.send_log(guild, "member_unban", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        embed = discord.Embed(title="🗑️ Сообщение удалено", color=discord.Color.red())
        embed.add_field(name="Автор", value=f"{message.author.mention} (`{message.author}`)")
        embed.add_field(name="Канал", value=message.channel.mention)
        if message.content:
            embed.add_field(name="Содержимое", value=message.content[:1024], inline=False)
        await self.send_log(message.guild, "message_delete", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        embed = discord.Embed(title="✏️ Сообщение отредактировано", color=discord.Color.yellow())
        embed.add_field(name="Автор", value=f"{before.author.mention} (`{before.author}`)")
        embed.add_field(name="Канал", value=before.channel.mention)
        embed.add_field(name="До", value=before.content[:512] or "*пусто*", inline=False)
        embed.add_field(name="После", value=after.content[:512] or "*пусто*", inline=False)
        embed.add_field(name="Ссылка", value=f"[Перейти]({after.jump_url})", inline=False)
        await self.send_log(before.guild, "message_edit", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(title="➕ Роль создана", color=discord.Color.green())
        embed.add_field(name="Роль", value=f"{role.mention} (`{role.name}`)")
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            embed.add_field(name="Кто создал", value=entry.user.mention)
        await self.send_log(role.guild, "role_create", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(title="❌ Роль удалена", color=discord.Color.red())
        embed.add_field(name="Роль", value=f"`{role.name}`")
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            embed.add_field(name="Кто удалил", value=entry.user.mention)
        await self.send_log(role.guild, "role_delete", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(title="📁 Канал создан", color=discord.Color.green())
        embed.add_field(name="Канал", value=f"{channel.mention} (`{channel.name}`)")
        embed.add_field(name="Тип", value=str(channel.type))
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            embed.add_field(name="Кто создал", value=entry.user.mention)
        await self.send_log(channel.guild, "channel_create", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(title="🗂️ Канал удалён", color=discord.Color.red())
        embed.add_field(name="Канал", value=f"`{channel.name}`")
        embed.add_field(name="Тип", value=str(channel.type))
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            embed.add_field(name="Кто удалил", value=entry.user.mention)
        await self.send_log(channel.guild, "channel_delete", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            embed = discord.Embed(title="🔊 Вошёл в голосовой канал", color=discord.Color.green())
            embed.add_field(name="Участник", value=f"{member.mention} (`{member}`)")
            embed.add_field(name="Канал", value=after.channel.mention)
            await self.send_log(member.guild, "voice_join", embed)
        elif before.channel and not after.channel:
            embed = discord.Embed(title="🔇 Вышел из голосового канала", color=discord.Color.light_grey())
            embed.add_field(name="Участник", value=f"{member.mention} (`{member}`)")
            embed.add_field(name="Канал", value=before.channel.mention)
            await self.send_log(member.guild, "voice_leave", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Смена ника
        if before.nick != after.nick:
            embed = discord.Embed(title="📝 Смена никнейма", color=discord.Color.blurple())
            embed.add_field(name="Участник", value=f"{after.mention} (`{after}`)")
            embed.add_field(name="Было", value=before.nick or "*нет*")
            embed.add_field(name="Стало", value=after.nick or "*нет*")
            await self.send_log(after.guild, "nickname_change", embed)

        # Выдача/снятие ролей
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added or removed:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                embed = discord.Embed(title="🎭 Изменение ролей участника", color=discord.Color.blurple())
                embed.add_field(name="Участник", value=f"{after.mention} (`{after}`)")
                embed.add_field(name="Кто изменил", value=entry.user.mention)
                if added:
                    embed.add_field(name="➕ Добавлены", value=" ".join(r.mention for r in added), inline=False)
                if removed:
                    embed.add_field(name="➖ Сняты", value=" ".join(r.mention for r in removed), inline=False)
                await self.send_log(after.guild, "role_assign", embed)
                break

    # ══════════════════════════════════════════════════════════════
    # КОМАНДЫ
    # ══════════════════════════════════════════════════════════════

    @app_commands.command(name="logs_set", description="Установить канал для логов")
    @app_commands.describe(channel="Канал куда слать логи")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_set(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.get_config(interaction.guild_id)
        config["channel_id"] = channel.id
        save_config(interaction.guild_id, config)
        await interaction.response.send_message(f"✅ Логи будут отправляться в {channel.mention}", ephemeral=True)

    @app_commands.command(name="logs_disable", description="Отключить логи")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_disable(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild_id)
        config["channel_id"] = None
        save_config(interaction.guild_id, config)
        await interaction.response.send_message("✅ Логи отключены.", ephemeral=True)

    @app_commands.command(name="logs_toggle", description="Включить/выключить определённый тип логов")
    @app_commands.describe(event="Тип события")
    @app_commands.choices(event=[
        app_commands.Choice(name=name, value=key)
        for key, name in EVENT_NAMES.items()
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_toggle(self, interaction: discord.Interaction, event: str):
        config = self.get_config(interaction.guild_id)
        current = config["events"].get(event, True)
        config["events"][event] = not current
        save_config(interaction.guild_id, config)
        status = "✅ Включён" if not current else "❌ Выключен"
        await interaction.response.send_message(
            f"{status} лог: **{EVENT_NAMES.get(event, event)}**", ephemeral=True
        )

    @app_commands.command(name="logs_status", description="Показать статус всех логов")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_status(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild_id)
        channel_id = config.get("channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else None

        embed = discord.Embed(title="📋 Статус логов", color=discord.Color.blurple())
        embed.add_field(
            name="Канал логов",
            value=channel.mention if channel else "❌ Не установлен",
            inline=False
        )

        events_text = ""
        for key, name in EVENT_NAMES.items():
            enabled = config["events"].get(key, True)
            events_text += f"{'✅' if enabled else '❌'} {name}\n"

        embed.add_field(name="События", value=events_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Logs(bot))
