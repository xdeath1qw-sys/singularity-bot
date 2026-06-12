import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from collections import defaultdict

WHITELIST_FILE = "whitelist.txt"
MAX_WARNINGS = 3  # Максимум предупреждений до снятия ролей

# Опасные права которые нельзя выдавать
DANGEROUS_PERMISSIONS = [
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "mention_everyone",
]

DANGEROUS_PERMS_RU = {
    "administrator": "Администратор",
    "ban_members": "Банить участников",
    "kick_members": "Кикать участников",
    "manage_guild": "Управлять сервером",
    "manage_roles": "Управлять ролями",
    "manage_channels": "Управлять каналами",
    "manage_webhooks": "Управлять вебхуками",
    "mention_everyone": "Упоминать всех",
}


def load_whitelist() -> set:
    try:
        with open(WHITELIST_FILE, "r") as f:
            return set(int(line.strip()) for line in f if line.strip().isdigit())
    except FileNotFoundError:
        return set()


def save_whitelist(whitelist: set):
    with open(WHITELIST_FILE, "w") as f:
        for uid in whitelist:
            f.write(f"{uid}\n")


class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.whitelist: set = load_whitelist()
        self.punished: set = set()
        self.warnings: dict = defaultdict(lambda: defaultdict(int))

    # ─── Получить лог-канал ───────────────────────────────────────
    async def get_log_channel(self, guild: discord.Guild):
        log_channel = discord.utils.get(guild.text_channels, name="security-log")
        if not log_channel:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    return ch
        return log_channel

    # ─── Снять все роли ───────────────────────────────────────────
    async def punish(self, guild: discord.Guild, user_id: int, reason: str):
        if user_id in self.punished:
            return
        if user_id in self.whitelist:
            return

        self.punished.add(user_id)

        member = guild.get_member(user_id)
        if member:
            try:
                roles_to_remove = [r for r in member.roles if r != guild.default_role and r.is_assignable()]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason=f"[SECURITY] {reason}")
            except Exception:
                pass

        # Лог
        log_channel = await self.get_log_channel(guild)
        if log_channel:
            embed = discord.Embed(title="🛡️ SECURITY — Роли сняты", color=discord.Color.red())
            embed.add_field(name="Пользователь", value=f"<@{user_id}> (`{user_id}`)")
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.set_footer(text="Антирейд защита")
            try:
                await log_channel.send(embed=embed)
            except Exception:
                pass

        await asyncio.sleep(60)
        self.punished.discard(user_id)

    # ─── Выдать предупреждение ────────────────────────────────────
    async def warn(self, guild: discord.Guild, user_id: int, reason: str):
        if user_id in self.whitelist:
            return
        if user_id in self.punished:
            return

        self.warnings[guild.id][user_id] += 1
        count = self.warnings[guild.id][user_id]

        log_channel = await self.get_log_channel(guild)
        if log_channel:
            embed = discord.Embed(
                title=f"⚠️ Предупреждение {count}/{MAX_WARNINGS}",
                color=discord.Color.yellow() if count < MAX_WARNINGS else discord.Color.red()
            )
            embed.add_field(name="Пользователь", value=f"<@{user_id}> (`{user_id}`)")
            embed.add_field(name="Причина", value=reason, inline=False)
            if count >= MAX_WARNINGS:
                embed.description = "🔴 Достигнут лимит — роли сняты!"
            embed.set_footer(text="Антирейд защита")
            try:
                await log_channel.send(embed=embed)
            except Exception:
                pass

        if count >= MAX_WARNINGS:
            self.warnings[guild.id][user_id] = 0
            await self.punish(guild, user_id, f"Превышен лимит предупреждений ({MAX_WARNINGS}): {reason}")

    # ══════════════════════════════════════════════════════════════
    # СОБЫТИЯ — МГНОВЕННОЕ СНЯТИЕ РОЛЕЙ
    # ══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Забанил участника ({user})")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            if entry.target.id == member.id:
                await self.punish(guild, entry.user.id, f"Кикнул участника ({member})")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Удалил канал ({channel.name})")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Удалил роль ({role.name})")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Создал вебхук в #{channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Создал канал → снять роли"""
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Создал канал ({channel.name})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Добавили бота → снять роли у того кто добавил"""
        if not member.bot:
            return
        guild = member.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.punish(guild, entry.user.id, f"Добавил бота ({member.name})")

    # ══════════════════════════════════════════════════════════════
    # СОБЫТИЯ — СИСТЕМА ПРЕДУПРЕЖДЕНИЙ
    # ══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return

        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        guild = after.guild

        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return

            # Выдал роль сам себе
            if entry.user.id == after.id:
                role_names = ", ".join(r.name for r in added_roles)
                await self.warn(guild, entry.user.id, f"Выдал себе роль: {role_names}")
            break

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Создал роль → предупреждение"""
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            await self.warn(guild, entry.user.id, f"Создал роль ({role.name})")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Выдал роли опасные права или права администратора → снять роли"""
        guild = after.guild

        # Проверяем какие права добавились
        added_perms = []
        for perm in DANGEROUS_PERMISSIONS:
            before_val = getattr(before.permissions, perm, False)
            after_val = getattr(after.permissions, perm, False)
            if not before_val and after_val:
                added_perms.append(DANGEROUS_PERMS_RU.get(perm, perm))

        if not added_perms:
            return

        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
            if entry.user.bot or entry.user.id == self.bot.user.id:
                return
            perms_str = ", ".join(added_perms)
            await self.punish(guild, entry.user.id, f"Выдал опасные права роли «{after.name}»: {perms_str}")

    # ══════════════════════════════════════════════════════════════
    # КОМАНДЫ УПРАВЛЕНИЯ
    # ══════════════════════════════════════════════════════════════

    @app_commands.command(name="whitelist_add", description="Добавить пользователя в вайтлист")
    @app_commands.describe(member="Пользователь")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelist_add(self, interaction: discord.Interaction, member: discord.Member):
        self.whitelist.add(member.id)
        save_whitelist(self.whitelist)
        await interaction.response.send_message(f"✅ {member.mention} добавлен в вайтлист.", ephemeral=True)

    @app_commands.command(name="whitelist_remove", description="Убрать пользователя из вайтлиста")
    @app_commands.describe(member="Пользователь")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelist_remove(self, interaction: discord.Interaction, member: discord.Member):
        self.whitelist.discard(member.id)
        save_whitelist(self.whitelist)
        await interaction.response.send_message(f"✅ {member.mention} убран из вайтлиста.", ephemeral=True)

    @app_commands.command(name="whitelist_list", description="Показать вайтлист")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelist_list(self, interaction: discord.Interaction):
        if not self.whitelist:
            await interaction.response.send_message("Вайтлист пуст.", ephemeral=True)
            return
        users = "\n".join(f"<@{uid}> (`{uid}`)" for uid in self.whitelist)
        embed = discord.Embed(title="🛡️ Вайтлист", description=users, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="warnings", description="Показать предупреждения участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(administrator=True)
    async def warnings_cmd(self, interaction: discord.Interaction, member: discord.Member):
        count = self.warnings[interaction.guild_id][member.id]
        await interaction.response.send_message(
            f"⚠️ {member.mention} имеет **{count}/{MAX_WARNINGS}** предупреждений.",
            ephemeral=True
        )

    @app_commands.command(name="warnings_clear", description="Сбросить предупреждения участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(administrator=True)
    async def warnings_clear(self, interaction: discord.Interaction, member: discord.Member):
        self.warnings[interaction.guild_id][member.id] = 0
        await interaction.response.send_message(f"✅ Предупреждения {member.mention} сброшены.", ephemeral=True)

    @app_commands.command(name="security_info", description="Показать настройки защиты")
    @app_commands.checks.has_permissions(administrator=True)
    async def security_info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛡️ Антирейд защита", color=discord.Color.blurple())
        embed.description = (
            "**🔴 Мгновенно снимает все роли:**\n"
            "🔨 Забанил участника\n"
            "👢 Кикнул участника\n"
            "🗑️ Удалил канал\n"
            "📁 Создал канал\n"
            "❌ Удалил роль\n"
            "🪝 Создал вебхук\n"
            "🤖 Добавил бота\n"
            "⚡ Выдал опасные права роли\n\n"
            f"**🟡 Предупреждения (макс. {MAX_WARNINGS}):**\n"
            "➕ Создал роль\n"
            "👤 Выдал себе роль\n"
            f"На {MAX_WARNINGS} предупреждении — снятие всех ролей\n"
        )
        wl = "\n".join(f"<@{uid}>" for uid in self.whitelist) if self.whitelist else "Пусто"
        embed.add_field(name="Вайтлист", value=wl, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Security(bot))
