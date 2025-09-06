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
from datetime import datetime, timedelta
import json

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

bypass_test_data = {
    "words": {
        "success_rate": "unknown",
        "last_tested": None,
        "testing": False,
        "first_tester": None
    },
    "sentences": {
        "success_rate": "unknown", 
        "last_tested": None,
        "testing": False,
        "first_tester": None
    },
    "roleplay": {
        "success_rate": "unknown",
        "last_tested": None,
        "testing": False,
        "first_tester": None
    },
    "nsfw_websites": {
        "success_rate": "unknown",
        "last_tested": None,
        "testing": False,
        "first_tester": None
    },
    "not_legit": {
        "success_rate": "unknown",
        "last_tested": None,
        "testing": False,
        "first_tester": None
    }
}

def reset_bypass_data():
    global bypass_test_data
    for category in bypass_test_data:
        bypass_test_data[category] = {
            "success_rate": "unknown",
            "last_tested": None,
            "testing": False,
            "first_tester": None
        }
    logger.info("Bypass test data reset")

def check_and_reset_if_needed():
    for category, data in bypass_test_data.items():
        if data["last_tested"]:
            last_test_time = datetime.fromisoformat(data["last_tested"])
            if datetime.now() - last_test_time > timedelta(hours=24):
                data["success_rate"] = "unknown"
                data["last_tested"] = None
                data["testing"] = False
                data["first_tester"] = None

def daily_reset_task():
    while True:
        check_and_reset_if_needed()
        time.sleep(3600)

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

def inject_meta_tags(html_content, meta_tags):
    if '<head>' in html_content:
        return html_content.replace('<head>', f'<head>\n{meta_tags}')
    return html_content

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
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = '''
    <meta property="og:title" content="Vadrifts - Roblox Scripts & Tools">
    <meta property="og:description" content="Vadrift's all-in-one website! Check out everything made by Vadrifts such as Discord server, Image converter, Roblox Scripts and More!!">
    <meta property="og:image" content="https://i.imgur.com/PIHDQJf.png">
    <meta property="og:url" content="https://vadrifts.onrender.com/">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Vadrifts - Roblox Scripts & Tools">
    <meta name="twitter:description" content="Vadrift's all-in-one website! Check out everything made by Vadrifts such as Discord server, Image converter, Roblox Scripts and More!!">
    <meta name="twitter:image" content="https://i.imgur.com/PIHDQJf.png">
    <meta name="theme-color" content="#7289DA">'''
        
        return inject_meta_tags(html_content, meta_tags)
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
    script = next((s for s in scripts_data if s['id'] == script_id), None)
    
    if not script:
        return jsonify({"error": "Script not found"}), 404
    
    try:
        with open('templates/script-detail.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = f'''
    <meta property="og:title" content="{script['title']} - Vadrifts">
    <meta property="og:description" content="{script['description']}">
    <meta property="og:image" content="{script['thumbnail']}">
    <meta property="og:url" content="https://vadrifts.onrender.com/script/{script['id']}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{script['title']} - Vadrifts">
    <meta name="twitter:description" content="{script['description']}">
    <meta name="twitter:image" content="{script['thumbnail']}">
    <meta name="theme-color" content="#7289DA">'''
        
        return inject_meta_tags(html_content, meta_tags)
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

@app.route('/api/bypass-status')
def get_bypass_status():
    check_and_reset_if_needed()
    return jsonify(bypass_test_data)

@app.route('/api/bypass-status/<category>', methods=['GET'])
def get_category_status(category):
    if category not in bypass_test_data:
        return jsonify({"error": "Invalid category"}), 404
    
    check_and_reset_if_needed()
    return jsonify({category: bypass_test_data[category]})

@app.route('/api/bypass-status/<category>/start', methods=['POST'])
def start_bypass_test(category):
    if category not in bypass_test_data:
        return jsonify({"error": "Invalid category"}), 404
    
    check_and_reset_if_needed()
    
    data = bypass_test_data[category]
    player_id = request.json.get('player_id', 'Unknown')
    
    if data["testing"]:
        return jsonify({"error": "Already testing", "status": "testing"}), 409
    
    if data["success_rate"] != "unknown":
        return jsonify({"error": "Already tested today", "status": "completed", "success_rate": data["success_rate"]}), 200
    
    data["testing"] = True
    data["first_tester"] = player_id
    
    return jsonify({
        "status": "started",
        "message": "You're the first today!",
        "first_tester": True
    })

@app.route('/api/bypass-status/<category>/complete', methods=['POST'])
def complete_bypass_test(category):
    if category not in bypass_test_data:
        return jsonify({"error": "Invalid category"}), 404
    
    data = bypass_test_data[category]
    success_rate = request.json.get('success_rate')
    
    if not isinstance(success_rate, (int, float)) or success_rate < 0 or success_rate > 100:
        return jsonify({"error": "Invalid success rate"}), 400
    
    data["success_rate"] = f"{int(success_rate)}%"
    data["last_tested"] = datetime.now().isoformat()
    data["testing"] = False
    
    return jsonify({
        "status": "completed",
        "success_rate": data["success_rate"]
    })

@app.route('/api/bypass-status/webpage')
def bypass_status_webpage():
    check_and_reset_if_needed()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bypass Status - Vadrifts</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #1a1a1a;
                color: #ffffff;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                text-align: center;
                color: #7289DA;
            }
            .status-grid {
                display: grid;
                gap: 20px;
                margin-top: 30px;
            }
            .status-item {
                background-color: #2a2a2a;
                padding: 20px;
                border-radius: 10px;
                border: 2px solid #3a3a3a;
            }
            .category-name {
                font-size: 20px;
                font-weight: bold;
                color: #7289DA;
                margin-bottom: 10px;
            }
            .success-rate {
                font-size: 24px;
                font-weight: bold;
            }
            .success-rate.high {
                color: #00FF00;
            }
            .success-rate.medium {
                color: #FFFF00;
            }
            .success-rate.low {
                color: #FF0000;
            }
            .success-rate.unknown {
                color: #888888;
            }
            .testing {
                color: #00BFFF;
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .last-tested {
                font-size: 12px;
                color: #888888;
                margin-top: 5px;
            }
        </style>
        <meta http-equiv="refresh" content="30">
    </head>
    <body>
        <div class="container">
            <h1>Bypass Status Dashboard</h1>
            <div class="status-grid">
    """
    
    category_names = {
        "words": "Words",
        "sentences": "Sentences",
        "roleplay": "Roleplay",
        "nsfw_websites": "NSFW Websites",
        "not_legit": "Not Legit"
    }
    
    for category, display_name in category_names.items():
        data = bypass_test_data[category]
        success_rate = data["success_rate"]
        
        if data["testing"]:
            rate_class = "testing"
            rate_text = "Testing..."
        elif success_rate == "unknown":
            rate_class = "unknown"
            rate_text = "Unknown"
        else:
            rate_value = int(success_rate.rstrip('%'))
            rate_text = success_rate + " success rate"
            if rate_value >= 70:
                rate_class = "high"
            elif rate_value >= 40:
                rate_class = "medium"
            else:
                rate_class = "low"
        
        last_tested_text = ""
        if data["last_tested"]:
            last_tested_time = datetime.fromisoformat(data["last_tested"])
            time_ago = datetime.now() - last_tested_time
            hours_ago = int(time_ago.total_seconds() / 3600)
            if hours_ago < 1:
                last_tested_text = f"<div class='last-tested'>Tested less than an hour ago</div>"
            else:
                last_tested_text = f"<div class='last-tested'>Tested {hours_ago} hours ago</div>"
        
        html += f"""
                <div class="status-item">
                    <div class="category-name">{display_name}</div>
                    <div class="success-rate {rate_class}">{rate_text}</div>
                    {last_tested_text}
                </div>
        """
    
    html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

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
    
    reset_thread = threading.Thread(target=daily_reset_task, daemon=True)
    reset_thread.start()
    logger.info("Daily reset task started")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot thread started")
    
    run_flask()
