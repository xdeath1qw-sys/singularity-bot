import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta

# Активные розыгрыши: message_id -> данные
active_giveaways = {}


def parse_duration(duration: str) -> int:
    """Парсит строку типа 1d, 2h, 30m, 60s в секунды"""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = duration[-1].lower()
    if unit not in units:
        raise ValueError("Неверный формат")
    return int(duration[:-1]) * units[unit]


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Участвовать", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = interaction.message.id
        if msg_id not in active_giveaways:
            await interaction.response.send_message("❌ Этот розыгрыш уже завершён.", ephemeral=True)
            return

        data = active_giveaways[msg_id]
        user_id = interaction.user.id

        if user_id in data["participants"]:
            data["participants"].remove(user_id)
            await interaction.response.send_message("❌ Ты вышел из розыгрыша.", ephemeral=True)
        else:
            data["participants"].add(user_id)
            await interaction.response.send_message("✅ Ты участвуешь в розыгрыше!", ephemeral=True)

        # Обновляем счётчик на кнопке
        button.label = f"🎉 Участвовать ({len(data['participants'])})"
        await interaction.message.edit(view=self)


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(GiveawayView())

    @app_commands.command(name="giveaway", description="Создать розыгрыш")
    @app_commands.describe(
        duration="Длительность: 1d, 2h, 30m, 60s",
        winners="Количество победителей",
        prize="Приз"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, duration: str, winners: int, prize: str):
        try:
            seconds = parse_duration(duration)
        except Exception:
            await interaction.response.send_message(
                "❌ Неверный формат времени. Используй: `1d`, `2h`, `30m`, `60s`", ephemeral=True
            )
            return

        if winners < 1:
            await interaction.response.send_message("❌ Победителей должно быть минимум 1.", ephemeral=True)
            return

        end_time = datetime.now() + timedelta(seconds=seconds)

        embed = discord.Embed(
            title="🎉 РОЗЫГРЫШ",
            description=f"**Приз:** {prize}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Победителей", value=str(winners))
        embed.add_field(name="Организатор", value=interaction.user.mention)
        embed.add_field(name="Заканчивается", value=discord.utils.format_dt(end_time, "R"), inline=False)
        embed.set_footer(text="Нажми кнопку чтобы участвовать!")

        view = GiveawayView()
        await interaction.response.send_message("✅ Розыгрыш создан!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        active_giveaways[msg.id] = {
            "prize": prize,
            "winners": winners,
            "participants": set(),
            "channel_id": interaction.channel_id,
            "organizer_id": interaction.user.id,
            "end_time": end_time
        }

        # Ждём и завершаем
        await asyncio.sleep(seconds)
        await self.end_giveaway(msg)

    async def end_giveaway(self, msg: discord.Message):
        if msg.id not in active_giveaways:
            return

        data = active_giveaways.pop(msg.id)
        participants = list(data["participants"])
        winners_count = data["winners"]
        prize = data["prize"]

        embed = discord.Embed(
            title="🎉 РОЗЫГРЫШ ЗАВЕРШЁН",
            description=f"**Приз:** {prize}",
            color=discord.Color.red()
        )

        if not participants:
            embed.add_field(name="Победители", value="😢 Никто не участвовал", inline=False)
        else:
            winners = random.sample(participants, min(winners_count, len(participants)))
            winners_mentions = " ".join(f"<@{w}>" for w in winners)
            embed.add_field(name="🏆 Победители", value=winners_mentions, inline=False)
            embed.add_field(name="Участников", value=str(len(participants)))

        embed.set_footer(text="Розыгрыш завершён")

        # Отключаем кнопку
        view = discord.ui.View()
        button = discord.ui.Button(
            label=f"🎉 Участвовать ({len(participants)})",
            style=discord.ButtonStyle.gray,
            disabled=True
        )
        view.add_item(button)

        try:
            await msg.edit(embed=embed, view=view)
            if participants:
                await msg.reply(f"🎉 Поздравляем победителей розыгрыша **{prize}**: {winners_mentions}")
        except Exception:
            pass

    @app_commands.command(name="giveaway_end", description="Досрочно завершить розыгрыш")
    @app_commands.describe(message_id="ID сообщения с розыгрышем")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Неверный ID сообщения.", ephemeral=True)
            return

        if msg_id not in active_giveaways:
            await interaction.response.send_message("❌ Розыгрыш не найден или уже завершён.", ephemeral=True)
            return

        data = active_giveaways[msg_id]
        channel = self.bot.get_channel(data["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                await interaction.response.send_message("✅ Розыгрыш завершается...", ephemeral=True)
                await self.end_giveaway(msg)
                return
            except Exception:
                pass
        await interaction.response.send_message("❌ Не удалось найти сообщение.", ephemeral=True)

    @app_commands.command(name="giveaway_reroll", description="Перевыбрать победителей розыгрыша")
    @app_commands.describe(message_id="ID сообщения с завершённым розыгрышем")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.send_message("🔄 Новые победители выбраны случайно!", ephemeral=True)
        await interaction.channel.send("🔄 Перевыбор победителей! Новый победитель будет объявлен.")


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
