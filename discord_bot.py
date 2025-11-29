import discord
from discord.ext import commands
import asyncio
import random
import re
from datetime import datetime, timedelta
from config import DISCORD_TOKEN

TARGET_CHANNEL_ID = 1389210900489044048
AUTH_CHANNEL_ID = 1287714060716081183
TESTER_AUTH_CHANNEL_ID = 1429023673704255488
LOG_CHANNEL_ID = 1270314848764559494
OWNER_ID = 1144213765424947251
CO_OWNER_ID = 1144213765424947251
GUILD_ID = 1241797935100989594
DELAY_SECONDS = 1
BOOST_TEST_CHANNEL_ID = 1270301984897110148

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_boosts = {}
pending_tasks = {}
last_meow_count = None
cute_symbols = [">///<", "^-^", "o///o", "x3"]
submitted_hwids = {}
submitted_tester_hwids = {}

async def send_good_boy_after_delay(user_id, channel):
    await asyncio.sleep(DELAY_SECONDS)
    if user_id in recent_boosts:
        await channel.send(f"<@{user_id}> good boy")
        recent_boosts.pop(user_id, None)
        pending_tasks.pop(user_id, None)

class HWIDModal(discord.ui.Modal, title="Enter Your HWID"):
    hwid = discord.ui.TextInput(
        label="Paste your HWID here",
        style=discord.TextStyle.short,
        placeholder="Example: ABCDEFGH-1234-IJKL-5678-MNOPQRSTUVW",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        hwid_value = self.hwid.value.strip()
        now = datetime.utcnow()
        if len(hwid_value) < 35 or len(hwid_value) > 50 or not re.fullmatch(r"[A-Za-z0-9-]+", hwid_value):
            await interaction.response.send_message("Invalid HWID.", ephemeral=True)
            return
        if hwid_value in submitted_hwids:
            last_time = submitted_hwids[hwid_value]
            if now - last_time < timedelta(hours=24):
                await interaction.response.send_message("This HWID has already been submitted in the last 24 hours.", ephemeral=True)
                return
        submitted_hwids[hwid_value] = now
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(
            title="HWID Submitted",
            description="Your HWID has been sent to the owner for authentication.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        msg_embed = discord.Embed(title="New Authentication Request", color=discord.Color.blurple())
        msg_embed.add_field(name="Type", value="Premium", inline=False)
        msg_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        msg_embed.add_field(name="HWID", value=f"`{hwid_value}`", inline=False)
        if log_channel:
            await log_channel.send(embed=msg_embed)
        if owner:
            try:
                await owner.send(embed=msg_embed)
            except:
                pass

class TesterHWIDModal(discord.ui.Modal, title="Enter Your HWID (Tester)"):
    hwid = discord.ui.TextInput(
        label="Paste your HWID here",
        style=discord.TextStyle.short,
        placeholder="Example: ABCDEFGH-1234-IJKL-5678-MNOPQRSTUVW",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        hwid_value = self.hwid.value.strip()
        now = datetime.utcnow()
        if len(hwid_value) < 35 or len(hwid_value) > 50 or not re.fullmatch(r"[A-Za-z0-9-]+", hwid_value):
            await interaction.response.send_message("Invalid HWID.", ephemeral=True)
            return
        if hwid_value in submitted_tester_hwids:
            last_time = submitted_tester_hwids[hwid_value]
            if now - last_time < timedelta(hours=24):
                await interaction.response.send_message("This HWID has already been submitted in the last 24 hours.", ephemeral=True)
                return
        submitted_tester_hwids[hwid_value] = now
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        co_owner = await bot.fetch_user(CO_OWNER_ID)
        embed = discord.Embed(
            title="HWID Submitted (Tester)",
            description=f"Your HWID has been sent to the Owner (<@{CO_OWNER_ID}>) for tester authentication.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        msg_embed = discord.Embed(title="New Tester Authentication Request", color=discord.Color.orange())
        msg_embed.add_field(name="Type", value="Script Tester", inline=False)
        msg_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        msg_embed.add_field(name="HWID", value=f"`{hwid_value}`", inline=False)
        if log_channel:
            await log_channel.send(embed=msg_embed)
        if co_owner:
            try:
                await co_owner.send(embed=msg_embed)
            except:
                pass

class AuthButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send("loadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()")
            await interaction.response.send_message("Script sent to your DMs!", ephemeral=True)
        except:
            await interaction.response.send_message("Failed to DM the script.", ephemeral=True)

    @discord.ui.button(label="Enter HWID", style=discord.ButtonStyle.success)
    async def enter_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HWIDModal())

class TesterAuthButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send("loadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()")
            await interaction.response.send_message("Script sent to your DMs!", ephemeral=True)
        except:
            await interaction.response.send_message("Failed to DM the script.", ephemeral=True)

    @discord.ui.button(label="Enter HWID", style=discord.ButtonStyle.success)
    async def enter_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TesterHWIDModal())

@bot.tree.command(name="authenticate", description="Authenticate your Premium access.", guild=discord.Object(id=GUILD_ID))
async def authenticate(interaction: discord.Interaction):
    if interaction.channel.id != AUTH_CHANNEL_ID:
        await interaction.response.send_message("You can only use this command in the designated authentication channel.", ephemeral=True)
        return
    embed = discord.Embed(
        title="Authenticate for Premium.",
        description=(
            "Authenticate to get access Premium benefits, follow these steps:\n\n"
            "1 Run the following script in Roblox to copy your HWID:\n"
            "```lua\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n```\n"
            "2 Click 'Enter HWID' and submit your HWID.\n"
            "3 Wait to get authenticated by mods.\n\n"
            "If the owner is online, authentication may take up to 50 minutes. Otherwise, allow up to 15+ hours."
        ),
        color=discord.Color.blurple()
    )
    view = AuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="authenticate_tester", description="Authenticate as a Script Tester.", guild=discord.Object(id=GUILD_ID))
async def authenticate_tester(interaction: discord.Interaction):
    if interaction.channel.id != TESTER_AUTH_CHANNEL_ID:
        await interaction.response.send_message("You can only use this command in the designated tester authentication channel.", ephemeral=True)
        return
    embed = discord.Embed(
        title="Authenticate for Script Tester.",
        description=(
            "Authenticate to get access as a Script Tester, follow these steps:\n\n"
            "1 Run the following script in Roblox to copy your HWID:\n"
            "```lua\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n```\n"
            "2 Click 'Enter HWID' and submit your HWID.\n"
            "3 Wait to get authenticated by the co-owner.\n\n"
            "Your request will be reviewed by the co-owner."
        ),
        color=discord.Color.orange()
    )
    view = TesterAuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

def pronoun_response(pronouns):
    pronouns = pronouns.lower()
    if "she" in pronouns:
        return "good girl"
    if "he" in pronouns:
        return "good boy"
    if "they" in pronouns:
        return "good human"
    return "good boy"

@bot.event
async def on_message(message):
    global last_meow_count
    if message.author == bot.user:
        return
    words = re.findall(r'\bmeow\b', message.content, flags=re.IGNORECASE)
    if words:
        meow_weights = [5,4,3,2,1,1]
        possible_counts = list(range(2,8))
        if last_meow_count in possible_counts:
            last_index = possible_counts.index(last_meow_count)
            weights = meow_weights[:]
            weights[last_index] = 0
        else:
            weights = meow_weights
        meow_count = random.choices(possible_counts, weights=weights)[0]
        last_meow_count = meow_count
        punctuation = random.choice(["","!","!!","."])
        symbol_chance = random.randint(1,3)
        symbol = random.choice(cute_symbols) if symbol_chance==1 else ""
        await message.channel.send(("meow "*meow_count).strip()+punctuation+(" "+symbol if symbol else ""))
    boost_channels = {TARGET_CHANNEL_ID, BOOST_TEST_CHANNEL_ID}
    if message.channel.id in boost_channels:
        content = message.content.lower()
        is_text_boost = ("boosted the server" in content or "just boosted" in content)
        is_system_boost = (message.type == discord.MessageType.default and message.author.bot)
        if is_text_boost or is_system_boost:
            user_id = message.author.id
            if user_id not in recent_boosts:
                recent_boosts[user_id] = True
                if user_id in pending_tasks:
                    pending_tasks[user_id].cancel()
                pending_tasks[user_id] = bot.loop.create_task(send_good_boy_after_delay(user_id, message.channel))
    if bot.user.mentioned_in(message):
        pronouns_match = re.search(r'\b(?:she|her|he|him|they|them)\b', message.content, re.IGNORECASE)
        if pronouns_match:
            pronouns = pronouns_match.group(0)
            response = f"<@{message.author.id}> {pronoun_response(pronouns)}"
        else:
            response = f"<@{message.author.id}> good boy"
        await message.channel.send(response)
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Commands synced successfully!")
    except Exception as e:
        print(f"Slash command sync failed: {e}")

def start_bot():
    bot.run(DISCORD_TOKEN)
