import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
import re

# ─── Префиксы поиска по платформам ───────────────────────────────
SEARCH_PREFIXES = {
    "youtube":    "ytsearch:",
    "soundcloud": "scsearch:",
    "yandex":     "ytsearch:",
    "spotify":    "ytsearch:",
}

PLATFORM_ICONS = {
    "youtube":    "🎬 YouTube",
    "soundcloud": "🔶 SoundCloud",
    "yandex":     "🎵 Яндекс.Музыка",
    "spotify":    "🟢 Spotify",
    "auto":       "🎵 Авто",
}

# ─── Определяем платформу по ссылке ──────────────────────────────
def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "soundcloud.com" in url:
        return "soundcloud"
    if "spotify.com" in url:
        return "spotify"
    if "music.yandex" in url or "yandex.ru/music" in url:
        return "yandex"
    if "bandcamp.com" in url:
        return "bandcamp"
    if "twitch.tv" in url:
        return "twitch"
    if "vk.com" in url:
        return "vk"
    return "direct"

# ─── Порядок попыток для авто-режима ─────────────────────────────
AUTO_SEARCH_ORDER = [
    "ytsearch:",   # YouTube
    "scsearch:",   # SoundCloud
]

_ytdl_opts: dict = {
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "geo_bypass": True,
    "age_limit": 99,
    "extractor_args": {
        "youtube": {
            "player_client": ["ios", "web"],
        }
    },
}
if os.path.exists("cookies.txt"):
    _ytdl_opts["cookiefile"] = "cookies.txt"

YTDL_OPTIONS = _ytdl_opts

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn -ar 48000 -ac 2 -ab 192k",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


def is_url(query: str) -> bool:
    return query.startswith("http://") or query.startswith("https://")


def build_query(query: str, platform: str) -> str:
    if is_url(query):
        return query
    # Spotify ссылка — вытащим название трека и ищем на YT
    prefix = SEARCH_PREFIXES.get(platform, "ytsearch:")
    return f"{prefix}{query}"


def extract_spotify_query(url: str) -> str:
    """Пытается вытащить название трека из Spotify URL через yt-dlp"""
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "")
            artist = info.get("artist") or info.get("uploader", "")
            if artist and title:
                return f"{artist} - {title}"
            return title
    except Exception:
        return ""


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Неизвестно")
        self.url = data.get("webpage_url", "")
        self.thumbnail = data.get("thumbnail", "")
        self.duration = data.get("duration", 0)
        self.uploader = data.get("uploader", "")
        self.extractor = data.get("extractor", "")

    @classmethod
    async def from_query(cls, query: str, platform: str = "auto", *, stream=True):
        loop = asyncio.get_event_loop()

        # ── Прямая ссылка ──────────────────────────────────────────
        if is_url(query):
            detected = detect_platform(query)

            # Spotify ссылка — конвертируем в поиск по YT
            if detected == "spotify":
                spotify_query = await loop.run_in_executor(None, lambda: extract_spotify_query(query))
                if spotify_query:
                    search = f"ytsearch:{spotify_query}"
                else:
                    # fallback: просто пробуем через yt-dlp напрямую
                    search = query
            else:
                search = query

            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(search, download=not stream)
            )
            if data and "entries" in data:
                data = data["entries"][0]
            if not data:
                raise Exception("Не удалось получить информацию о треке")
            filename = data["url"] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

        # ── Авто-режим: пробуем YT → SoundCloud ───────────────────
        if platform == "auto":
            last_error = None
            for prefix in AUTO_SEARCH_ORDER:
                try:
                    search = f"{prefix}{query}"
                    data = await loop.run_in_executor(
                        None, lambda s=search: ytdl.extract_info(s, download=not stream)
                    )
                    if data and "entries" in data:
                        data = data["entries"][0]
                    if data:
                        filename = data["url"] if stream else ytdl.prepare_filename(data)
                        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
                except Exception as e:
                    last_error = e
                    continue
            raise Exception(f"Не найдено ни на одной платформе. Последняя ошибка: {last_error}")

        # ── Конкретная платформа ───────────────────────────────────
        search = build_query(query, platform)
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(search, download=not stream)
        )
        if data and "entries" in data:
            data = data["entries"][0]
        if not data:
            raise Exception("Трек не найден")
        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, list] = {}
        self.current: dict[int, YTDLSource] = {}

    def get_queue(self, guild_id: int) -> list:
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def format_duration(self, seconds: int) -> str:
        if not seconds:
            return "?"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    def make_embed(self, source: YTDLSource, title: str = "🎵 Сейчас играет") -> discord.Embed:
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.description = f"[{source.title}]({source.url})" if source.url else source.title
        embed.add_field(name="Длительность", value=self.format_duration(source.duration))
        if source.uploader:
            embed.add_field(name="Автор", value=source.uploader)
        # Показываем источник
        extractor = source.extractor.lower() if source.extractor else ""
        if "youtube" in extractor:
            embed.add_field(name="Источник", value="🎬 YouTube")
        elif "soundcloud" in extractor:
            embed.add_field(name="Источник", value="🔶 SoundCloud")
        elif "bandcamp" in extractor:
            embed.add_field(name="Источник", value="🎸 Bandcamp")
        elif "twitch" in extractor:
            embed.add_field(name="Источник", value="🟣 Twitch")
        elif "vk" in extractor:
            embed.add_field(name="Источник", value="💙 VK")
        if source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)
        return embed

    # ─── /join ────────────────────────────────────────────────────────
    @app_commands.command(name="join", description="Зайти в голосовой канал")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Ты не в голосовом канале.", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        await interaction.response.send_message(f"✅ Подключился к **{channel.name}**")

    # ─── /play ────────────────────────────────────────────────────────
    @app_commands.command(name="play", description="Играть музыку — название, ссылка (YT, SC, Spotify, Bandcamp, VK, Twitch...)")
    @app_commands.describe(
        query="Название трека, ссылка на YouTube/SoundCloud/Spotify/Bandcamp/VK/Twitch и др.",
        platform="Платформа поиска (по умолчанию Авто — YT→SC)"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="🎵 Авто (YouTube → SoundCloud)", value="auto"),
        app_commands.Choice(name="🎬 YouTube", value="youtube"),
        app_commands.Choice(name="🔶 SoundCloud", value="soundcloud"),
        app_commands.Choice(name="🟢 Spotify (поиск через YT)", value="spotify"),
        app_commands.Choice(name="🎵 Яндекс.Музыка (поиск через YT)", value="yandex"),
    ])
    async def play(self, interaction: discord.Interaction, query: str, platform: str = "auto"):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Сначала зайди в голосовой канал.", ephemeral=True)
            return

        await interaction.response.defer()

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        queue = self.get_queue(interaction.guild_id)

        if vc.is_playing() or vc.is_paused():
            queue.append((query, platform))
            icon = PLATFORM_ICONS.get(platform, "🎵")
            await interaction.followup.send(f"➕ Добавлено в очередь [{icon}]: **{query}** (позиция {len(queue)})")
            return

        try:
            source = await YTDLSource.from_query(query, platform)
        except Exception as e:
            await interaction.followup.send(f"❌ Не удалось загрузить: `{e}`")
            return

        self.current[interaction.guild_id] = source

        def after_playing(error):
            if error:
                print(f"Ошибка плеера: {error}")
            asyncio.run_coroutine_threadsafe(
                self.play_next(interaction.guild_id, interaction.channel), self.bot.loop
            )

        vc.play(source, after=after_playing)
        await interaction.followup.send(embed=self.make_embed(source))

    async def play_next(self, guild_id: int, channel):
        queue = self.get_queue(guild_id)
        if not queue:
            self.current.pop(guild_id, None)
            return

        query, platform = queue.pop(0)
        vc = discord.utils.get(self.bot.voice_clients, guild__id=guild_id)
        if not vc or not vc.is_connected():
            self.current.pop(guild_id, None)
            self.queues[guild_id] = []
            return

        try:
            source = await YTDLSource.from_query(query, platform)
        except Exception as e:
            await channel.send(f"❌ Не удалось загрузить трек: `{e}`")
            await self.play_next(guild_id, channel)
            return

        self.current[guild_id] = source

        def after_playing(error):
            if error:
                print(f"Ошибка плеера: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild_id, channel), self.bot.loop)

        vc.play(source, after=after_playing)
        await channel.send(embed=self.make_embed(source))

    # ─── /pause ───────────────────────────────────────────────────────
    @app_commands.command(name="pause", description="Поставить музыку на паузу")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Музыка на паузе.")
        else:
            await interaction.response.send_message("❌ Сейчас ничего не играет.", ephemeral=True)

    # ─── /resume ──────────────────────────────────────────────────────
    @app_commands.command(name="resume", description="Продолжить воспроизведение")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Воспроизведение продолжено.")
        else:
            await interaction.response.send_message("❌ Музыка не на паузе.", ephemeral=True)

    # ─── /skip ────────────────────────────────────────────────────────
    @app_commands.command(name="skip", description="Пропустить текущий трек")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Трек пропущен.")
        else:
            await interaction.response.send_message("❌ Сейчас ничего не играет.", ephemeral=True)

    # ─── /stop ────────────────────────────────────────────────────────
    @app_commands.command(name="stop", description="Остановить музыку и очистить очередь")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.queues[interaction.guild_id] = []
            self.current.pop(interaction.guild_id, None)
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("⏹️ Музыка остановлена, бот покинул канал.")
        else:
            await interaction.response.send_message("❌ Бот не в голосовом канале.", ephemeral=True)

    # ─── /queue ───────────────────────────────────────────────────────
    @app_commands.command(name="queue", description="Показать очередь треков")
    async def queue_list(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild_id)
        current = self.current.get(interaction.guild_id)

        embed = discord.Embed(title="📋 Очередь", color=discord.Color.blurple())

        if current:
            embed.add_field(
                name="🎵 Сейчас играет",
                value=f"[{current.title}]({current.url})" if current.url else current.title,
                inline=False
            )
        else:
            embed.add_field(name="🎵 Сейчас играет", value="Ничего", inline=False)

        if queue:
            tracks = "\n".join(
                f"`{i+1}.` {PLATFORM_ICONS.get(p, '🎵')} {q}"
                for i, (q, p) in enumerate(queue[:10])
            )
            if len(queue) > 10:
                tracks += f"\n...и ещё {len(queue) - 10} треков"
            embed.add_field(name="📜 Следующие треки", value=tracks, inline=False)
        else:
            embed.add_field(name="📜 Следующие треки", value="Очередь пуста", inline=False)

        await interaction.response.send_message(embed=embed)

    # ─── /volume ──────────────────────────────────────────────────────
    @app_commands.command(name="volume", description="Установить громкость (0–100)")
    @app_commands.describe(level="Уровень громкости от 0 до 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if level < 0 or level > 100:
            await interaction.response.send_message("❌ Укажи значение от 0 до 100.", ephemeral=True)
            return
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
            await interaction.response.send_message(f"🔊 Громкость установлена: **{level}%**")
        else:
            await interaction.response.send_message("❌ Сейчас ничего не играет.", ephemeral=True)

    # ─── /nowplaying ──────────────────────────────────────────────────
    @app_commands.command(name="nowplaying", description="Показать текущий трек")
    async def nowplaying(self, interaction: discord.Interaction):
        current = self.current.get(interaction.guild_id)
        if not current:
            await interaction.response.send_message("❌ Сейчас ничего не играет.", ephemeral=True)
            return
        await interaction.response.send_message(embed=self.make_embed(current))


async def setup(bot):
    await bot.add_cog(Music(bot))
