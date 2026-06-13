import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timedelta

ECONOMY_FILE = "economy.json"
SHOP_FILE = "shop.json"

DAILY_AMOUNT = 100       # Монет за /daily
DAILY_COOLDOWN = 86400   # 24 часа в секундах
CURRENCY = "💰"

# ─── Кеш в памяти ────────────────────────────────────────────────
_economy_cache: dict = {}
_shop_cache: dict = {}

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

def load_economy(guild_id: int) -> dict:
    if not _economy_cache:
        _economy_cache.update(_load_file(ECONOMY_FILE))
    return _economy_cache.get(str(guild_id), {})

def save_economy(guild_id: int, eco: dict):
    if not _economy_cache:
        _economy_cache.update(_load_file(ECONOMY_FILE))
    _economy_cache[str(guild_id)] = eco
    _save_file(ECONOMY_FILE, _economy_cache)


def get_user(eco: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in eco:
        eco[uid] = {"balance": 0, "last_daily": None, "total_earned": 0}
    return eco[uid]


def load_shop(guild_id: int) -> list:
    if not _shop_cache:
        _shop_cache.update(_load_file(SHOP_FILE))
    return _shop_cache.get(str(guild_id), [])

def save_shop(guild_id: int, shop: list):
    if not _shop_cache:
        _shop_cache.update(_load_file(SHOP_FILE))
    _shop_cache[str(guild_id)] = shop
    _save_file(SHOP_FILE, _shop_cache)


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── /daily ───────────────────────────────────────────────────
    @app_commands.command(name="daily", description="Получить ежедневную награду")
    async def daily(self, interaction: discord.Interaction):
        eco = load_economy(interaction.guild_id)
        user = get_user(eco, interaction.user.id)

        now = datetime.now()

        if user["last_daily"]:
            last = datetime.fromisoformat(user["last_daily"])
            diff = now - last
            if diff.total_seconds() < DAILY_COOLDOWN:
                remaining = timedelta(seconds=DAILY_COOLDOWN) - diff
                h, r = divmod(int(remaining.total_seconds()), 3600)
                m, s = divmod(r, 60)
                embed = discord.Embed(
                    title="⏳ Уже получил награду",
                    description=f"Следующая награда через **{h}ч {m}м {s}с**",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        user["balance"] += DAILY_AMOUNT
        user["total_earned"] += DAILY_AMOUNT
        user["last_daily"] = now.isoformat()
        save_economy(interaction.guild_id, eco)

        embed = discord.Embed(
            title="🎁 Ежедневная награда получена!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Получено", value=f"{CURRENCY} **+{DAILY_AMOUNT}**")
        embed.add_field(name="Баланс", value=f"{CURRENCY} **{user['balance']}**")
        embed.set_footer(text="Следующая награда через 24 часа")
        await interaction.response.send_message(embed=embed)

    # ─── /balance ─────────────────────────────────────────────────
    @app_commands.command(name="balance", description="Посмотреть баланс")
    @app_commands.describe(member="Участник (по умолчанию ты)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        eco = load_economy(interaction.guild_id)
        user = get_user(eco, target.id)

        embed = discord.Embed(
            title=f"{CURRENCY} Баланс — {target.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Баланс", value=f"{CURRENCY} **{user['balance']}**")
        embed.add_field(name="Всего заработано", value=f"{CURRENCY} **{user['total_earned']}**")
        await interaction.response.send_message(embed=embed)

    # ─── /pay ─────────────────────────────────────────────────────
    @app_commands.command(name="pay", description="Перевести монеты другому участнику")
    @app_commands.describe(member="Кому перевести", amount="Сколько монет")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member == interaction.user:
            await interaction.response.send_message("❌ Нельзя перевести себе.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть больше 0.", ephemeral=True)
            return

        eco = load_economy(interaction.guild_id)
        sender = get_user(eco, interaction.user.id)
        receiver = get_user(eco, member.id)

        if sender["balance"] < amount:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. У тебя: {CURRENCY} **{sender['balance']}**", ephemeral=True
            )
            return

        sender["balance"] -= amount
        receiver["balance"] += amount
        save_economy(interaction.guild_id, eco)

        embed = discord.Embed(title="💸 Перевод выполнен", color=discord.Color.green())
        embed.add_field(name="Отправитель", value=interaction.user.mention)
        embed.add_field(name="Получатель", value=member.mention)
        embed.add_field(name="Сумма", value=f"{CURRENCY} **{amount}**", inline=False)
        await interaction.response.send_message(embed=embed)

    # ─── /leaderboard ─────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Топ богатейших участников")
    async def leaderboard(self, interaction: discord.Interaction):
        eco = load_economy(interaction.guild_id)
        if not eco:
            await interaction.response.send_message("❌ Никто ещё не получал монеты.", ephemeral=True)
            return

        sorted_users = sorted(eco.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]

        embed = discord.Embed(title=f"{CURRENCY} Топ богатейших", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]

        lines = []
        for i, (uid, data) in enumerate(sorted_users):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"Участник {uid}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{medal} **{name}** — {CURRENCY} {data.get('balance', 0)}")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    # ─── /give_money ──────────────────────────────────────────────
    @app_commands.command(name="give_money", description="Выдать монеты участнику (админ)")
    @app_commands.describe(member="Участник", amount="Количество монет")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_money(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        eco = load_economy(interaction.guild_id)
        user = get_user(eco, member.id)
        user["balance"] += amount
        user["total_earned"] += max(0, amount)
        save_economy(interaction.guild_id, eco)
        await interaction.response.send_message(
            f"✅ {member.mention} получил {CURRENCY} **{amount}**. Баланс: **{user['balance']}**",
            ephemeral=True
        )

    # ─── /take_money ──────────────────────────────────────────────
    @app_commands.command(name="take_money", description="Снять монеты у участника (админ)")
    @app_commands.describe(member="Участник", amount="Количество монет")
    @app_commands.checks.has_permissions(administrator=True)
    async def take_money(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        eco = load_economy(interaction.guild_id)
        user = get_user(eco, member.id)
        user["balance"] = max(0, user["balance"] - amount)
        save_economy(interaction.guild_id, eco)
        await interaction.response.send_message(
            f"✅ У {member.mention} снято {CURRENCY} **{amount}**. Баланс: **{user['balance']}**",
            ephemeral=True
        )

    # ─── /shop ────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="Магазин ролей")
    async def shop(self, interaction: discord.Interaction):
        items = load_shop(interaction.guild_id)
        if not items:
            await interaction.response.send_message(
                "❌ Магазин пуст. Добавь товары через `/shop_add`", ephemeral=True
            )
            return

        embed = discord.Embed(title="🛒 Магазин ролей", color=discord.Color.blurple())
        for item in items:
            role = interaction.guild.get_role(item["role_id"])
            if role:
                embed.add_field(
                    name=f"{role.name}",
                    value=f"{CURRENCY} **{item['price']}** — `/buy {role.name}`",
                    inline=False
                )
        await interaction.response.send_message(embed=embed)

    # ─── /shop_add ────────────────────────────────────────────────
    @app_commands.command(name="shop_add", description="Добавить роль в магазин")
    @app_commands.describe(role="Роль", price="Цена в монетах")
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_add(self, interaction: discord.Interaction, role: discord.Role, price: int):
        shop = load_shop(interaction.guild_id)
        if any(i["role_id"] == role.id for i in shop):
            await interaction.response.send_message("❌ Эта роль уже в магазине.", ephemeral=True)
            return
        shop.append({"role_id": role.id, "price": price})
        save_shop(interaction.guild_id, shop)
        await interaction.response.send_message(
            f"✅ Роль {role.mention} добавлена в магазин за {CURRENCY} **{price}**", ephemeral=True
        )

    # ─── /shop_remove ─────────────────────────────────────────────
    @app_commands.command(name="shop_remove", description="Убрать роль из магазина")
    @app_commands.describe(role="Роль")
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_remove(self, interaction: discord.Interaction, role: discord.Role):
        shop = load_shop(interaction.guild_id)
        shop = [i for i in shop if i["role_id"] != role.id]
        save_shop(interaction.guild_id, shop)
        await interaction.response.send_message(f"✅ Роль {role.mention} убрана из магазина.", ephemeral=True)

    # ─── /buy ─────────────────────────────────────────────────────
    @app_commands.command(name="buy", description="Купить роль из магазина")
    @app_commands.describe(role="Роль которую хочешь купить")
    async def buy(self, interaction: discord.Interaction, role: discord.Role):
        shop = load_shop(interaction.guild_id)
        item = next((i for i in shop if i["role_id"] == role.id), None)

        if not item:
            await interaction.response.send_message("❌ Этой роли нет в магазине.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("❌ У тебя уже есть эта роль.", ephemeral=True)
            return

        eco = load_economy(interaction.guild_id)
        user = get_user(eco, interaction.user.id)

        if user["balance"] < item["price"]:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. Нужно: {CURRENCY} **{item['price']}**, у тебя: {CURRENCY} **{user['balance']}**",
                ephemeral=True
            )
            return

        user["balance"] -= item["price"]
        save_economy(interaction.guild_id, eco)

        try:
            await interaction.user.add_roles(role, reason="Покупка в магазине")
        except Exception:
            user["balance"] += item["price"]
            save_economy(interaction.guild_id, eco)
            await interaction.response.send_message("❌ Не удалось выдать роль.", ephemeral=True)
            return

        embed = discord.Embed(title="✅ Покупка успешна!", color=discord.Color.green())
        embed.add_field(name="Роль", value=role.mention)
        embed.add_field(name="Потрачено", value=f"{CURRENCY} **{item['price']}**")
        embed.add_field(name="Остаток", value=f"{CURRENCY} **{user['balance']}**")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
