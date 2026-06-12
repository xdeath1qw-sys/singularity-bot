import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "applications_config.json"
APPS_FILE = "applications_data.json"


def load_config(guild_id: int) -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), {})


def save_config(guild_id: int, config: dict):
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    data[str(guild_id)] = config
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_apps(guild_id: int) -> dict:
    if not os.path.exists(APPS_FILE):
        return {}
    with open(APPS_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), {})


def save_apps(guild_id: int, apps: dict):
    data = {}
    if os.path.exists(APPS_FILE):
        with open(APPS_FILE, "r") as f:
            data = json.load(f)
    data[str(guild_id)] = apps
    with open(APPS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Модальное окно анкеты ────────────────────────────────────────
class ApplicationModal(discord.ui.Modal):
    def __init__(self, app_type: str, app_config: dict, guild_id: int):
        super().__init__(title=f"📋 {app_type}")
        self.app_type = app_type
        self.app_config = app_config
        self.guild_id = guild_id

        questions = app_config.get("questions", [
            "Как тебя зовут?",
            "Сколько тебе лет?",
            "Почему хочешь подать заявку?",
        ])

        for i, q in enumerate(questions[:5]):
            self.add_item(discord.ui.TextInput(
                label=q[:45],
                placeholder="Введи ответ...",
                style=discord.TextStyle.paragraph if i >= 2 else discord.TextStyle.short,
                max_length=500,
            ))

    async def on_submit(self, interaction: discord.Interaction):
        answers = [child.value for child in self.children]
        questions = self.app_config.get("questions", [])

        review_channel_id = self.app_config.get("review_channel_id")
        if not review_channel_id:
            await interaction.response.send_message("❌ Канал для заявок не настроен.", ephemeral=True)
            return

        review_channel = interaction.guild.get_channel(review_channel_id)
        if not review_channel:
            await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)
            return

        # Проверяем дубль заявки
        apps = load_apps(self.guild_id)
        key = f"{interaction.user.id}_{self.app_type}"
        if apps.get(key, {}).get("status") == "pending":
            await interaction.response.send_message("❌ У тебя уже есть активная заявка этого типа.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 {self.app_type}",
            color=discord.Color.yellow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(
            name="👤 Пользователь",
            value=f"{interaction.user.mention} (`{interaction.user}`)",
            inline=False
        )

        for q, a in zip(questions, answers):
            embed.add_field(name=q[:256], value=a[:1024] or "*нет ответа*", inline=False)

        embed.set_footer(text=f"ID: {interaction.user.id} | Тип: {self.app_type}")

        view = ReviewView(
            applicant_id=interaction.user.id,
            guild_id=self.guild_id,
            app_type=self.app_type,
            role_id=self.app_config.get("accept_role_id")
        )

        msg = await review_channel.send(embed=embed, view=view)

        apps[key] = {"message_id": msg.id, "channel_id": review_channel_id, "status": "pending"}
        save_apps(self.guild_id, apps)

        await interaction.response.send_message(
            f"✅ Твоя заявка **{self.app_type}** отправлена! Ожидай решения модераторов.",
            ephemeral=True
        )


# ─── Кнопки принять / отклонить ───────────────────────────────────
class ReviewView(discord.ui.View):
    def __init__(self, applicant_id: int = 0, guild_id: int = 0, app_type: str = "", role_id: int = None):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.guild_id = guild_id
        self.app_type = app_type
        self.role_id = role_id

    def _parse_footer(self, message: discord.Message):
        try:
            footer = message.embeds[0].footer.text
            parts = {p.split(": ")[0]: p.split(": ")[1] for p in footer.split(" | ")}
            return int(parts.get("ID", 0)), parts.get("Тип", "")
        except Exception:
            return 0, ""

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.green, custom_id="rev_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        applicant_id, app_type = self._parse_footer(interaction.message)
        member = interaction.guild.get_member(applicant_id)

        # Выдаём роль
        config = load_config(interaction.guild_id)
        app_cfg = next((a for a in config.get("applications", []) if a["name"] == app_type), {})
        role_id = app_cfg.get("accept_role_id")
        if role_id and member:
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Заявка принята: {app_type}")
                except Exception:
                    pass

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(
            name="✅ Решение",
            value=f"**Принята** модератором {interaction.user.mention}",
            inline=False
        )
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, view=self)

        if member:
            try:
                dm = discord.Embed(
                    title=f"✅ Заявка «{app_type}» принята!",
                    description=f"Сервер: **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                dm.add_field(name="Модератор", value=str(interaction.user))
                await member.send(embed=dm)
            except Exception:
                pass

        apps = load_apps(interaction.guild_id)
        key = f"{applicant_id}_{app_type}"
        if key in apps:
            apps[key]["status"] = "accepted"
            save_apps(interaction.guild_id, apps)

        await interaction.response.send_message("✅ Заявка принята.", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="rev_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        applicant_id, app_type = self._parse_footer(interaction.message)
        await interaction.response.send_modal(
            DeclineModal(interaction.message, interaction.guild_id, applicant_id, app_type)
        )


class DeclineModal(discord.ui.Modal, title="Причина отклонения"):
    reason = discord.ui.TextInput(
        label="Причина",
        placeholder="Укажи причину...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, message: discord.Message, guild_id: int, applicant_id: int, app_type: str):
        super().__init__()
        self.app_message = message
        self.guild_id = guild_id
        self.applicant_id = applicant_id
        self.app_type = app_type

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.app_message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(
            name="❌ Решение",
            value=f"**Отклонена** модератором {interaction.user.mention}\n**Причина:** {self.reason.value}",
            inline=False
        )

        view = discord.ui.View()
        for label, style, cid in [("✅ Принять", discord.ButtonStyle.green, "rev_accept"),
                                    ("❌ Отклонить", discord.ButtonStyle.red, "rev_decline")]:
            b = discord.ui.Button(label=label, style=style, custom_id=cid, disabled=True)
            view.add_item(b)

        await self.app_message.edit(embed=embed, view=view)

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
                dm = discord.Embed(
                    title=f"❌ Заявка «{self.app_type}» отклонена",
                    description=f"Сервер: **{interaction.guild.name}**",
                    color=discord.Color.red()
                )
                dm.add_field(name="Причина", value=self.reason.value)
                dm.add_field(name="Модератор", value=str(interaction.user))
                await member.send(embed=dm)
            except Exception:
                pass

        apps = load_apps(self.guild_id)
        key = f"{self.applicant_id}_{self.app_type}"
        if key in apps:
            apps[key]["status"] = "declined"
            save_apps(self.guild_id, apps)

        await interaction.response.send_message("✅ Заявка отклонена.", ephemeral=True)


# ─── Дропдаун выбора заявки ───────────────────────────────────────
class ApplicationSelect(discord.ui.Select):
    def __init__(self, applications: list, guild_id: int):
        options = [
            discord.SelectOption(
                label=app["name"],
                description=app.get("description", "Нажми чтобы подать заявку."),
                value=app["name"]
            )
            for app in applications
        ]
        super().__init__(
            placeholder="Выбери заявку для подачи",
            options=options,
            custom_id="app_select"
        )
        self.applications = applications
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        app_cfg = next((a for a in self.applications if a["name"] == selected), None)
        if not app_cfg:
            await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
            return

        modal = ApplicationModal(selected, app_cfg, self.guild_id)
        await interaction.response.send_modal(modal)


class ApplicationView(discord.ui.View):
    def __init__(self, applications: list, guild_id: int):
        super().__init__(timeout=None)
        self.add_item(ApplicationSelect(applications, guild_id))


# ─── КОГ ──────────────────────────────────────────────────────────
class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ReviewView())

    @app_commands.command(name="app_setup", description="Настроить и опубликовать панель заявок")
    @app_commands.describe(
        channel="Канал где появится панель с дропдауном",
        title="Заголовок панели",
        description="Описание панели",
        image_url="Ссылка на картинку (необязательно)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def app_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        image_url: str = None
    ):
        config = load_config(interaction.guild_id)

        if not config.get("applications"):
            config["applications"] = [
                {
                    "name": "Заявка в клан",
                    "description": "Нажми чтобы подать заявку.",
                    "review_channel_id": None,
                    "accept_role_id": None,
                    "questions": [
                        "Как тебя зовут?",
                        "Сколько тебе лет?",
                        "Почему хочешь вступить в клан?",
                        "Твой опыт?",
                        "Откуда узнал о нас?"
                    ]
                },
                {
                    "name": "Заявка на медиа",
                    "description": "Нажми чтобы подать заявку.",
                    "review_channel_id": None,
                    "accept_role_id": None,
                    "questions": [
                        "Как тебя зовут?",
                        "Какой контент ты создаёшь?",
                        "Ссылка на твои работы?",
                        "Сколько подписчиков?",
                        "Почему хочешь стать медиа?"
                    ]
                },
                {
                    "name": "Заявка на Creator гп",
                    "description": "Нажми чтобы подать заявку.",
                    "review_channel_id": None,
                    "accept_role_id": None,
                    "questions": [
                        "Как тебя зовут?",
                        "Что ты умеешь создавать?",
                        "Покажи примеры своих работ",
                        "Сколько времени готов уделять?",
                        "Почему хочешь стать Creator?"
                    ]
                }
            ]

        config["panel_channel_id"] = channel.id
        config["panel_title"] = title
        config["panel_description"] = description
        config["panel_image"] = image_url
        save_config(interaction.guild_id, config)

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple()
        )
        if image_url:
            embed.set_image(url=image_url)

        view = ApplicationView(config["applications"], interaction.guild_id)
        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Панель заявок опубликована в {channel.mention}!\n"
            f"Настрой каналы для каждой заявки через `/app_channel`",
            ephemeral=True
        )

    @app_commands.command(name="app_channel", description="Установить канал для определённой заявки")
    @app_commands.describe(
        app_name="Название заявки",
        review_channel="Канал куда приходят заявки",
        accept_role="Роль при принятии (необязательно)"
    )
    @app_commands.choices(app_name=[
        app_commands.Choice(name="Заявка в клан", value="Заявка в клан"),
        app_commands.Choice(name="Заявка на медиа", value="Заявка на медиа"),
        app_commands.Choice(name="Заявка на Creator гп", value="Заявка на Creator гп"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def app_channel(
        self,
        interaction: discord.Interaction,
        app_name: str,
        review_channel: discord.TextChannel,
        accept_role: discord.Role = None
    ):
        config = load_config(interaction.guild_id)
        apps = config.get("applications", [])

        for app in apps:
            if app["name"] == app_name:
                app["review_channel_id"] = review_channel.id
                if accept_role:
                    app["accept_role_id"] = accept_role.id
                break

        save_config(interaction.guild_id, config)

        msg = f"✅ Заявка **{app_name}** → {review_channel.mention}"
        if accept_role:
            msg += f"\nРоль при принятии: {accept_role.mention}"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="app_questions", description="Изменить вопросы для заявки (от 2 до 5)")
    @app_commands.describe(
        app_name="Название заявки",
        q1="Вопрос 1", q2="Вопрос 2",
        q3="Вопрос 3 (необязательно)", q4="Вопрос 4 (необязательно)", q5="Вопрос 5 (необязательно)"
    )
    @app_commands.choices(app_name=[
        app_commands.Choice(name="Заявка в клан", value="Заявка в клан"),
        app_commands.Choice(name="Заявка на медиа", value="Заявка на медиа"),
        app_commands.Choice(name="Заявка на Creator гп", value="Заявка на Creator гп"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def app_questions(
        self,
        interaction: discord.Interaction,
        app_name: str,
        q1: str, q2: str,
        q3: str = None, q4: str = None, q5: str = None
    ):
        config = load_config(interaction.guild_id)
        questions = [q1, q2]
        if q3: questions.append(q3)
        if q4: questions.append(q4)
        if q5: questions.append(q5)

        for app in config.get("applications", []):
            if app["name"] == app_name:
                app["questions"] = questions
                break

        save_config(interaction.guild_id, config)

        embed = discord.Embed(
            title=f"✅ Вопросы обновлены — {app_name}",
            description="\n".join(f"`{i+1}.` {q}" for i, q in enumerate(questions)),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="app_info", description="Показать настройки всех заявок")
    @app_commands.checks.has_permissions(administrator=True)
    async def app_info(self, interaction: discord.Interaction):
        config = load_config(interaction.guild_id)
        embed = discord.Embed(title="📋 Система заявок", color=discord.Color.blurple())

        for app in config.get("applications", []):
            ch = interaction.guild.get_channel(app.get("review_channel_id") or 0)
            role = interaction.guild.get_role(app.get("accept_role_id") or 0)
            embed.add_field(
                name=app["name"],
                value=(
                    f"Канал: {ch.mention if ch else '❌ Не задан'}\n"
                    f"Роль: {role.mention if role else 'Не задана'}\n"
                    f"Вопросов: {len(app.get('questions', []))}"
                ),
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Applications(bot))
