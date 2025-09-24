import discord
from discord.ext import commands
import asyncio
import logging
from config import DISCORD_TOKEN, TARGET_CHANNEL_ID, DELAY_SECONDS

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_boosts = {}
pending_tasks = {}

@bot.event
async def on_ready():
    logger.info(f"Discord bot logged in as {bot.user}")

async def send_good_boy_after_delay(user_id, channel):
    await asyncio.sleep(DELAY_SECONDS)
    if user_id in recent_boosts:
        await channel.send(f"<@{user_id}> good boy")
        recent_boosts.pop(user_id, None)
        pending_tasks.pop(user_id, None)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "meow" in message.content.lower():
        await message.channel.send("meow")
    
    if message.channel.id == TARGET_CHANNEL_ID:
        if "just boosted the server!" in message.content.lower():
            user_id = message.author.id
            recent_boosts[user_id] = True
            if user_id in pending_tasks:
                pending_tasks[user_id].cancel()
            pending_tasks[user_id] = bot.loop.create_task(send_good_boy_after_delay(user_id, message.channel))
    
    await bot.process_commands(message)

def start_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        logger.error(f"Discord bot error: {e}")
