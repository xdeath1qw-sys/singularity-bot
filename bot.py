import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ─── Глобальная проверка канала ───────────────────────────────────
COMMAND_GROUPS = {
    "economy":    ["daily", "balance", "pay", "leaderboard", "shop", "buy", "shop_add", "shop_remove", "give_money", "take_money"],
    "moderation": ["kick", "ban", "unban", "mute", "unmute", "clear", "warn", "warns", "warn_remove", "warns_clear", "roleall", "roledown", "banall", "unbanall", "announce"],
    "profile":    ["me", "userinfo"],
}

GUILD_ID = discord.Object(id=1307035051866853477)


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.security")
        await self.load_extension("cogs.logs")
        await self.load_extension("cogs.autorole")
        await self.load_extension("cogs.welcome")
        await self.load_extension("cogs.warns")
        await self.load_extension("cogs.giveaway")
        await self.load_extension("cogs.applications")
        await self.load_extension("cogs.economy")
        await self.load_extension("cogs.profile")
        await self.load_extension("cogs.channels")
        await self.load_extension("cogs.help")
        # Глобальная синхронизация (работает на всех серверах)
        await self.tree.sync()
        print("✅ Коги загружены, команды синхронизированы глобально")

    async def on_ready(self):
        for vc in self.voice_clients:
            await vc.disconnect(force=True)
        print(f"✅ Бот запущен как {self.user} (ID: {self.user.id})")

        # Принудительная синхронизация команд
        try:
            synced = await self.tree.sync()
            print(f"✅ Синхронизировано {len(synced)} команд глобально")
            for cmd in synced:
                print(f"   /{cmd.name}")
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}")

        restart_file = "restart_pending.json"
        if os.path.exists(restart_file):
            try:
                with open(restart_file, "r") as f:
                    data = json.load(f)
                channel = self.get_channel(data["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(data["message_id"])
                        await msg.edit(content="✅ Перезапуск успешный! Бот снова онлайн.")
                    except Exception:
                        await channel.send("✅ Перезапуск успешный! Бот снова онлайн.")
            except Exception as e:
                print(f"Ошибка отчёта перезапуска: {e}")
            finally:
                os.remove(restart_file)


bot = MyBot()


async def check_channel(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return True
    cmd_name = interaction.command.name if interaction.command else None
    if not cmd_name:
        return True

    config_file = "channels_config.json"
    if not os.path.exists(config_file):
        return True
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = data.get(str(interaction.guild_id), {})
    except Exception:
        return True

    for group, cmds in COMMAND_GROUPS.items():
        if cmd_name in cmds:
            allowed_id = config.get(group)
            if allowed_id and interaction.channel_id != allowed_id:
                channel = interaction.guild.get_channel(allowed_id)
                mention = channel.mention if channel else "специальном канале"
                await interaction.response.send_message(
                    f"❌ Эту команду можно использовать только в {mention}",
                    ephemeral=True
                )
                return False
    return True

bot.tree.interaction_check = check_channel


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ У тебя нет прав для этой команды.", ephemeral=True)
    elif not interaction.response.is_done():
        await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


bot.run(TOKEN)
