import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os


class RestartButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="🔄 Перезапустить бота", style=discord.ButtonStyle.danger)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только администратор может перезапустить бота.", ephemeral=True)
            return

        await interaction.response.send_message("🔄 Перезапуск через **3**...", ephemeral=True)
        msg = await interaction.original_response()

        for vc in self.bot.voice_clients:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass

        await asyncio.sleep(1)
        await msg.edit(content="🔄 Перезапуск через **2**...")
        await asyncio.sleep(1)
        await msg.edit(content="🔄 Перезапуск через **1**...")
        await asyncio.sleep(1)
        await msg.edit(content="⏳ Перезапуск...")

        import json
        restart_data = {
            "channel_id": interaction.channel_id,
            "message_id": msg.id,
            "guild_id": interaction.guild_id
        }
        with open("restart_pending.json", "w") as f:
            json.dump(restart_data, f)

        os._exit(42)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Показать все команды бота")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Список всех команд",
            description="Полный список команд бота по категориям.",
            color=discord.Color.blurple()
        )

        # ─── Модерация ────────────────────────────────────────────────
        embed.add_field(
            name="🛡️ Модерация",
            value=(
                "`/kick <участник> [причина]` — Выгнать\n"
                "`/ban <участник> [причина]` — Забанить\n"
                "`/unban <User#1234>` — Разбанить\n"
                "`/mute <участник> [минуты] [причина]` — Замутить\n"
                "`/unmute <участник>` — Снять мут\n"
                "`/clear [кол-во]` — Удалить сообщения (1–100)\n"
                "`/roleall <роль>` — Выдать роль всем\n"
                "`/roledown <роль>` — Снять роль у всех\n"
                "`/lock [канал] [причина]` — Закрыть текстовый канал\n"
                "`/unlock [канал]` — Открыть текстовый канал\n"
                "`/voicelock <канал> [причина]` — Закрыть войс\n"
                "`/voiceunlock <канал>` — Открыть войс\n"
                "`/slowmode <секунды> [канал]` — Медленный режим"
            ),
            inline=False
        )

        # ─── Предупреждения ───────────────────────────────────────────
        embed.add_field(
            name="⚠️ Предупреждения",
            value=(
                "`/warn <участник> [причина]` — Выдать варн\n"
                "`/warns <участник>` — История варнов\n"
                "`/warn_remove <участник> <номер>` — Удалить варн\n"
                "`/warns_clear <участник>` — Очистить все варны"
            ),
            inline=False
        )

        # ─── Музыка ───────────────────────────────────────────────────
        embed.add_field(
            name="🎵 Музыка",
            value=(
                "`/join` — Зайти в голосовой канал\n"
                "`/play <запрос> [платформа]` — Играть трек\n"
                "`/pause` — Пауза\n"
                "`/resume` — Продолжить\n"
                "`/skip` — Пропустить трек\n"
                "`/stop` — Остановить и выйти\n"
                "`/queue` — Очередь треков\n"
                "`/nowplaying` — Текущий трек\n"
                "`/volume <0–100>` — Громкость\n"
                "Платформы: YouTube, SoundCloud, Spotify, Яндекс"
            ),
            inline=False
        )

        # ─── Антирейд защита ──────────────────────────────────────────
        embed.add_field(
            name="🔒 Антирейд защита",
            value=(
                "`/whitelist_add <участник>` — В вайтлист\n"
                "`/whitelist_remove <участник>` — Из вайтлиста\n"
                "`/whitelist_list` — Показать вайтлист\n"
                "`/warnings <участник>` — Предупреждения\n"
                "`/warnings_clear <участник>` — Сбросить\n"
                "`/security_info` — Настройки защиты\n"
                "⚡ Авто: бан/кик/удал. канала/роли/вебхук → снятие ролей"
            ),
            inline=False
        )

        # ─── Логи ─────────────────────────────────────────────────────
        embed.add_field(
            name="📋 Логи",
            value=(
                "`/logs_set <канал>` — Канал для логов\n"
                "`/logs_disable` — Отключить логи\n"
                "`/logs_toggle <событие>` — Вкл/выкл событие\n"
                "`/logs_status` — Статус логов"
            ),
            inline=False
        )

        # ─── Авто-роли ────────────────────────────────────────────────
        embed.add_field(
            name="🎭 Авто-роли",
            value=(
                "`/autorole_add <роль>` — Добавить авто-роль\n"
                "`/autorole_remove <роль>` — Убрать авто-роль\n"
                "`/autorole_list` — Список авто-ролей"
            ),
            inline=False
        )

        # ─── Приветствия ──────────────────────────────────────────────
        embed.add_field(
            name="👋 Приветствия",
            value=(
                "`/welcome_set <канал> <текст> [картинка]` — Настроить\n"
                "`/welcome_image [ссылка]` — Установить картинку/GIF\n"
                "`/welcome_disable` — Отключить\n"
                "`/welcome_test` — Проверить\n"
                "`/welcome_info` — Настройки\n"
                "Плейсхолдеры: `{user}` `{username}` `{server}` `{count}`"
            ),
            inline=False
        )

        # ─── Розыгрыши ────────────────────────────────────────────────
        embed.add_field(
            name="🎉 Розыгрыши",
            value=(
                "`/giveaway <время> <победителей> <приз>` — Создать\n"
                "`/giveaway_end <id>` — Завершить досрочно\n"
                "`/giveaway_reroll <id>` — Перевыбрать победителей\n"
                "Время: `1d` `2h` `30m` `60s`"
            ),
            inline=False
        )

        # ─── Заявки ───────────────────────────────────────────────────
        embed.add_field(
            name="📋 Заявки",
            value=(
                "`/app_setup <канал_заявок> <канал_кнопки> [картинка]` — Панель\n"
                "`/app_channel <тип> <канал> [роль]` — Канал для типа\n"
                "`/app_questions <тип> <вопросы>` — Изменить вопросы\n"
                "`/app_info` — Настройки заявок"
            ),
            inline=False
        )

        # ─── Экономика ────────────────────────────────────────────────
        embed.add_field(
            name="💰 Экономика",
            value=(
                "`/daily` — Ежедневная награда (100 монет)\n"
                "`/balance [участник]` — Баланс\n"
                "`/pay <участник> <сумма>` — Перевести монеты\n"
                "`/leaderboard` — Топ богатейших\n"
                "`/shop` — Магазин ролей\n"
                "`/buy <роль>` — Купить роль\n"
                "`/shop_add <роль> <цена>` — Добавить в магазин 🔑\n"
                "`/shop_remove <роль>` — Убрать из магазина 🔑\n"
                "`/give_money <участник> <сумма>` — Выдать монеты 🔑\n"
                "`/take_money <участник> <сумма>` — Снять монеты 🔑"
            ),
            inline=False
        )

        # ─── Профиль ──────────────────────────────────────────────────
        embed.add_field(
            name="👤 Профиль",
            value=(
                "`/me` — Твоя карточка профиля\n"
                "`/userinfo [участник]` — Профиль участника"
            ),
            inline=False
        )

        # ─── Каналы команд ────────────────────────────────────────────
        embed.add_field(
            name="📌 Каналы команд",
            value=(
                "`/channel_set <группа> <канал>` — Задать канал\n"
                "`/channel_remove <группа>` — Убрать ограничение\n"
                "`/channel_info` — Настройки каналов\n"
                "Группы: `music` `economy` `moderation` `profile`"
            ),
            inline=False
        )

        embed.set_footer(text="🔑 — только для администраторов  |  💡 Музыка — нужно быть в голосовом канале")

        view = None
        if interaction.user.guild_permissions.administrator:
            view = RestartButton(self.bot)

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))
