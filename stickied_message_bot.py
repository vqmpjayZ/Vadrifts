import os
import asyncio
import json
import discord
from discord.ext import commands
from discord import Embed
from discord import app_commands

GUILD_ID = 1241797935100989594
\ nintents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
\ nstickied_messages = {}

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
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    except:
        pass

@bot.tree.command(name="setstickied", description="Set a stickied message.", guild=discord.Object(id=GUILD_ID))
async def setstickied(interaction: discord.Interaction, message_text: str):
    channel_id = str(interaction.channel_id)
    stickied_messages[channel_id] = {"content": message_text, "embed": None, "last_message": None}
    await save_data()
    await interaction.response.send_message("Stickied message set.", ephemeral=True)

@bot.tree.command(name="setstickiedembed", description="Set a stickied embed.", guild=discord.Object(id=GUILD_ID))
async def setstickiedembed(interaction: discord.Interaction, title: str, description: str):
    channel_id = str(interaction.channel_id)
    embed_data = {"title": title, "description": description}
    stickied_messages[channel_id] = {"content": None, "embed": embed_data, "last_message": None}
    await save_data()
    await interaction.response.send_message("Stickied embed set.", ephemeral=True)

@bot.tree.command(name="removestickied", description="Remove stickied message.", guild=discord.Object(id=GUILD_ID))
async def removestickied(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)
    if channel_id in stickied_messages:
        del stickied_messages[channel_id]
        await save_data()
        await interaction.response.send_message("Stickied message removed.", ephemeral=True)
    else:
        await interaction.response.send_message("No stickied message set.", ephemeral=True)

@bot.tree.command(name="stickiedhelp", description="Show stickied bot help.", guild=discord.Object(id=GUILD_ID))
async def stickiedhelp(interaction: discord.Interaction):
    msg = """
/setstickied <message>
/setstickiedembed <title> <description>
/removestickied
/stickiedhelp
"""
    await interaction.response.send_message(msg, ephemeral=True)

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
