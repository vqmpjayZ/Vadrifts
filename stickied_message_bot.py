import os
import asyncio
import json
from discord import Intents, Embed
from discord.ext import commands
from discord import app_commands

intents = Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

stickied_messages = {}

async def save_data():
    with open("stickied_data.json", "w") as f:
        f.write(json.dumps(stickied_messages))

async def load_data():
    global stickied_messages
    try:
        with open("stickied_data.json", "r") as f:
            stickied_messages = json.loads(f.read())
    except:
        stickied_messages = {}

@bot.event
async def on_ready():
    await load_data()
    await bot.tree.sync()

@bot.tree.command(name="setstickied", description="Set a stickied message for this channel.")
async def setstickied(interaction, message_text: str):
    channel_id = str(interaction.channel_id)
    stickied_messages[channel_id] = {"content": message_text, "embed": None, "last_message": None}
    await save_data()
    await interaction.response.send_message("Stickied message set.", ephemeral=True)

@bot.tree.command(name="setstickiedembed", description="Set a stickied embed for this channel.")
async def setstickiedembed(interaction, title: str, description: str):
    channel_id = str(interaction.channel_id)
    embed_data = {"title": title, "description": description}
    stickied_messages[channel_id] = {"content": None, "embed": embed_data, "last_message": None}
    await save_data()
    await interaction.response.send_message("Stickied embed set.", ephemeral=True)

@bot.tree.command(name="removestickied", description="Remove stickied message from this channel.")
async def removestickied(interaction):
    channel_id = str(interaction.channel_id)
    if channel_id in stickied_messages:
        del stickied_messages[channel_id]
        await save_data()
        await interaction.response.send_message("Stickied message removed.", ephemeral=True)
    else:
        await interaction.response.send_message("No stickied message set.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    channel_id = str(message.channel.id)
    if channel_id in stickied_messages:
        data = stickied_messages[channel_id]
        if data["last_message"]:
            try:
                old_msg = await message.channel.fetch_message(data["last_message"])
                await old_msg.delete()
            except:
                pass
        if data["embed"]:
            embed = Embed(title=data["embed"]["title"], description=data["embed"]["description"])
            new_msg = await message.channel.send(embed=embed)
        else:
            new_msg = await message.channel.send(data["content"])
        stickied_messages[channel_id]["last_message"] = new_msg.id
        await save_data()
    await bot.process_commands(message)

bot.run(os.getenv("STICKIED_TOKEN"))
