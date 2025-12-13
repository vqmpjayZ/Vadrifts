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

@bot.tree.command(name="stick", description="Set a stickied text message.")
@app_commands.default_permissions(manage_messages=True)
async def stick(
    interaction: discord.Interaction, 
    message: str,
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
        "content": message, 
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
                content=message,
                username=webhook_name or "Stickied Message",
                avatar_url=webhook_avatar,
                wait=True
            )
        else:
            msg = await target_channel.send(message)
        
        stickied_messages[channel_key]["last_message"] = msg.id
        stickied_messages[channel_key]["last_sent"] = time.time()
        save_data()
        
        await interaction.followup.send(f"✅ Stickied message set in {target_channel.mention}!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="stickembed", description="Set a stickied embed message.")
@app_commands.default_permissions(manage_messages=True)
async def stickembed(
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
        
        await interaction.followup.send(f"✅ Stickied embed set in {target_channel.mention}!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="unstick", description="Remove stickied message from a channel.")
@app_commands.default_permissions(manage_messages=True)
async def unstick(interaction: discord.Interaction, channel: discord.TextChannel = None):
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
        await interaction.followup.send(f"❌ No stickied message in {target_channel.mention}.")

@bot.tree.command(name="list", description="List all active stickied messages in this server.")
@app_commands.default_permissions(manage_messages=True)
async def list_stickied(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    server_stickied = {k: v for k, v in stickied_messages.items() if k.startswith(f"{interaction.guild_id}_")}
    
    if not server_stickied:
        await interaction.followup.send("No stickied messages set in this server.")
        return
    
    embed = Embed(
        title="📌 Active Stickied Messages",
        description=f"Total: {len(server_stickied)} channel(s)",
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
            webhook_text = " • Webhook" if data.get('use_webhook') else ""
            embed.add_field(
                name=f"#{channel.name}",
                value=f"`{content_preview}`{cooldown_text}{webhook_text}",
                inline=False
            )
    
    embed.set_footer(text="Use /unstick to remove")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="Show bot commands and info.")
async def help_command(interaction: discord.Interaction):
    embed = Embed(
        title="📌 Stickied Bot",
        description="Keep important messages pinned at the bottom of your channels!",
        color=0x9c88ff
    )
    
    embed.add_field(
        name="📝 /stick",
        value=(
            "**Set a text stickied message**\n"
            "`message` - Your message\n"
            "`channel` - Target channel (optional)\n"
            "`cooldown` - Seconds between re-sticks (optional)\n"
            "`use_webhook` - Custom appearance (optional)\n"
            "`webhook_name` - Custom name (optional)\n"
            "`webhook_avatar` - Custom avatar URL (optional)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="✨ /stickembed",
        value=(
            "**Set an embed stickied message**\n"
            "`title` - Embed title\n"
            "`description` - Embed description\n"
            "`channel` - Target channel (optional)\n"
            "`cooldown` - Seconds between re-sticks (optional)\n"
            "`color` - Hex color like #9c88ff (optional)\n"
            "`footer` - Footer text (optional)\n"
            "`image_url` - Large image (optional)\n"
            "`thumbnail_url` - Small image (optional)\n"
            "`use_webhook` - Custom appearance (optional)\n"
            "`webhook_name` - Custom name (optional)\n"
            "`webhook_avatar` - Custom avatar URL (optional)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🗑️ /unstick",
        value="**Remove a stickied message**\n`channel` - Target channel (optional)",
        inline=False
    )
    
    embed.add_field(
        name="📋 /list",
        value="**View all stickied messages** in this server",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value=(
            "• `cooldown` prevents spam (10 = wait 10s before re-sticking)\n"
            "• Webhooks let you customize name & avatar\n"
            "• Messages send instantly when set\n"
            "• Colors use hex codes without # (e.g. 9c88ff)"
        ),
        inline=False
    )
    
    embed.set_footer(text="Made with 💜 by Vadrifts • Requires Manage Messages")
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if not message.guild:
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
