import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import re
from config import DISCORD_TOKEN

TARGET_CHANNEL_ID = 1389210900489044048
AUTH_CHANNEL_ID = 1287714060716081183
LOG_CHANNEL_ID = 1270314848764559494
OWNER_ID = 1144213765424947251
DELAY_SECONDS = 1

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_boosts = {}
pending_tasks = {}
last_meow_count = None
cute_symbols = [">///<", "^-^", "o///o", "x3"]

async def send_good_boy_after_delay(user_id, channel):
    await asyncio.sleep(DELAY_SECONDS)
    if user_id in recent_boosts:
        await channel.send(f"<@{user_id}> good boy")
        recent_boosts.pop(user_id, None)
        pending_tasks.pop(user_id, None)

class HWIDModal(discord.ui.Modal, title="Enter Your HWID"):
    hwid = discord.ui.TextInput(label="Paste your HWID here", style=discord.TextStyle.short, placeholder="Example: 7d9f3e2b-xxxx-xxxx-xxxx", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        hwid_value = self.hwid.value.strip()
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(title="HWID Submitted ✅", description="Your HWID has been sent to the owner for authentication.\n\nIf the owner (<@1144213765424947251>) is **online**, this usually takes up to **50 minutes**.\nOtherwise (during school/night), it may take up to **15+ hours**.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        msg_embed = discord.Embed(title="🔐 New Authentication Request", color=discord.Color.blurple())
        msg_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        msg_embed.add_field(name="HWID", value=f"`{hwid_value}`", inline=False)
        if log_channel:
            await log_channel.send(embed=msg_embed)
        if owner:
            try:
                await owner.send(embed=msg_embed)
            except:
                pass

class AuthButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("loadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()", ephemeral=True)
    @discord.ui.button(label="Enter HWID", style=discord.ButtonStyle.success)
    async def enter_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HWIDModal())

@app_commands.command(name="authenticate", description="Authenticate your Premium access.")
async def authenticate(interaction: discord.Interaction):
    if interaction.channel.id != AUTH_CHANNEL_ID:
        await interaction.response.send_message("❌ You can only use this command in the designated authentication channel.", ephemeral=True)
        return
    embed = discord.Embed(title="🔐 Premium Authentication", description="**To authenticate your Premium access**, follow these steps:\n\n1️⃣ Run the following script in **Roblox** to copy your HWID:\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n2️⃣ Click **Enter HWID** below to submit it.\n3️⃣ Wait for the owner (<@1144213765424947251>) to authenticate you.\n\n_Note: If the owner is online, authentication may take up to 50 minutes. If not, please allow up to 15+ hours._", color=discord.Color.blurple())
    view = AuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_message(message):
    global last_meow_count
    if message.author == bot.user:
        return
    words = re.findall(r'\bmeow\b', message.content, flags=re.IGNORECASE)
    if words:
        meow_weights = [5, 4, 3, 2, 1, 1]
        possible_counts = list(range(2, 8))
        if last_meow_count in possible_counts:
            last_index = possible_counts.index(last_meow_count)
            weights = meow_weights[:]
            weights[last_index] = 0
        else:
            weights = meow_weights
        meow_count = random.choices(possible_counts, weights=weights)[0]
        last_meow_count = meow_count
        punctuation = random.choice(["", "!", "!!", "."])
        symbol_chance = random.randint(1, 3)
        symbol = random.choice(cute_symbols) if symbol_chance == 1 else ""
        await message.channel.send(("meow " * meow_count).strip() + punctuation + (" " + symbol if symbol else ""))
    if message.channel.id == TARGET_CHANNEL_ID:
        if "just boosted the server!" in message.content.lower():
            user_id = message.author.id
            if user_id not in recent_boosts:
                recent_boosts[user_id] = True
                if user_id in pending_tasks:
                    pending_tasks[user_id].cancel()
                pending_tasks[user_id] = bot.loop.create_task(send_good_boy_after_delay(user_id, message.channel))
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    try:
        if not any(cmd.name == "authenticate" for cmd in bot.tree.get_commands()):
            bot.tree.add_command(authenticate)
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print(f"Sync failed: {e}")

def start_bot():
    bot.run(DISCORD_TOKEN)
