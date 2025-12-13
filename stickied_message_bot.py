import os
import json
import time
import discord
from discord.ext import commands
from discord import Embed, app_commands

GUILD_ID = 1241797935100989594

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

stickied_messages = {}

def save_data():
    with open("stickied_data.json", "w") as f:
        json.dump(stickied_messages, f, indent=2)

def load_data():
    global stickied_messages
    try:
        with open("stickied_data.json", "r") as f:
            stickied_messages = json.load(f)
    except:
        stickied_messages = {}

@bot.event
async def on_ready():
    load_data()
    print(f'Stickied bot logged in as {bot.user}')
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} stickied commands")
    except Exception as e:
        print(f"Stickied bot slash command sync failed: {e}")

def create_embed_from_data(data):
    embed = Embed(
        title=data.get("title"),
        description=data.get("description")
    )
    
    if data.get("color"):
        try:
            embed.color = int(data["color"].replace("#", ""), 16)
        except:
            embed.color = 0x9c88ff
    else:
        embed.color = 0x9c88ff
    
    if data.get("footer"):
        embed.set_footer(text=data["footer"])
    
    if data.get("image"):
        embed.set_image(url=data["image"])
    
    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"])
    
    return embed

@bot.tree.command(name="setstickied", description="Set a stickied text message.", guild=discord.Object(id=GUILD_ID))
async def setstickied(
    interaction: discord.Interaction, 
    message_text: str,
    channel: discord.TextChannel = None,
    send_now: bool = False,
    cooldown: int = 0
):
    target_channel = channel or interaction.channel
    channel_id = str(target_channel.id)
    
    stickied_messages[channel_id] = {
        "content": message_text, 
        "embed": None, 
        "last_message": None,
        "cooldown": cooldown,
        "last_sent": 0
    }
    save_data()
    
    if send_now:
        msg = await target_channel.send(message_text)
        stickied_messages[channel_id]["last_message"] = msg.id
        stickied_messages[channel_id]["last_sent"] = time.time()
        save_data()
    
    await interaction.response.send_message(
        f"✅ Stickied message set in {target_channel.mention}" + (" and sent!" if send_now else ""),
        ephemeral=True
    )

@bot.tree.command(name="setstickiedembed", description="Set a stickied embed message.", guild=discord.Object(id=GUILD_ID))
async def setstickiedembed(
    interaction: discord.Interaction, 
    title: str, 
    description: str,
    channel: discord.TextChannel = None,
    send_now: bool = False,
    cooldown: int = 0,
    color: str = None,
    footer: str = None,
    image_url: str = None,
    thumbnail_url: str = None
):
    target_channel = channel or interaction.channel
    channel_id = str(target_channel.id)
    
    embed_data = {
        "title": title, 
        "description": description,
        "color": color,
        "footer": footer,
        "image": image_url,
        "thumbnail": thumbnail_url
    }
    
    stickied_messages[channel_id] = {
        "content": None, 
        "embed": embed_data, 
        "last_message": None,
        "cooldown": cooldown,
        "last_sent": 0
    }
    save_data()
    
    if send_now:
        embed = create_embed_from_data(embed_data)
        msg = await target_channel.send(embed=embed)
        stickied_messages[channel_id]["last_message"] = msg.id
        stickied_messages[channel_id]["last_sent"] = time.time()
        save_data()
    
    await interaction.response.send_message(
        f"✅ Stickied embed set in {target_channel.mention}" + (" and sent!" if send_now else ""),
        ephemeral=True
    )

@bot.tree.command(name="removestickied", description="Remove stickied message from a channel.", guild=discord.Object(id=GUILD_ID))
async def removestickied(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    channel_id = str(target_channel.id)
    
    if channel_id in stickied_messages:
        if stickied_messages[channel_id].get("last_message"):
            try:
                msg = await target_channel.fetch_message(stickied_messages[channel_id]["last_message"])
                await msg.delete()
            except:
                pass
        
        del stickied_messages[channel_id]
        save_data()
        await interaction.response.send_message(f"✅ Stickied message removed from {target_channel.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No stickied message set in {target_channel.mention}.", ephemeral=True)

@bot.tree.command(name="liststickied", description="List all active stickied messages in the server.", guild=discord.Object(id=GUILD_ID))
async def liststickied(interaction: discord.Interaction):
    if not stickied_messages:
        await interaction.response.send_message("No stickied messages set.", ephemeral=True)
        return
    
    embed = Embed(
        title="📌 Active Stickied Messages",
        description=f"Total: {len(stickied_messages)} channel(s)",
        color=0x9c88ff
    )
    
    for channel_id, data in stickied_messages.items():
        channel = bot.get_channel(int(channel_id))
        if channel:
            content_preview = data.get("content") or f"Embed: {data['embed']['title']}"
            if len(content_preview) > 50:
                content_preview = content_preview[:50] + "..."
            
            cooldown_text = f" • {data['cooldown']}s cooldown" if data.get('cooldown', 0) > 0 else ""
            embed.add_field(
                name=f"#{channel.name}",
                value=f"`{content_preview}`{cooldown_text}",
                inline=False
            )
    
    embed.set_footer(text="Use /removestickied to remove them")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stickiedhelp", description="Show stickied bot help and commands.", guild=discord.Object(id=GUILD_ID))
async def stickiedhelp(interaction: discord.Interaction):
    embed = Embed(
        title="📌 Stickied Message Bot",
        description="Keep important messages pinned at the bottom of your channels automatically!",
        color=0x9c88ff
    )
    
    embed.add_field(
        name="📝 /setstickied",
        value=(
            "**Set a text stickied message**\n"
            "`message_text` - Your message\n"
            "`channel` - Where to stick (optional)\n"
            "`send_now` - Send immediately (optional)\n"
            "`cooldown` - Seconds delay between re-sticks (optional)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="✨ /setstickiedembed",
        value=(
            "**Set an embed stickied message**\n"
            "`title` - Embed title\n"
            "`description` - Embed description\n"
            "`channel` - Where to stick (optional)\n"
            "`send_now` - Send immediately (optional)\n"
            "`cooldown` - Seconds delay (optional)\n"
            "`color` - Hex color like #9c88ff (optional)\n"
            "`footer` - Footer text (optional)\n"
            "`image_url` - Full image URL (optional)\n"
            "`thumbnail_url` - Small thumbnail URL (optional)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🗑️ /removestickied",
        value="**Remove a stickied message**\n`channel` - Channel to remove from (optional)",
        inline=False
    )
    
    embed.add_field(
        name="📋 /liststickied",
        value="**View all active stickied messages** in the server",
        inline=False
    )
    
    embed.add_field(
        name="💡 Pro Tips",
        value=(
            "• Use `cooldown` to prevent spam (e.g. 10 = only re-stick every 10 seconds)\n"
            "• Use `send_now=True` to test your stickied message instantly\n"
            "• Embed colors use hex codes without # (e.g. 9c88ff for purple)"
        ),
        inline=False
    )
    
    embed.set_footer(text="Made with 💜 by Vadrifts")
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    channel_id = str(message.channel.id)
    if channel_id in stickied_messages:
        data = stickied_messages[channel_id]
        
        cooldown = data.get("cooldown", 0)
        last_sent = data.get("last_sent", 0)
        
        if cooldown > 0 and (time.time() - last_sent) < cooldown:
            return
        
        if data["last_message"]:
            try:
                old_msg = await message.channel.fetch_message(data["last_message"])
                await old_msg.delete()
            except:
                pass
        
        if data["embed"]:
            embed = create_embed_from_data(data["embed"])
            new_msg = await message.channel.send(embed=embed)
        else:
            new_msg = await message.channel.send(data["content"])
        
        stickied_messages[channel_id]["last_message"] = new_msg.id
        stickied_messages[channel_id]["last_sent"] = time.time()
        save_data()
    
    await bot.process_commands(message)

def start_stickied_bot():
    token = os.getenv("STICKIED_TOKEN")
    if not token:
        print("ERROR: STICKIED_TOKEN environment variable not set!")
        return
    bot.run(token)

if __name__ == "__main__":
    start_stickied_bot()
