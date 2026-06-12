import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d %B %Y").replace(
        "January", "января").replace("February", "февраля").replace(
        "March", "марта").replace("April", "апреля").replace(
        "May", "мая").replace("June", "июня").replace(
        "July", "июля").replace("August", "августа").replace(
        "September", "сентября").replace("October", "октября").replace(
        "November", "ноября").replace("December", "декабря")


def time_ago(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    diff = now - dt
    days = diff.days
    if days == 0:
        return "сегодня"
    elif days == 1:
        return "вчера"
    elif days < 30:
        return f"{days} дн. назад"
    elif days < 365:
        m = days // 30
        return f"{m} мес. назад"
    else:
        y = days // 365
        return f"{y} г. назад"


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="me", description="Показать свой профиль")
    async def me(self, interaction: discord.Interaction):
        await self._show_profile(interaction, interaction.user)

    @app_commands.command(name="userinfo", description="Показать профиль участника")
    @app_commands.describe(member="Участник")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        await self._show_profile(interaction, member or interaction.user)

    async def _show_profile(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()

        guild = interaction.guild
        created_at = member.created_at
        joined_at = member.joined_at

        # Роли (без @everyone)
        roles = [r for r in member.roles if r != guild.default_role]
        roles.sort(key=lambda r: r.position, reverse=True)
        top_role = roles[0] if roles else None

        # Статусы
        status_icons = {
            discord.Status.online: "🟢 В сети",
            discord.Status.idle: "🟡 Не активен",
            discord.Status.dnd: "🔴 Не беспокоить",
            discord.Status.offline: "⚫ Не в сети",
        }
        status_text = status_icons.get(member.status, "⚫ Не в сети")

        # Активность
        activity_text = "Нет"
        if member.activity:
            act = member.activity
            if isinstance(act, discord.Game):
                activity_text = f"🎮 Играет в {act.name}"
            elif isinstance(act, discord.Streaming):
                activity_text = f"📺 Стримит {act.name}"
            elif isinstance(act, discord.Listening):
                activity_text = f"🎵 Слушает {act.title}"
            elif isinstance(act, discord.CustomActivity):
                activity_text = f"{act.emoji or ''} {act.name or ''}".strip()
            else:
                activity_text = act.name or "Нет"

        # Позиция на сервере (по дате входа)
        all_members = sorted([m for m in guild.members if m.joined_at], key=lambda m: m.joined_at)
        join_pos = next((i+1 for i, m in enumerate(all_members) if m.id == member.id), "?")

        # Флаги (значки)
        badges = []
        flags = member.public_flags
        if flags.staff: badges.append("👨‍💼 Discord Staff")
        if flags.partner: badges.append("🤝 Партнёр")
        if flags.hypesquad_balance: badges.append("⚖️ HypeSquad Balance")
        if flags.hypesquad_bravery: badges.append("🦁 HypeSquad Bravery")
        if flags.hypesquad_brilliance: badges.append("💎 HypeSquad Brilliance")
        if flags.early_supporter: badges.append("⭐ Ранний поддержатель")
        if flags.bug_hunter: badges.append("🐛 Bug Hunter")
        if flags.verified_bot_developer: badges.append("🤖 Разработчик ботов")
        if member.premium_since: badges.append("💜 Нитро Буст")

        # Embed
        embed = discord.Embed(color=top_role.color if top_role else discord.Color.blurple())

        # Заголовок
        name_parts = []
        if member.nick:
            name_parts.append(f"**{member.nick}**  {member.name}")
        else:
            name_parts.append(f"**{member.name}**")
        if top_role:
            name_parts.append(f"*{top_role.name}*")

        embed.set_author(
            name=" | ".join(name_parts),
            icon_url=member.display_avatar.url
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # Основная инфа
        embed.add_field(
            name="📅 Аккаунт создан",
            value=f"{format_dt(created_at)}\n*{time_ago(created_at)}*",
            inline=True
        )
        embed.add_field(
            name="📥 Вступил на сервер",
            value=f"{format_dt(joined_at)}\n*{time_ago(joined_at)}*",
            inline=True
        )
        embed.add_field(
            name="🏆 Позиция входа",
            value=f"#{join_pos} участник",
            inline=True
        )

        embed.add_field(name="📶 Статус", value=status_text, inline=True)
        embed.add_field(name="🎯 Активность", value=activity_text, inline=True)
        embed.add_field(name="🎨 Главная роль", value=top_role.mention if top_role else "Нет", inline=True)

        # Роли
        if roles:
            roles_text = " ".join(r.mention for r in roles[:15])
            if len(roles) > 15:
                roles_text += f" *+{len(roles)-15} ещё*"
            embed.add_field(name=f"🎭 Роли [{len(roles)}]", value=roles_text, inline=False)

        # Значки
        if badges:
            embed.add_field(name="🏅 Значки", value=" | ".join(badges), inline=False)

        embed.set_footer(text=f"ID: {member.id}")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
