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

bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Глобальная проверка канала ───────────────────────────────────
COMMAND_GROUPS = {
    "music":      ["play", "pause", "resume", "skip", "stop", "queue", "nowplaying", "volume", "join"],
    "economy":    ["daily", "balance", "pay", "leaderboard", "shop", "buy", "shop_add", "shop_remove", "give_money", "take_money"],
    "moderation": ["kick", "ban", "unban", "mute", "unmute", "clear", "warn", "warns", "warn_remove", "warns_clear", "roleall", "roledown"],
    "profile":    ["me", "userinfo"],
}

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

# ─── Загрузка когов при старте (до on_ready) ──────────────────────
GUILD_ID = discord.Object(id=1307035051866853477)

async def setup_hook():
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.music")
    await bot.load_extension("cogs.security")
    await bot.load_extension("cogs.logs")
    await bot.load_extension("cogs.autorole")
    await bot.load_extension("cogs.welcome")
    await bot.load_extension("cogs.warns")
    await bot.load_extension("cogs.giveaway")
    await bot.load_extension("cogs.applications")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.profile")
    await bot.load_extension("cogs.channels")
    await bot.load_extension("cogs.help")
    bot.tree.copy_global_to(guild=GUILD_ID)
    await bot.tree.sync(guild=GUILD_ID)
    print("✅ Коги загружены, команды синхронизированы")

bot.setup_hook = setup_hook

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ У тебя нет прав для этой команды.", ephemeral=True)
    elif not interaction.response.is_done():
        await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user} (ID: {bot.user.id})")

    # ─── Отчёт об успешном перезапуске ────────────────────────────
    restart_file = "restart_pending.json"
    if os.path.exists(restart_file):
        try:
            with open(restart_file, "r") as f:
                data = json.load(f)
            channel = bot.get_channel(data["channel_id"])
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

bot.run(TOKEN)
