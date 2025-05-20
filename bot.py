import discord
import aiohttp
import asyncio
from threading import Thread
import os
import time
from discord.ext import commands, tasks
from dotenv import load_dotenv

#Load .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USER_LOGIN = os.getenv("TWITCH_USER_LOGIN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

twitch_token = None
user_live_status = False
cooldown_user = {}

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
            return data["access_token"]

async def check_if_live():
    global twitch_token
    url = f"https://api.twitch.tv/helix/streams?user_login={TWITCH_USER_LOGIN}"
    
    if not twitch_token:
        twitch_token = await get_twitch_token()
    
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_token}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 401:
                #Token expirado
                twitch_token = await get_twitch_token()
                return await check_if_live()
            data = await resp.json()
            return len(data["data"]) > 0 #True if live

@tasks.loop(seconds=60)
async def check_twitch_stream():
    global user_live_status
    is_live = await check_if_live()

    if is_live and not user_live_status:
        user_live_status = True
        channel = bot.get_channel(CHANNEL_ID)   
        await channel.send(f"Iwavi en directo wilsons\nhttps://www.twitch.tv/{TWITCH_USER_LOGIN}")
    elif not is_live and user_live_status:
        user_live_status = False

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    check_twitch_stream.start()

@bot.event
async def on_message(message):
    david_user = "tutankañon#7894"

    if message.author == bot.user:
        return
    
    if str(message.author) == david_user:
        now = time.time()
        last_use = cooldown_user.get(message.author.id, 0)
        time_since_last_user = now - last_use

        if time_since_last_user > 120:
            await message.channel.send("QUE PASA EQUIPO")
            cooldown_user[message.author.id] = now

    if "guti" in message.content.lower() or "beka" in message.content.lower():
        await message.channel.send("SAPO")

    await bot.process_commands(message)

@bot.command()
async def iwavi(ctx):
    await ctx.send("HEHEHEYYYYY TENGO CANCER")

#Run bot
bot.run(TOKEN)