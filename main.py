import os
import logging
import time
import threading
import requests
import asyncio
from flask import Flask, request, jsonify, send_from_directory, send_file, render_template_string, redirect
from PIL import Image
from io import BytesIO
import discord
from discord.ext import commands, tasks
from collections import defaultdict
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
TARGET_CHANNEL_ID = 1389210900489044048
DELAY_SECONDS = 2

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_boosts = {}
pending_tasks = {}

thumbnail_cache = {}
game_data_cache = {}

active_slugs = {}

def generate_key(hwid):
    period = int(time.time() // (60 * 60 * 48))
    hash_input = f"{hwid}{period}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

def create_slug(hwid):
    import random
    import string
    slug = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    active_slugs[slug] = hwid
    
    def remove_slug():
        if slug in active_slugs:
            del active_slugs[slug]
    
    timer = threading.Timer(300, remove_slug)
    timer.start()
    
    return slug

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

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
    if message.channel.id == TARGET_CHANNEL_ID:
        if "just boosted the server!" in message.content.lower():
            user_id = message.author.id
            recent_boosts[user_id] = True
            if user_id in pending_tasks:
                pending_tasks[user_id].cancel()
            pending_tasks[user_id] = bot.loop.create_task(send_good_boy_after_delay(user_id, message.channel))
    await bot.process_commands(message)

def resize_with_crop(image, target_size=(32, 32)):
    original_width, original_height = image.size
    target_width, target_height = target_size
    
    scale_w = target_width / original_width
    scale_h = target_height / original_height
    scale = max(scale_w, scale_h)
    
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)
    
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    cropped_image = resized_image.crop((left, top, right, bottom))
    
    return cropped_image

def convert_rblx_asset_url(url):
    return url

def get_roblox_game_data(place_id):
    return None, None, f"https://www.roblox.com/games/{place_id}"

def process_script_data(scripts):
    for script in scripts:
        if str(script.get('id', '')).isdigit():
            script['game_link'] = f"https://www.roblox.com/games/{script['id']}"
        elif script.get('game', '').lower() == 'universal':
            script['game_link'] = "https://www.roblox.com/games"
        else:
            script['game_link'] = "https://www.roblox.com/games"
    
    return scripts

scripts_data = [
    {
        "id": 1,
        "title": "Vadrifts.byp",
        "game": "Universal",
        "thumbnail": "https://i.imgur.com/jI8qDiR.jpeg",
        "description": "Best and undetected Roblox Chat Bypasser. Bypasses the Roblox Chat Filters allowing you to Swear on roblox!",
        "features": [
            "Chat Bypass",
            "Mobile Friendly", 
            "Works on ALL executors",
            "Automatic chat bypasser",
            "Tag Detection",
            "700+ Premade bypasses",
            "Anti Admin",
            "Anti Chat Ban",
            "Sus Animations",
            "Bang",
            "Chat tools AND MORE!!",
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/Bypass/main/vadrifts.lua"))()''',
        "key_type": "discord",
        "key_link": "https://discord.com/invite/WDbJ5wE2cR"
        },
    {
        "id": 8916037983,
        "title": "Starving Artists Script",
        "game": "Starving Artists",
        "thumbnail": "https://tr.rbxcdn.com/180DAY-808f20386cb8582fcd0075aae67cd039/768/432/Image/Webp/noFilter",
        "description": "A Free starving artists script by Vadrifts with a simple and easy Discord Key System. Generate images by getting an image url online, and then pasting the url in the textbox!",
        "features": [
            "Reliable, undetected AND Customiseable Image generator",
            "Mobile Friendly", 
            "ALL executor support",
            "Automatic Booth Claimer",
            "Advanced Customizable Server Hopper",
            "Webhook Notifier",
            "Customizable Auto Beg",
            "Automatic Thank for donations and tips",
            "Anti-AFK",
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/Vadrifts-Hub/refs/heads/main/Games/Starving-Artists/source.lua"))()''',
        "key_type": "discord",
        "key_link": "https://discord.com/invite/WDbJ5wE2cR"
       # "key_type": "ad-websites",
       # "key_system": {
       #     "work_ink": "https://workink.net/20yd/vadriftscb",
       #     "lootlabs": "https://lootdest.org/s?vadriftscb"
    },
    {
        "id": 263761432,
        "title": "Horrific Housing Script",
        "game": "Horrific Housing",
        "thumbnail": "https://tr.rbxcdn.com/180DAY-8598e6c1626e3ccf16eb8b3acbd618fe/768/432/Image/Webp/noFilter",
        "description": "Best keyless Horrific Housing script with tons of features!",
        "features": [
            "Keyless",
            "Mobile Friendly", 
            "ALL executor support",
            "Infinite tokens",
            "Unlock all items for free",
            "ESP",
            "Reach",
            "Item Grabber",
            "Weapon Exploit (Spam weapon)",
            "Reset cooldowns",
            "Fly",
            "Godmode",
            "Teleportation",
            "Auto event remover",
            "And SO MUCH MORE!!",
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/More-Scripts/refs/heads/main/Vadrifts-Horrific-Housing.lua"))()''',
        "key_type": "no-key"
    },
]

def server_pinger():
    while True:
        try:
            requests.get("https://vadrifts.onrender.com/health", timeout=10)
            logger.info("Server pinged successfully")
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        time.sleep(300)

@app.route('/')
def home():
    try:
        return send_file('templates/index.html')
    except FileNotFoundError:
        logger.error("index.html template not found")
        return jsonify({
            "message": "Vadrifts - Your ultimate Roblox scripting platform",
            "status": "deployed",
            "endpoints": {
                "scripts": "GET /api/scripts - Get all scripts",
                "script_detail": "GET /api/scripts/<id> - Get script details", 
                "converter": "GET /converter - Image converter tool",
                "convert_image": "GET /convert-image?url=<url>&crop=<true|false> - Convert image to pixels"
            }
        }), 200

@app.route('/discord')
def discord_invite():
    return redirect("https://discord.com/invite/WDbJ5wE2cR")

@app.route('/templates/<path:filename>')
def serve_templates(filename):
    return send_from_directory('templates', filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/api/scripts')
def get_scripts():
    search = request.args.get('search', '').lower()
    
    processed_scripts = process_script_data(scripts_data.copy())
    
    if search:
        filtered_scripts = [
            script for script in processed_scripts 
            if search in script['title'].lower() or search in script['game'].lower()
        ]
        return jsonify(filtered_scripts)
    return jsonify(processed_scripts)

@app.route('/api/scripts/<int:script_id>')
def get_script_detail(script_id):
    processed_scripts = process_script_data(scripts_data.copy())
    script = next((s for s in processed_scripts if s['id'] == script_id), None)
    if script:
        return jsonify(script)
    return jsonify({"error": "Script not found"}), 404

@app.route('/script/<int:script_id>')
def script_detail(script_id):
    try:
        return send_file('templates/script-detail.html')
    except FileNotFoundError:
        logger.error("script-detail.html template not found")
        return jsonify({"error": "Script detail page not found"}), 404

@app.route('/converter')
def converter():
    try:
        return send_file('templates/converter.html')
    except FileNotFoundError:
        logger.error("converter.html template not found")
        return jsonify({
            "error": "Converter page not found",
            "message": "Create templates/converter.html file"
        }), 404

@app.route('/convert-image', methods=['GET'])
def convert_image():
    start_time = time.time()
    logger.info("Convert image endpoint accessed")
    
    image_url = request.args.get('url')
    crop_mode = request.args.get('crop', 'true').lower() == 'true'
    
    if not image_url:
        logger.warning("No URL provided in request")
        return jsonify({'error': 'No URL provided in query parameters'}), 400

    original_url = image_url
    image_url = convert_rblx_asset_url(image_url)
    
    if original_url != image_url:
        logger.info(f"Converted Roblox asset URL: {original_url} -> {image_url}")
    
    logger.info(f"Processing image from URL: {image_url}, crop_mode: {crop_mode}")
    
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            logger.error(f"Failed to fetch image: HTTP {response.status_code}")
            return jsonify({'error': f'Failed to fetch image: HTTP {response.status_code}'}), 500
        try:
            image = Image.open(BytesIO(response.content))
        except Exception as e:
            logger.error(f"Failed to open image: {str(e)}")
            return jsonify({'error': f'Failed to open image: {str(e)}'}), 500

        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        original_size = image.size
        
        if crop_mode:
            image = resize_with_crop(image, (32, 32))
            resize_method = "crop"
        else:
            image = image.resize((32, 32), Image.LANCZOS)
            resize_method = "simple_resize"
        
        pixels = []
        try:
            for y in range(image.height):
                for x in range(image.width):
                    pixel = image.getpixel((x, y))
                    if len(pixel) >= 3:
                        r, g, b = pixel[:3]
                    else:
                        r = g = b = pixel if isinstance(pixel, int) else pixel[0]
                    pixels.append({'R': r, 'G': g, 'B': b})
        except Exception as e:
            logger.error(f"Error processing pixels: {str(e)}")
            return jsonify({'error': f'Error processing pixels: {str(e)}'}), 500
        
        processing_time = time.time() - start_time
        logger.info(f"Image processed successfully in {processing_time:.2f} seconds using {resize_method}")
        
        return jsonify({
            'pixels': pixels,
            'processing_time': processing_time,
            'original_size': original_size,
            'final_size': [32, 32],
            'resize_method': resize_method,
            'crop_mode': crop_mode
        })
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return jsonify({'error': 'Request timed out fetching the image'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'error': f'Request error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/key-system')
def key_system():
    try:
        return send_file('templates/key-system.html')
    except FileNotFoundError:
        logger.error("key-system.html template not found")
        return jsonify({"error": "Key system page not found"}), 404

@app.route('/create')
def create_key():
    hwid = request.args.get('hwid')
    if not hwid:
        return "Missing HWID", 400
    
    slug = create_slug(hwid)
    return f"https://{request.headers.get('host')}/getkey/{slug}"

@app.route('/getkey/<slug>')
def get_key(slug):
    hwid = active_slugs.get(slug)
    if not hwid:
        return "Invalid or expired key link", 404
    
    del active_slugs[slug]
    key = generate_key(hwid)
    return key

@app.route('/verify')
def verify():
    try:
        return send_file('templates/verify.html')
    except FileNotFoundError:
        logger.error("verify.html template not found")
        return jsonify({"error": "Verify page not found"}), 404

def run_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        logger.error(f"Discord bot error: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Vadrifts Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    ping_thread = threading.Thread(target=server_pinger, daemon=True)
    ping_thread.start()
    logger.info("Server pinger started")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot thread started")
    
    run_flask()
