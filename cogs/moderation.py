import discord
from discord.ext import commands
from discord import app_commands


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── /kick ────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Выгнать участника с сервера")
    @app_commands.describe(member="Участник которого нужно выгнать", reason="Причина")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
        if member == interaction.user:
            await interaction.response.send_message("❌ Ты не можешь выгнать самого себя.", ephemeral=True)
            return
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 Участник выгнан",
                color=discord.Color.orange()
            )
            embed.add_field(name="Участник", value=member.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ У меня нет прав выгнать этого участника.", ephemeral=True)

    # ─── /ban ─────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Забанить участника")
    @app_commands.describe(member="Участник которого нужно забанить", reason="Причина")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
        if member == interaction.user:
            await interaction.response.send_message("❌ Ты не можешь забанить самого себя.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="🔨 Участник забанен",
                color=discord.Color.red()
            )
            embed.add_field(name="Участник", value=member.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ У меня нет прав забанить этого участника.", ephemeral=True)

    # ─── /unban ───────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Разбанить участника по имени (User#1234)")
    @app_commands.describe(user="Имя пользователя в формате User#1234")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: str):
        banned_users = [entry async for entry in interaction.guild.bans()]
        for ban_entry in banned_users:
            if str(ban_entry.user) == user:
                await interaction.guild.unban(ban_entry.user)
                embed = discord.Embed(
                    title="✅ Участник разбанен",
                    color=discord.Color.green()
                )
                embed.add_field(name="Участник", value=ban_entry.user.mention)
                embed.add_field(name="Модератор", value=interaction.user.mention)
                await interaction.response.send_message(embed=embed)
                return
        await interaction.response.send_message(f"❌ Пользователь `{user}` не найден в банлисте.", ephemeral=True)

    # ─── /mute ────────────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Замутить участника (тайм-аут) в минутах")
    @app_commands.describe(member="Участник", minutes="Длительность в минутах", reason="Причина")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Не указана"):
        import datetime
        try:
            duration = datetime.timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            embed = discord.Embed(
                title="🔇 Участник замучен",
                color=discord.Color.dark_orange()
            )
            embed.add_field(name="Участник", value=member.mention)
            embed.add_field(name="Длительность", value=f"{minutes} мин.")
            embed.add_field(name="Причина", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ У меня нет прав замутить этого участника.", ephemeral=True)

    # ─── /unmute ──────────────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Снять мут с участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None)
            embed = discord.Embed(
                title="🔊 Мут снят",
                color=discord.Color.green()
            )
            embed.add_field(name="Участник", value=member.mention)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ У меня нет прав снять мут.", ephemeral=True)

    # ─── /roleall ─────────────────────────────────────────────────────
    @app_commands.command(name="roleall", description="Выдать роль всем участникам сервера")
    @app_commands.describe(role="Роль которую нужно выдать всем")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roleall(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(thinking=True)

        members = [m for m in interaction.guild.members if not m.bot and role not in m.roles]

        if not members:
            await interaction.followup.send(f"✅ У всех участников уже есть роль {role.mention}")
            return

        success = 0
        failed = 0

        for member in members:
            try:
                await member.add_roles(role, reason=f"[roleall] {interaction.user}")
                success += 1
            except Exception:
                failed += 1

        embed = discord.Embed(title="🎭 Роль выдана всем", color=discord.Color.green())
        embed.add_field(name="Роль", value=role.mention)
        embed.add_field(name="Успешно", value=str(success))
        if failed:
            embed.add_field(name="Не удалось", value=str(failed))
        embed.add_field(name="Выполнил", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    # ─── /roledown ────────────────────────────────────────────────────
    @app_commands.command(name="roledown", description="Снять роль у всех участников сервера")
    @app_commands.describe(role="Роль которую нужно снять у всех")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roledown(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(thinking=True)

        members = [m for m in interaction.guild.members if not m.bot and role in m.roles]

        if not members:
            await interaction.followup.send(f"✅ Ни у кого нет роли {role.mention}")
            return

        success = 0
        failed = 0

        for member in members:
            try:
                await member.remove_roles(role, reason=f"[roledown] {interaction.user}")
                success += 1
            except Exception:
                failed += 1

        embed = discord.Embed(title="🎭 Роль снята у всех", color=discord.Color.orange())
        embed.add_field(name="Роль", value=role.mention)
        embed.add_field(name="Успешно", value=str(success))
        if failed:
            embed.add_field(name="Не удалось", value=str(failed))
        embed.add_field(name="Выполнил", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)

    # ─── /lock ────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Закрыть канал (запретить писать всем)")
    @app_commands.describe(channel="Канал (по умолчанию текущий)", reason="Причина")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "Не указана"):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        try:
            await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
            embed = discord.Embed(title="🔒 Канал закрыт", color=discord.Color.red())
            embed.add_field(name="Канал", value=ch.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав управлять этим каналом.", ephemeral=True)

    # ─── /unlock ──────────────────────────────────────────────────────
    @app_commands.command(name="unlock", description="Открыть канал (разрешить писать всем)")
    @app_commands.describe(channel="Канал (по умолчанию текущий)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        overwrite = ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        try:
            await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            embed = discord.Embed(title="🔓 Канал открыт", color=discord.Color.green())
            embed.add_field(name="Канал", value=ch.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав управлять этим каналом.", ephemeral=True)

    # ─── /voicelock ───────────────────────────────────────────────────
    @app_commands.command(name="voicelock", description="Закрыть голосовой канал (запретить подключаться)")
    @app_commands.describe(channel="Голосовой канал", reason="Причина")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def voicelock(self, interaction: discord.Interaction, channel: discord.VoiceChannel, reason: str = "Не указана"):
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = False
        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
            embed = discord.Embed(title="🔒 Голосовой канал закрыт", color=discord.Color.red())
            embed.add_field(name="Канал", value=channel.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав управлять этим каналом.", ephemeral=True)

    # ─── /voiceunlock ─────────────────────────────────────────────────
    @app_commands.command(name="voiceunlock", description="Открыть голосовой канал")
    @app_commands.describe(channel="Голосовой канал")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def voiceunlock(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = None
        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            embed = discord.Embed(title="🔓 Голосовой канал открыт", color=discord.Color.green())
            embed.add_field(name="Канал", value=channel.mention)
            embed.add_field(name="Модератор", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав управлять этим каналом.", ephemeral=True)

    # ─── /slowmode ────────────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Установить медленный режим в канале")
    @app_commands.describe(seconds="Задержка в секундах (0 — выключить)", channel="Канал")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Укажи значение от 0 до 21600 секунд.", ephemeral=True)
            return
        try:
            await ch.edit(slowmode_delay=seconds)
            if seconds == 0:
                await interaction.response.send_message(f"✅ Медленный режим в {ch.mention} выключен.")
            else:
                await interaction.response.send_message(f"🐢 Медленный режим в {ch.mention}: **{seconds} сек.**")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)

    # ─── /clear ───────────────────────────────────────────────────────
    @app_commands.command(name="clear", description="Удалить сообщения в канале")
    @app_commands.describe(amount="Количество сообщений (1–100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int = 10):
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Укажи число от 1 до 100.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Удалено **{len(deleted)}** сообщений.", ephemeral=True)

    # ─── Обработка ошибок прав ────────────────────────────────────────
    @kick.error
    @ban.error
    @unban.error
    @mute.error
    @unmute.error
    @clear.error
    async def permission_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ У тебя нет прав для этой команды.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
