import os
import time
import json
from urllib.parse import urlparse, unquote
import discord
import aiohttp
import datetime
import yt_dlp
from discord import FFmpegPCMAudio
from discord.ext import commands, tasks
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USER_LOGIN = os.getenv("TWITCH_USER_LOGIN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


twitch_token = None
user_live_status = False

# Cooldown tracking
cooldown_user = {}

# Price API
FULL_PRICE_URL = (
    "https://rust.scmm.app/api/item/prices"
    "?markets=SteamStore&markets=SteamCommunityMarket"
    "&currency=EUR"
)
items_list = None

# Items to exclude completely
EXCLUDED_ITEMS = {
    "Twitch Rivals Trophy",
    "Retro Tool Cupboard",
    "Brutalist",
    "Weapon Racks",
    "Brick",
    "Nomad Outfit",
    "Jungle Building Skin",
    "Industrial Lights",
    "Factory Door",
    "Coconut Underwear",
    "Adobe",
    "Shipping Container",
    "Pattern Boomer"
}

# User → SteamID64 map persistence
USER_MAP_FILE = "user_steam_map.json"
try:
    with open(USER_MAP_FILE, "r") as f:
        user_steam_map = json.load(f)
except FileNotFoundError:
    user_steam_map = {}

async def get_inventory(steam_user_id):
    all_assets = []
    all_descriptions = []
    start_assetid = None

    async with aiohttp.ClientSession() as session:
        while True:
            url = (
                f'https://steamcommunity.com/inventory/{steam_user_id}/252490/2'
                '?l=english&count=5000'
            )
            if start_assetid:
                url += f"&start_assetid={start_assetid}"

            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                all_assets.extend(data.get('assets', []))
                all_descriptions.extend(data.get('descriptions', []))
                if not data.get('more', False):
                    break
                start_assetid = data.get('last_assetid')

    return {'assets': all_assets, 'descriptions': all_descriptions}

async def get_item_price_from_market(session, market_hash_name):
    global items_list

    # Load full price list once
    if items_list is None:
        print(f"[PRICE] 🔄 Descargando listado completo desde: {FULL_PRICE_URL}")
        async with session.get(FULL_PRICE_URL) as resp:
            if resp.status != 200:
                print(f"[PRICE] ❌ Error {resp.status} al cargar listado completo")
                return None
            items_list = await resp.json()
        print(f"[PRICE] ✅ Listado cargado: {len(items_list)} ítems")

    # Find matching item by name
    match = next(
        (itm for itm in items_list if itm.get("name") == market_hash_name),
        None
    )
    if not match:
        print(f"[PRICE] ⚠️ No encontrado '{market_hash_name}'")
        return None

    # Extract first valid price (divide by 100 to convert cents → euros)
    for entry in match.get("prices", []):
        if entry.get("isAvailable") and entry.get("price", 0) > 0:
            raw = entry["price"]
            price = raw / 100
            print(f"[PRICE] ✅ Precio: {price:.2f}€ (raw={raw}) para '{market_hash_name}'")
            return price

    print(f"[PRICE] ⚠️ Ningún precio válido en '{market_hash_name}'")
    return None

async def get_twitch_token():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            data = await resp.json()
            return data.get("access_token")

async def check_if_live():
    global twitch_token
    if not twitch_token:
        twitch_token = await get_twitch_token()

    url = f"https://api.twitch.tv/helix/streams?user_login={TWITCH_USER_LOGIN}"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_token}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 401:
                twitch_token = await get_twitch_token()
                return await check_if_live()
            data = await resp.json()
            return bool(data.get("data"))

@tasks.loop(seconds=60)
async def check_twitch_stream():
    global user_live_status
    is_live = await check_if_live()
    channel = bot.get_channel(CHANNEL_ID)

    if is_live and not user_live_status:
        user_live_status = True
        await channel.send(f"Iwavi en directo wilsons\nhttps://www.twitch.tv/{TWITCH_USER_LOGIN}")
    elif not is_live and user_live_status:
        user_live_status = False

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    check_twitch_stream.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.author.name == "tutankanon":
        today = datetime.date.today()
        last_date = cooldown_user.get(message.author.id)
        
        if last_date != today:
            await message.channel.send("QUE PASA EQUIPO")
            cooldown_user[message.author.id] = today

    # Respuestas automáticas
    content = message.content.lower()
    if "guti" in content or "beka" in content:
        await message.channel.send("SAPO")

    await bot.process_commands(message)

@bot.command()
async def iwavi(ctx):
    await ctx.send("HEHEHEYYYYY TENGO CANCER")

@bot.command()
async def registrar(ctx, profile_url: str):
    """
    Registra el SteamID64 del usuario a partir de su URL de Steam:
      - https://steamcommunity.com/id/vanityName/
      - https://steamcommunity.com/profiles/76561198000000000/
    """
    try:
        path = urlparse(profile_url).path
        parts = [p for p in path.split("/") if p]
        if len(parts) != 2 or parts[0] not in ("id", "profiles"):
            raise ValueError
    except Exception:
        return await ctx.send(
            "❌ URL inválida. Usa `/id/tuVanity/` o `/profiles/tuSteamID64/`."
        )

    kind, identifier = parts

    if kind == "id":
        vanity = unquote(identifier)
        resolve_url = (
            f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
            f"?key={STEAM_API_KEY}&vanityurl={vanity}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(resolve_url) as resp:
                data = await resp.json()
        if data.get("response", {}).get("success") != 1:
            return await ctx.send(f"❌ No pude resolver `{vanity}`.")
        steamid64 = data["response"]["steamid"]
    else:
        steamid64 = identifier
        if not steamid64.isdigit():
            return await ctx.send("❌ SteamID64 no válido en la URL.")

    user_steam_map[ctx.author.name] = steamid64
    with open(USER_MAP_FILE, "w") as f:
        json.dump(user_steam_map, f)
    await ctx.send(f"✅ `{ctx.author.name}` registrado: `{steamid64}`")

@bot.command()
async def skins(ctx):
    steamid = user_steam_map.get(ctx.author.name)
    if not steamid:
        return await ctx.send(
            "❌ No tienes SteamID64 registrado. Usa `!registrar <URL>` primero."
        )

    inventory = await get_inventory(steamid)
    if not inventory or 'assets' not in inventory:
        return await ctx.send("No pude obtener tu inventario. ¿Es público?")

    # Map assetid → nombre
    description_map = {
        item['assetid']: desc['name']
        for desc in inventory['descriptions']
        for item in inventory['assets']
        if item['classid'] == desc['classid']
        and item['instanceid'] == desc['instanceid']
    }

    total_items = 0
    total_price = 0.0
    counted_items = 0
    local_cache = {}
    max_price = 0.0
    max_item = None
    excluded = []

    async with aiohttp.ClientSession() as session:
        for asset in inventory['assets']:
            name = description_map.get(asset['assetid'])
            amt = int(asset.get("amount", 1))
            total_items += amt
            if not name:
                continue

            # Exclusiones manuales
            if name in EXCLUDED_ITEMS:
                excluded.append(name)
                continue

            # Excluir items que acaben en " pack"
            if name.lower().endswith(" pack"):
                excluded.append(name)
                continue

            # Precio
            if name not in local_cache:
                local_cache[name] = await get_item_price_from_market(session, name)
            price = local_cache[name]
            if price is None:
                continue

            total_price += price * amt
            counted_items += amt
            if price > max_price:
                max_price, max_item = price, name

    await ctx.send(f"Total ítems: {total_items}")
    if counted_items == 0:
        await ctx.send("No se encontraron ítems con precio.")
    else:
        await ctx.send(
            f"{counted_items} con precio. Valor total: {total_price:.2f}€"
        )
        if max_item:
            await ctx.send(
                f"Ítem más caro: **{max_item}** a {max_price:.2f}€"
            )

    if excluded:
        uniques = ", ".join(sorted(set(excluded)))
        await ctx.send(f"Excluidos: {uniques}")
    
@bot.command()
async def play(ctx, *, url: str):
   
    voice_channel = bot.get_channel(CHANNEL_ID)
    if not voice_channel or not isinstance(voice_channel, discord.VoiceChannel):
        return await ctx.send("❌ Canal de voz no encontrado.")

    if ctx.voice_client is None:
        vc = await voice_channel.connect()
    else:
        vc = ctx.voice_client
        if vc.channel.id != voice_channel.id:
            await vc.move_to(voice_channel)

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'auto'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        audio_url = info['url']

    source = FFmpegPCMAudio(
        audio_url,
        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    )
    vc.play(source, after=lambda e: print(f"[PLAY] Terminado: {e}") if e else None)

    await ctx.send(f"▶️ Reproduciendo **{info.get('title', 'desconocido')}**")

bot.run(TOKEN)
