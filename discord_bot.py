import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import re
import json
import aiohttp
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

WEBSITE_URL = "https://vadrifts.onrender.com"
API_SECRET = "vadriftsisalwaysinseason"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
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

def parse_bypass_mappings(code_text):
    try:
        print("Starting to parse bypass mappings...")
        
        us_char_match = re.search(r'local US_CHAR = "([^"]*)"', code_text)
        us_char = us_char_match.group(1) if us_char_match else ""
        print(f"Found US_CHAR: '{us_char}'")
        
        auto_logic_pattern = r'if currentMethod == "auto" then\s*local bypassLogic = \{(.*?)\}'
        match = re.search(auto_logic_pattern, code_text, re.DOTALL)
        
        if not match:
            print("Could not find auto method pattern")
            return None
        
        print("Found auto method bypassLogic table")
        table_content = match.group(1)
        methods = {}
        
        method_pattern = r'\[(\d+)\]\s*=\s*\{([^}]+)\}'
        method_matches = list(re.finditer(method_pattern, table_content))
        print(f"Found {len(method_matches)} methods in auto logic")
        
        for method_match in method_matches:
            method_num = int(method_match.group(1))
            mappings_str = method_match.group(2)
            mappings = {}
            
            char_pattern = r'(\w+)="([^"]*)"'
            for char_match in re.finditer(char_pattern, mappings_str):
                key = char_match.group(1)
                value = char_match.group(2)
                mappings[key] = value
            
            if '[" "]=US_CHAR' in mappings_str:
                mappings[" "] = us_char
            
            methods[str(method_num)] = mappings
            print(f"Auto method {method_num}: {len(mappings)} mappings")
        
        priority_pattern = r'priorityOrder = \{([^}]+)\}'
        priority_match = re.search(priority_pattern, code_text)
        priority_order = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
        
        if priority_match:
            priority_str = priority_match.group(1)
            priority_nums = re.findall(r'\d+', priority_str)
            if priority_nums:
                priority_order = [int(x) for x in priority_nums]
                print(f"Found priority order: {priority_order}")
        
        result = {
            "us_char": us_char,
            "methods": methods,
            "priority_order": priority_order,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"Successfully parsed {len(methods)} auto methods")
        return result
        
    except Exception as e:
        print(f"Error parsing bypass mappings: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    except Exception as e:
        print(f"Error parsing bypass mappings: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    except Exception as e:
        print(f"Error parsing bypass mappings: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    except Exception as e:
        print(f"Error parsing bypass mappings: {e}")
        return None
        
    except Exception as e:
        print(f"Error parsing bypass mappings: {e}")
        return None

async def update_bypass_data(data):
    try:
        print(f"Attempting to update bypass data to {WEBSITE_URL}/api/update_bypass")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{WEBSITE_URL}/api/update_bypass',
                json=data,
                headers={'Authorization': API_SECRET}
            ) as resp:
                response_text = await resp.text()
                print(f"Server response: {resp.status} - {response_text}")
                return resp.status == 200
    except Exception as e:
        print(f"Error updating bypass data: {e}")
        return False

def validate_bypass_code(content):
    required_markers = ["premiumLogicRaw", "local US_CHAR", "WindUI"]
    return all(marker in content for marker in required_markers)

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
        msg_embed.add_field(name="HWID", value=f"`{hwid_value}`", inline=False)
        if log_channel:
            await log_channel.send(embed=msg_embed)
        if owner:
            try:
                await owner.send(embed=msg_embed)
            except:
                pass

class TesterHWIDModal(discord.ui.Modal, title="Enter Your HWID (Tester)"):
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
        if hwid_value in submitted_tester_hwids:
            last_time = submitted_tester_hwids[hwid_value]
            if now - last_time < timedelta(hours=24):
                await interaction.response.send_message("This HWID has already been submitted in the last 24 hours.", ephemeral=True)
                return
        submitted_tester_hwids[hwid_value] = now
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        co_owner = await bot.fetch_user(CO_OWNER_ID)
        embed = discord.Embed(title="HWID Submitted (Tester)", description=f"Your HWID has been sent to the Owner (<@{CO_OWNER_ID}>) for tester authentication.\n\nYou'll be contacted once reviewed.", color=discord.Color.green())
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
            await interaction.response.send_message("Failed to DM the script. Check your privacy settings.", ephemeral=True)
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
            await interaction.response.send_message("Failed to DM the script. Check your privacy settings.", ephemeral=True)
    @discord.ui.button(label="Enter HWID", style=discord.ButtonStyle.success)
    async def enter_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TesterHWIDModal())

@bot.tree.command(name="authenticate", description="Authenticate your Premium access.", guild=discord.Object(id=GUILD_ID))
async def authenticate(interaction: discord.Interaction):
    if interaction.channel.id != AUTH_CHANNEL_ID:
        await interaction.response.send_message("You can only use this command in the designated authentication channel.", ephemeral=True)
        return
    embed = discord.Embed(title="Authenticate for Premium.", description=("Authenticate to get access Premium benefits, follow these steps:\n\n1 Run the following script in Roblox to copy your HWID:\n```lua\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n```\n2 Click 'Enter HWID' and submit your HWID.\n3 Wait to get authenticated by mods.\n\nIf the owner is online, authentication may take up to 50 minutes. Otherwise, allow up to 15+ hours."), color=discord.Color.blurple())
    view = AuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="authenticate_tester", description="Authenticate as a Script Tester.", guild=discord.Object(id=GUILD_ID))
async def authenticate_tester(interaction: discord.Interaction):
    if interaction.channel.id != TESTER_AUTH_CHANNEL_ID:
        await interaction.response.send_message("You can only use this command in the designated tester authentication channel.", ephemeral=True)
        return
    embed = discord.Embed(title="Authenticate for Script Tester.", description=("Authenticate to get access as a Script Tester, follow these steps:\n\n1 Run the following script in Roblox to copy your HWID:\n```lua\nloadstring(game:HttpGet('https://raw.githubusercontent.com/vqmpjayZ/utils/refs/heads/main/CopyHWID.lua'))()\n```\n2 Click 'Enter HWID' and submit your HWID.\n3 Wait to get authenticated by the co-owner.\n\nYour request will be reviewed by the co-owner."), color=discord.Color.orange())
    view = TesterAuthButtonView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

BOOST_TYPES = {discord.MessageType.premium_guild_subscription}

@bot.event
async def on_message(message):
    global last_meow_count

    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel) and message.author.id == OWNER_ID:
        content = ""
        
        if message.content:
            content = message.content
        elif message.attachments:
            for attachment in message.attachments:
                if attachment.filename.endswith(('.lua', '.txt')):
                    try:
                        file_content = await attachment.read()
                        content = file_content.decode('utf-8')
                        break
                    except:
                        await message.channel.send("❌ Could not read file")
                        return
        
        if content and validate_bypass_code(content):
            try:
                extracted_data = parse_bypass_mappings(content)
                
                if extracted_data:
                    success = await update_bypass_data(extracted_data)
                    
                    if success:
                        await message.channel.send("✅ Bypass mappings updated successfully!")
                    else:
                        await message.channel.send("❌ Failed to update mappings on server")
                else:
                    await message.channel.send("❌ Could not extract mappings from code")
            except Exception as e:
                await message.channel.send(f"❌ Error processing code: {str(e)}")
                print(f"Error in bypass update: {e}")
            return

    words = re.findall(r'\bmeow\b', message.content or "", flags=re.IGNORECASE)
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
        content = message.content.lower() if message.content else ""
        is_text_boost = ("boosted the server" in content or "just boosted" in content)
        is_system_boost = message.type in BOOST_TYPES
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
    print(f'Bot logged in as {bot.user}')
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    except Exception as e:
        print(f"Slash command sync failed: {e}")

def start_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    start_bot()
