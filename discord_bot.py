import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import re
from datetime import datetime, timedelta
from config import DISCORD_TOKEN

TARGET_CHANNEL_ID = 1389210900489044048
AUTH_CHANNEL_ID = 1287714060716081183
LOG_CHANNEL_ID = 1270314848764559494
OWNER_ID = 1144213765424947251
GUILD_ID = 1241797935100989594
DELAY_SECONDS = 1
BOOST_TEST_CHANNEL_ID = 1270301984897110148

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

recent_boosts = {}
pending_tasks = {}
last_meow_count = None
cute_symbols = [">///<", "^-^", "o///o", "x3"]
submitted_hwids = {}

async def send_good_boy_after_delay(user_id, channel):
    await asyncio.sleep(DELAY_SECONDS)
    if user_id in recent_boosts:
        await channel.send(f"<@{user_id}> good boy")
        recent_boosts.pop(user_id, None)
        pending_tasks.pop(user_id, None)

class HWIDModal(discord.ui.Modal, title="Enter Your HWID"):
    hwid = discord.ui.TextInput(label="Paste your HWID here", style=discord.TextStyle.short, placeholder="Example: ABCDEFGH-1234-IJKL-5678-MNOPQRSTUVW", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        hwid_value = self.hwid.value.strip()
        now = datetime.utcnow()

        if len(hwid_value) < 35:
            await interaction.response.send_message("HWID too short. Must be at least 35 characters.", ephemeral=True)
            return

        if len(hwid_value) > 50:
            await interaction.response.send_message("HWID too long. Maximum 50 characters.", ephemeral=True)
            return

        if not re.fullmatch(r"[A-Za-z0-9-]+", hwid_value):
            await interaction.response.send_message("HWID contains invalid characters. Use only letters, numbers, and dashes.", ephemeral=True)
            return

        if hwid_value in submitted_hwids:
            last_time = submitted_hwids[hwid_value]
            if now - last_time < timedelta(hours=24):
                await interaction.response.send_message("This HWID has already been submitted in the last 24 hours.", ephemeral=True)
                return

        submitted_hwids[hwid_value] = now

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        owner = await bot.fetch_user(OWNER_ID)

        embed = discord.Embed(title="HWID Submitted", description="Your HWID has been sent to the owner for authentication.\n\nIf the owner (<@1144213765424947251>) is online, this usually takes up to 50 minutes. Otherwise, allow up to 15+ hours.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

        msg_embed = discord.Embed(title="New Authentication Request", color=discord.Color.blurple())
        msg_embed.add_field(name="Type", value="Premium", inline=False)
        msg_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        msg_embed.add_field(name="HWID", value=f"{hwid_value}", inline=False)

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
        try:
            await interaction.user.send("loadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()")
            await interaction.response.send_message("Script sent to your DMs!", ephemeral=True)
        except:
            await interaction.response.send_message("Failed to DM the script. Check your privacy settings.", ephemeral=True)

    @discord.ui.button(label="Enter HWID", style=discord.ButtonStyle.success)
    async def enter_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HWIDModal())

@bot.tree.command(name="authenticate", description="Authenticate your Premium access.", guild=discord.Object(id=GUILD_ID))
async def authenticate(interaction: discord.Interaction):
    if interaction.channel.id != AUTH_CHANNEL_ID:
        await interaction.response.send_message("You can only use this command in the designated authentication channel.", ephemeral=True)
        return

    embed = discord.Embed(title="Authenticate for Premium.", description=("Authenticate to get access Premium benefits, follow these steps:\n\n1 Run the following script in Roblox to copy your HWID:\n```lua\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n```\n\n2 Click 'Enter HWID' and submit your HWID.\n3 Wait to get authenticated by mods.\n\nIf the owner is online, authentication may take up to 50 minutes. Otherwise, allow up to 15+ hours."), color=discord.Color.blurple())
    view = AuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

BOOST_TYPES = {discord.MessageType.premium_guild_subscription}

@bot.event
async def on_message(message):
    global last_meow_count

    if message.author == bot.user:
        return

    if message.author.bot:
        await bot.process_commands(message)
        return

    content = message.content or ""
    cleaned_content = re.sub(r'<@!?\d+>', '', content).strip()
    words = re.findall(r'\b\w+[!?.]*\b', cleaned_content)

    all_meows = all(re.match(r'meow[!?.]*$', word, re.IGNORECASE) for word in words) if words else False

    if all_meows and words:
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

        await message.reply(("meow " * meow_count).strip() + punctuation + (" " + symbol if symbol else ""), mention_author=False)

    boost_channels = {TARGET_CHANNEL_ID, BOOST_TEST_CHANNEL_ID}

    if message.channel.id in boost_channels:
        content_lower = content.lower()
        is_system_boost = message.type in BOOST_TYPES

        is_text_boost = any(pattern in content_lower for pattern in [
            "just boosted the server",
            "boosted the server"
        ])

        is_text_boost = is_text_boost and not is_system_boost

        if is_text_boost or is_system_boost:
            if not message.author:
                return

            user_id = message.author.id

            if user_id not in recent_boosts:
                recent_boosts[user_id] = True

                if user_id in pending_tasks:
                    try:
                        pending_tasks[user_id].cancel()
                    except:
                        pass

                pending_tasks[user_id] = bot.loop.create_task(send_good_boy_after_delay(user_id, message.channel))

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Main bot logged in as {bot.user}')

    try:
        await asyncio.sleep(2)
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} guild commands")
    except discord.HTTPException as e:
        if e.status == 429:
            print("⚠️ Rate limited - commands already synced, skipping")
        else:
            print(f"Command sync error: {e}")
    except Exception as e:
        print(f"Command sync failed: {e}")

def start_bot():
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Main bot error: {e}")

if __name__ == "__main__":
    start_bot()
