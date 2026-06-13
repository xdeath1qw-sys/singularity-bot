import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

WARNS_FILE = "warns.json"

_warns_cache: dict = {}

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

def load_warns(guild_id: int) -> dict:
    if not _warns_cache:
        _warns_cache.update(_load_file(WARNS_FILE))
    return _warns_cache.get(str(guild_id), {})

def save_warns(guild_id: int, warns: dict):
    if not _warns_cache:
        _warns_cache.update(_load_file(WARNS_FILE))
    _warns_cache[str(guild_id)] = warns
    _save_file(WARNS_FILE, _warns_cache)


class Warns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Выдать предупреждение участнику")
    @app_commands.describe(member="Участник", reason="Причина предупреждения")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
        if member == interaction.user:
            await interaction.response.send_message("❌ Нельзя варнить самого себя.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ Нельзя варнить бота.", ephemeral=True)
            return

        warns = load_warns(interaction.guild_id)
        user_id = str(member.id)

        if user_id not in warns:
            warns[user_id] = []

        warns[user_id].append({
            "reason": reason,
            "moderator_id": interaction.user.id,
            "moderator": str(interaction.user),
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        })

        save_warns(interaction.guild_id, warns)
        count = len(warns[user_id])

        embed = discord.Embed(title="⚠️ Предупреждение выдано", color=discord.Color.yellow())
        embed.add_field(name="Участник", value=member.mention)
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        embed.set_footer(text=f"Всего предупреждений: {count}")
        await interaction.response.send_message(embed=embed)

        # Уведомление в ЛС
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Вы получили предупреждение на сервере {interaction.guild.name}",
                color=discord.Color.yellow()
            )
            dm_embed.add_field(name="Причина", value=reason)
            dm_embed.add_field(name="Модератор", value=str(interaction.user))
            dm_embed.set_footer(text=f"Всего предупреждений: {count}")
            await member.send(embed=dm_embed)
        except Exception:
            pass

    @app_commands.command(name="warns", description="Посмотреть историю предупреждений участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns_list(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warns(interaction.guild_id)
        user_warns = warns.get(str(member.id), [])

        embed = discord.Embed(
            title=f"📋 Предупреждения — {member.display_name}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        if not user_warns:
            embed.description = "✅ Нет предупреждений"
        else:
            for i, w in enumerate(user_warns, 1):
                embed.add_field(
                    name=f"#{i} — {w['date']}",
                    value=f"**Причина:** {w['reason']}\n**Модератор:** {w['moderator']}",
                    inline=False
                )
        embed.set_footer(text=f"Всего: {len(user_warns)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="warn_remove", description="Удалить предупреждение у участника")
    @app_commands.describe(member="Участник", number="Номер предупреждения (из /warns)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_remove(self, interaction: discord.Interaction, member: discord.Member, number: int):
        warns = load_warns(interaction.guild_id)
        user_warns = warns.get(str(member.id), [])

        if not user_warns:
            await interaction.response.send_message("❌ У участника нет предупреждений.", ephemeral=True)
            return
        if number < 1 or number > len(user_warns):
            await interaction.response.send_message(f"❌ Укажи номер от 1 до {len(user_warns)}.", ephemeral=True)
            return

        removed = user_warns.pop(number - 1)
        warns[str(member.id)] = user_warns
        save_warns(interaction.guild_id, warns)

        await interaction.response.send_message(
            f"✅ Предупреждение #{number} удалено у {member.mention}.\n**Причина была:** {removed['reason']}",
            ephemeral=True
        )

    @app_commands.command(name="warns_clear", description="Очистить все предупреждения участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(administrator=True)
    async def warns_clear(self, interaction: discord.Interaction, member: discord.Member):
        warns = load_warns(interaction.guild_id)
        warns[str(member.id)] = []
        save_warns(interaction.guild_id, warns)
        await interaction.response.send_message(f"✅ Все предупреждения {member.mention} очищены.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Warns(bot))
