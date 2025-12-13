import os
import json
import time
import discord
from discord.ext import commands
from discord import Embed, app_commands

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.webhooks = True
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
    print(f'Bot is in {len(bot.guilds)} servers')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global commands")
    except Exception as e:
        print(f"Slash command sync failed: {e}")

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

async def get_or_create_webhook(channel):
    webhooks = await channel.webhooks()
    webhook = discord.utils.get(webhooks, name="Stickied Bot")
    
    if webhook is None:
        webhook = await channel.create_webhook(name="Stickied Bot")
    
    return webhook

def get_channel_key(guild_id, channel_id):
    return f"{guild_id}_{channel_id}"

@bot.tree.command(name="setstickied", description="Set a stickied text message.")
@app_commands.default_permissions(manage_messages=True)
async def setstickied(
    interaction: discord.Interaction, 
    message_text: str,
    channel: discord.TextChannel = None,
    cooldown: int = 0,
    use_webhook: bool = False,
    webhook_name: str = None,
    webhook_avatar: str = None
):
    await interaction.response.defer(ephemeral=True)
    
    target_channel = channel or interaction.channel
    channel_key = get_channel_key(interaction.guild_id, target_channel.id)
    
    stickied_messages[channel_key] = {
        "content": message_text, 
        "embed": None, 
        "last_message": None,
        "cooldown": cooldown,
        "last_sent": 0,
        "use_webhook": use_webhook,
        "webhook_name": webhook_name,
        "webhook_avatar": webhook_avatar
    }
    save_data()
    
    try:
        if use_webhook:
            webhook = await get_or_create_webhook(target_channel)
            msg = await webhook.send(
                content=message_text,
                username=webhook_name or "Stickied Message",
                avatar_url=webhook_avatar,
                wait=True
            )
        else:
            msg = await target_channel.send(message_text)
        
        stickied_messages[channel_key]["last_message"] = msg.id
        stickied_messages[channel_key]["last_sent"] = time.time()
        save_data()
        
        await interaction.followup.send(f"✅ Stickied message set and sent in {target_channel.mention}!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="setstickiedembed", description="Set a stickied embed message.")
@app_commands.default_permissions(manage_messages=True)
async def setstickiedembed(
    interaction: discord.Interaction, 
    title: str, 
    description: str,
    channel: discord.TextChannel = None,
    cooldown: int = 0,
    color: str = None,
    footer: str = None,
    image_url: str = None,
    thumbnail_url: str = None,
    use_webhook: bool = False,
    webhook_name: str = None,
    webhook_avatar: str = None
):
    await interaction.response.defer(ephemeral=True)
    
    target_channel = channel or interaction.channel
    channel_key = get_channel_key(interaction.guild_id, target_channel.id)
    
    embed_data = {
        "title": title, 
        "description": description,
        "color": color,
        "footer": footer,
        "image": image_url,
        "thumbnail": thumbnail_url
    }
    
    stickied_messages[channel_key] = {
        "content": None, 
        "embed": embed_data, 
        "last_message": None,
        "cooldown": cooldown,
        "last_sent": 0,
        "use_webhook": use_webhook,
        "webhook_name": webhook_name,
        "webhook_avatar": webhook_avatar
    }
    save_data()
    
    try:
        embed = create_embed_from_data(embed_data)
        
        if use_webhook:
            webhook = await get_or_create_webhook(target_channel)
            msg = await webhook.send(
                embed=embed,
                username=webhook_name or "Stickied Message",
                avatar_url=webhook_avatar,
                wait=True
            )
        else:
            msg = await target_channel.send(embed=embed)
        
        stickied_messages[channel_key]["last_message"] = msg.id
        stickied_messages[channel_key]["last_sent"] = time.time()
        save_data()
        
        await interaction.followup.send(f"✅ Stickied embed set and sent in {target_channel.mention}!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="removestickied", description="Remove stickied message from a channel.")
@app_commands.default_permissions(manage_messages=True)
async def removestickied(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    
    target_channel = channel or interaction.channel
    channel_key = get_channel_key(interaction.guild_id, target_channel.id)
    
    if channel_key in stickied_messages:
        if stickied_messages[channel_key].get("last_message"):
            try:
                msg = await target_channel.fetch_message(stickied_messages[channel_key]["last_message"])
                await msg.delete()
            except:
                pass
        
        del stickied_messages[channel_key]
        save_data()
        await interaction.followup.send(f"✅ Stickied message removed from {target_channel.mention}.")
    else:
        await interaction.followup.send(f"❌ No stickied message set in {target_channel.mention}.")

@bot.tree.command(name="liststickied", description="List all active stickied messages in this server.")
@app_commands.default_permissions(manage_messages=True)
async def liststickied(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    server_stickied = {k: v for k, v in stickied_messages.items() if k.startswith(f"{interaction.guild_id}_")}
    
    if not server_stickied:
        await interaction.followup.send("No stickied messages set in this server.")
        return
    
    embed = Embed(
        title="📌 Active Stickied Messages",
        description=f"Total: {len(server_stickied)} channel(s) in this server",
        color=0x9c88ff
    )
    
    for channel_key, data in server_stickied.items():
        channel_id = int(channel_key.split("_")[1])
        channel = bot.get_channel(channel_id)
        if channel:
            content_preview = data.get("content") or f"Embed: {data['embed']['title']}"
            if len(content_preview) > 50:
                content_preview = content_preview[:50] + "..."
            
            cooldown_text = f" • {data['cooldown']}s cooldown" if data.get('cooldown', 0) > 0 else ""
            webhook_text = " • Via Webhook" if data.get('use_webhook') else ""
            embed.add_field(
                name=f"#{channel.name}",
                value=f"`{content_preview}`{cooldown_text}{webhook_text}",
                inline=False
            )
    
    embed.set_footer(text="Use /removestickied to remove them")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="stickiedhelp", description="Show stickied bot help and commands.")
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
            "`cooldown` - Seconds delay between re-sticks (optional)\n"
            "`use_webhook` - Send via webhook (optional)\n"
            "`webhook_name` - Custom name (optional)\n"
            "`webhook_avatar` - Custom avatar URL (optional)"
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
            "`cooldown` - Seconds delay (optional)\n"
            "`color` - Hex color like #9c88ff (optional)\n"
            "`footer` - Footer text (optional)\n"
            "`image_url` - Full image URL (optional)\n"
            "`thumbnail_url` - Small thumbnail URL (optional)\n"
            "`use_webhook` - Send via webhook (optional)\n"
            "`webhook_name` - Custom name (optional)\n"
            "`webhook_avatar` - Custom avatar URL (optional)"
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
        value="**View all active stickied messages** in this server",
        inline=False
    )
    
    embed.add_field(
        name="💡 Pro Tips",
        value=(
            "• Use `cooldown` to prevent spam (e.g. 10 = only re-stick every 10 seconds)\n"
            "• Webhooks let you customize the name/avatar of stickied messages\n"
            "• Messages are sent instantly when you set them\n"
            "• Embed colors use hex codes (e.g. 9c88ff for purple)"
        ),
        inline=False
    )
    
    embed.set_footer(text="Made with 💜 by Vadrifts • Requires Manage Messages permission")
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    channel_key = get_channel_key(message.guild.id, message.channel.id)
    
    if channel_key in stickied_messages:
        data = stickied_messages[channel_key]
        
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
        
        try:
            if data.get("use_webhook"):
                webhook = await get_or_create_webhook(message.channel)
                
                if data["embed"]:
                    embed = create_embed_from_data(data["embed"])
                    new_msg = await webhook.send(
                        embed=embed,
                        username=data.get("webhook_name") or "Stickied Message",
                        avatar_url=data.get("webhook_avatar"),
                        wait=True
                    )
                else:
                    new_msg = await webhook.send(
                        content=data["content"],
                        username=data.get("webhook_name") or "Stickied Message",
                        avatar_url=data.get("webhook_avatar"),
                        wait=True
                    )
            else:
                if data["embed"]:
                    embed = create_embed_from_data(data["embed"])
                    new_msg = await message.channel.send(embed=embed)
                else:
                    new_msg = await message.channel.send(data["content"])
            
            stickied_messages[channel_key]["last_message"] = new_msg.id
            stickied_messages[channel_key]["last_sent"] = time.time()
            save_data()
        except Exception as e:
            print(f"Error sending stickied message: {e}")
    
    await bot.process_commands(message)

def start_stickied_bot():
    token = os.getenv("STICKIED_TOKEN")
    if not token:
        print("ERROR: STICKIED_TOKEN environment variable not set!")
        return
    bot.run(token)

if __name__ == "__main__":
    start_stickied_bot()
