import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "welcome_config.json"


def load_config(guild_id: int) -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(guild_id), {})
    except Exception:
        return {}


def save_config(guild_id: int, config: dict):
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[str(guild_id)] = config
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_text(template: str, member: discord.Member) -> str:
    return (template
        .replace("{user}", member.mention)
        .replace("{username}", str(member.name))
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
    )


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        config = load_config(member.guild.id)
        if not config.get("channel_id") or not config.get("message"):
            return

        channel = member.guild.get_channel(config["channel_id"])
        if not channel:
            return

        text = build_text(config["message"], member)
        image_url = config.get("image_url")

        embed = discord.Embed(
            description=f"## {text}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Участник #{member.guild.member_count}")
        if image_url:
            embed.set_image(url=image_url)

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

        # ─── ЛС участнику ─────────────────────────────────────────
        try:
            dm_embed = discord.Embed(
                description="## Приветствуем тебя в клане ꜱɪɴɢᴜʟᴀʀɪᴛʏ\nЖдем тебя в звонке 👋",
                color=discord.Color.green()
            )
            dm_embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else member.display_avatar.url)
            await member.send(embed=dm_embed)
        except Exception:
            pass

    @app_commands.command(name="welcome_set", description="Настроить приветствие")
    @app_commands.describe(
        channel="Канал для приветствий",
        message="Текст. Используй {user} {username} {server} {count}",
        image_url="Ссылка на картинку или GIF (необязательно)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_set(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        image_url: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        config = load_config(interaction.guild_id)
        config["channel_id"] = channel.id
        config["message"] = message
        if image_url:
            config["image_url"] = image_url
        elif "image_url" in config:
            del config["image_url"]
        save_config(interaction.guild_id, config)

        embed = discord.Embed(title="✅ Приветствие настроено", color=discord.Color.green())
        embed.add_field(name="Канал", value=channel.mention)
        embed.add_field(name="Текст", value=message, inline=False)
        if image_url:
            embed.add_field(name="Картинка", value=image_url, inline=False)
            embed.set_image(url=image_url)
        embed.add_field(
            name="Плейсхолдеры",
            value="`{user}` — тег\n`{username}` — имя\n`{server}` — сервер\n`{count}` — кол-во участников",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="welcome_image", description="Установить картинку или GIF для приветствия")
    @app_commands.describe(image_url="Ссылка на картинку или GIF (оставь пустым чтобы убрать)")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_image(self, interaction: discord.Interaction, image_url: str = None):
        await interaction.response.defer(ephemeral=True)
        config = load_config(interaction.guild_id)
        if image_url:
            config["image_url"] = image_url
            save_config(interaction.guild_id, config)
            embed = discord.Embed(title="✅ Картинка установлена", color=discord.Color.green())
            embed.set_image(url=image_url)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            config.pop("image_url", None)
            save_config(interaction.guild_id, config)
            await interaction.followup.send("✅ Картинка убрана.", ephemeral=True)

    @app_commands.command(name="welcome_disable", description="Отключить приветствия")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_disable(self, interaction: discord.Interaction):
        config = load_config(interaction.guild_id)
        config["channel_id"] = None
        save_config(interaction.guild_id, config)
        await interaction.response.send_message("✅ Приветствия отключены.", ephemeral=True)

    @app_commands.command(name="welcome_test", description="Проверить как выглядит приветствие")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_test(self, interaction: discord.Interaction):
        config = load_config(interaction.guild_id)
        if not config.get("message"):
            await interaction.response.send_message("❌ Приветствие не настроено. Используй `/welcome_set`", ephemeral=True)
            return

        text = build_text(config["message"], interaction.user)
        image_url = config.get("image_url")

        embed = discord.Embed(title=text, color=discord.Color.green())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Участник #{interaction.guild.member_count}")
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="welcome_info", description="Показать текущие настройки приветствия")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_info(self, interaction: discord.Interaction):
        config = load_config(interaction.guild_id)
        channel = interaction.guild.get_channel(config.get("channel_id") or 0)

        embed = discord.Embed(title="👋 Настройки приветствия", color=discord.Color.blurple())
        embed.add_field(name="Канал", value=channel.mention if channel else "❌ Не установлен")
        embed.add_field(name="Текст", value=config.get("message") or "❌ Не установлен", inline=False)
        image_url = config.get("image_url")
        embed.add_field(name="Картинка", value=image_url if image_url else "Не установлена", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
