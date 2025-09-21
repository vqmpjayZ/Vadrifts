import os
import logging
import time
import threading
import requests
import asyncio
import re
from flask import Flask, request, jsonify, send_from_directory, send_file, render_template_string, redirect
from PIL import Image
from io import BytesIO
import discord
from discord.ext import commands, tasks
from collections import defaultdict
import hashlib
from datetime import datetime, timedelta
import json
from urllib.parse import quote_plus
import uuid

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

channel_cache = {}
CACHE_DURATION = 7200

plugins_data = []
rate_limit_data = {}

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
    }
}

class YouTubeChannelFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def find_channel_by_username(self, username):
        cache_key = username.lower().strip()
        if cache_key in channel_cache:
            cached = channel_cache[cache_key]
            if time.time() - cached['timestamp'] < CACHE_DURATION:
                return cached['data']
        
        logger.info(f"Finding channel for username: {username}")
        
        possible_urls = [
            f"https://www.youtube.com/@{username}",
            f"https://www.youtube.com/c/{username}",
            f"https://www.youtube.com/user/{username}",
            f"https://www.youtube.com/{username}"
        ]
        
        for url in possible_urls:
            try:
                response = self.session.get(url, timeout=10, allow_redirects=True)
                
                if response.status_code == 200 and 'youtube.com' in response.url:
                    channel_data = self.extract_channel_data(response.text, response.url, username)
                    if channel_data:
                        channel_cache[cache_key] = {
                            'data': channel_data,
                            'timestamp': time.time()
                        }
                        logger.info(f"Found channel for {username}: {channel_data['url']}")
                        return channel_data
                        
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                continue
        
        search_result = self.search_for_channel(username)
        if search_result:
            channel_cache[cache_key] = {
                'data': search_result,
                'timestamp': time.time()
            }
            return search_result
        
        logger.warning(f"Could not find channel for username: {username}")
        return {
            'name': username,
            'handle': f'@{username}',
            'url': f'https://www.youtube.com/@{username}',
            'pfp_url': None,
            'found': False
        }
    
    def extract_channel_data(self, html_content, url, username):
        try:
            channel_name = self.extract_channel_name(html_content)
            pfp_url = self.extract_profile_picture(html_content)
            
            handle = f'@{username}'
            if '"canonicalChannelUrl":"https://www.youtube.com/@' in html_content:
                handle_match = re.search(r'"canonicalChannelUrl":"https://www\.youtube\.com/@([^"]+)"', html_content)
                if handle_match:
                    handle = f'@{handle_match.group(1)}'
            
            return {
                'name': channel_name or username,
                'handle': handle,
                'url': url,
                'pfp_url': pfp_url,
                'found': True
            }
        except Exception as e:
            logger.error(f"Error extracting channel data: {e}")
            return None
    
    def extract_channel_name(self, html_content):
        patterns = [
            r'"channelMetadataRenderer":{"title":"([^"]+)"',
            r'<meta property="og:title" content="([^"]+)"',
            r'"title":"([^"]+)","navigationEndpoint"',
            r'<title>([^<]+)</title>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                name = match.group(1).strip()
                if name and name != 'YouTube':
                    return name
        return None
    
    def extract_profile_picture(self, html_content):
        patterns = [
            r'"channelMetadataRenderer":{"title":"([^"]+)"',
            r'<meta property="og:title" content="([^"]+)"',
            r'"title":"([^"]+)","navigationEndpoint"',
            r'<title>([^<]+)</title>'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html_content)
            for match in matches:
                img_url = match.group(1)
                img_url = img_url.replace('\\u003d', '=').replace('\\', '')
                
                if self.validate_image_url(img_url):
                    return img_url
        
        yt3_pattern = r'(https?://yt3\.ggpht\.com[^"]*)'
        matches = re.findall(yt3_pattern, html_content)
        for url in matches:
            if self.validate_image_url(url):
                return url
        
        return None
    
    def search_for_channel(self, username):
        try:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(username)}&sp=EgIQAg%253D%253D"
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                channel_links = re.findall(r'"url":"(/channel/[^"]+)"', response.text)
                handle_links = re.findall(r'"url":"(/@[^"]+)"', response.text)
                
                all_links = []
                for link in channel_links + handle_links:
                    if link.startswith('/'):
                        all_links.append(f"https://www.youtube.com{link}")
                
                for link in all_links[:3]:
                    try:
                        channel_response = self.session.get(link, timeout=10)
                        if channel_response.status_code == 200:
                            channel_data = self.extract_channel_data(channel_response.text, link, username)
                            if channel_data and channel_data.get('pfp_url'):
                                return channel_data
                    except:
                        continue
        except Exception as e:
            logger.error(f"Search failed for {username}: {e}")
        
        return None
    
    def validate_image_url(self, url):
        try:
            if not url or not url.startswith('http'):
                return False
            
            response = self.session.head(url, timeout=5)
            content_type = response.headers.get('content-type', '').lower()
            
            return (response.status_code == 200 and 
                    ('image' in content_type or url.endswith(('.jpg', '.jpeg', '.png', '.webp'))))
        except:
            return False

youtube_finder = YouTubeChannelFinder()

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
    
    if "meow" in message.content.lower():
        await message.channel.send("meow")
    
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
            "400+ Premade bypasses",
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

def cleanup_expired_cache():
    current_time = time.time()
    keys_to_remove = []
    
    for key, data in channel_cache.items():
        if current_time - data['timestamp'] >= CACHE_DURATION:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del channel_cache[key]
    
    if keys_to_remove:
        logger.info(f"Cleaned up {len(keys_to_remove)} expired cache items")

def cache_cleanup_task():
    while True:
        try:
            cleanup_expired_cache()
            time.sleep(1800)
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            time.sleep(1800)

def save_plugins_to_file():
    try:
        with open('plugins_data.json', 'w') as f:
            json.dump(plugins_data, f)
    except Exception as e:
        logger.error(f"Error saving plugins: {e}")

def load_plugins_from_file():
    global plugins_data
    try:
        with open('plugins_data.json', 'r') as f:
            plugins_data = json.load(f)
    except FileNotFoundError:
        plugins_data = []
    except Exception as e:
        logger.error(f"Error loading plugins: {e}")
        plugins_data = []

@app.route('/')
def home():
    try:
        with open('templates/home.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = '''
    <meta property="og:title" content="Vadrifts - Roblox Scripts & Tools">
    <meta property="og:description" content="Vadrift's all-in-one website! Check out everything made by Vadrifts such as Discord server, Image converter, Roblox Scripts and More!!">
    <meta property="og:url" content="https://vadrifts.onrender.com">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Vadrifts - Roblox Scripts & Tools">
    <meta name="twitter:description" content="Vadrift's all-in-one website! Check out everything made by Vadrifts such as Discord server, Image converter, Roblox Scripts and More!!">
    <meta name="theme-color" content="#9c88ff">'''
        
        return inject_meta_tags(html_content, meta_tags)
    except FileNotFoundError:
        logger.error("home.html template not found")
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

@app.route('/scripts')
def scripts_page():
    try:
        with open('templates/scripts.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = '''
    <meta property="og:title" content="Vadrifts Scripts - Collection">
    <meta property="og:description" content="Check out our collection of all Vadrifts Scripts we've released! Discover powerful tools and exploits for your favorite games.">
    <meta property="og:url" content="https://vadrifts.onrender.com/scripts">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Vadrifts Scripts - Collection">
    <meta name="twitter:description" content="Check out our collection of all Vadrifts Scripts we've released! Discover powerful tools and exploits for your favorite games.">
    <meta name="theme-color" content="#9c88ff">'''
        
        return inject_meta_tags(html_content, meta_tags)
    except FileNotFoundError:
        logger.error("scripts.html template not found")
        return jsonify({
            "error": "Scripts page not found",
            "message": "Create templates/scripts.html file"
        }), 404

@app.route('/plugins')
def plugins_page():
    try:
        with open('templates/plugins.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = '''
    <meta property="og:title" content="Vadrifts Plugins - Community Bypasses">
    <meta property="og:description" content="Create and share custom bypass plugins for Vadrifts.byp. Browse community-made plugins and contribute your own!">
    <meta property="og:url" content="https://vadrifts.onrender.com/plugins">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Vadrifts Plugins - Community Bypasses">
    <meta name="twitter:description" content="Create and share custom bypass plugins for Vadrifts.byp">
    <meta name="theme-color" content="#9c88ff">'''
        
        return inject_meta_tags(html_content, meta_tags)
    except FileNotFoundError:
        logger.error("plugins.html template not found")
        return jsonify({"error": "Plugins page not found"}), 404

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
    <meta name="theme-color" content="#9c88ff">'''
        
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

@app.route('/api/plugins', methods=['GET'])
def get_plugins():
    sorted_plugins = sorted(plugins_data, key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(sorted_plugins[:50])

@app.route('/api/plugins', methods=['POST'])
def create_plugin():
    try:
        data = request.get_json()
        
        client_ip = request.remote_addr
        now = datetime.now()
        
        if client_ip in rate_limit_data:
            user_data = rate_limit_data[client_ip]
            time_diff = (now - user_data['last_create']).total_seconds()
            
            if time_diff < 300:
                if user_data['count'] >= 2:
                    time_left = int(300 - time_diff)
                    return jsonify({"error": f"You're creating plugins too fast! Wait {time_left} seconds"}), 429
            else:
                rate_limit_data[client_ip] = {'count': 0, 'last_create': now}
        else:
            rate_limit_data[client_ip] = {'count': 0, 'last_create': now}
        
        if not data.get('name') or not data.get('description') or not data.get('sections'):
            return jsonify({"error": "Missing required fields"}), 400
        
        name = data['name'][:25]
        author = data.get('author', 'Anonymous')[:20]
        
        if author != 'Anonymous' and author:
            if not re.match(r'^[a-zA-Z0-9]+$', author):
                return jsonify({"error": "Author name can only contain letters and numbers"}), 400
        
        plugin = {
            'id': str(uuid.uuid4()),
            'name': name,
            'author': author if author else 'Anonymous',
            'description': data['description'][:200],
            'icon': data.get('icon', ''),
            'sections': data['sections'],
            'created_at': datetime.now().isoformat(),
            'uses': 0
        }
        
        plugins_data.append(plugin)
        
        rate_limit_data[client_ip]['count'] += 1
        rate_limit_data[client_ip]['last_create'] = now
        
        save_plugins_to_file()
        
        return jsonify(plugin), 201
        
    except Exception as e:
        logger.error(f"Error creating plugin: {e}")
        return jsonify({"error": "Failed to create plugin"}), 500

@app.route('/api/plugins/<plugin_id>', methods=['GET'])
def get_plugin(plugin_id):
    plugin = next((p for p in plugins_data if p['id'] == plugin_id), None)
    if plugin:
        plugin['uses'] = plugin.get('uses', 0) + 1
        save_plugins_to_file()
        return jsonify(plugin)
    return jsonify({"error": "Plugin not found"}), 404

@app.route('/plugin/<plugin_id>')
def plugin_detail(plugin_id):
    plugin = next((p for p in plugins_data if p['id'] == plugin_id), None)
    if not plugin:
        return jsonify({"error": "Plugin not found"}), 404
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{plugin['name']} - Vadrifts Plugin</title>
        <style>
            body {{
                background: #000;
                color: #fff;
                font-family: 'Inter', sans-serif;
                padding: 40px;
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{ color: #9c88ff; }}
            .section {{ 
                background: rgba(40, 40, 40, 0.8);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
            .bypass {{ 
                background: rgba(114, 9, 183, 0.2);
                padding: 8px 12px;
                border-radius: 6px;
                margin: 5px;
                display: inline-block;
            }}
            .back-btn {{
                background: #9c88ff;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                text-decoration: none;
                display: inline-block;
                margin-bottom: 20px;
            }}
            .export-btn {{
                background: #22c55e;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                cursor: pointer;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <a href="/plugins" class="back-btn">← Back to Plugins</a>
        <h1>{plugin['name']}</h1>
        <p>By {plugin['author']}</p>
        <p>{plugin['description']}</p>
        <p>Used {plugin.get('uses', 0)} times</p>
        
        <div id="sections">
    """
    
    for section_name, bypasses in plugin['sections'].items():
        html += f"""
            <div class="section">
                <h3>{section_name}</h3>
                <div>
        """
        for bypass in bypasses:
            html += f'<span class="bypass">{bypass}</span>'
        html += """
                </div>
            </div>
        """
    
    html += f"""
        <button class="export-btn" onclick="exportPlugin()">Export for Roblox</button>
        
        <script>
            function exportPlugin() {{
                const pluginData = {json.dumps(plugin)};
                const scriptCode = generateRobloxScript(pluginData);
                navigator.clipboard.writeText(scriptCode);
                alert('Plugin code copied to clipboard!');
            }}
            
            function generateRobloxScript(plugin) {{
                let script = '{{\\n';
                script += '  id = "' + plugin.id + '",\\n';
                script += '  name = "' + plugin.name + '",\\n';
                script += '  author = "' + plugin.author + '",\\n';
                
                if (plugin.icon) {{
                    script += '  icon = "' + plugin.icon + '",\\n';
                }}
                
                script += '  sections = {{\\n';
                
                for (const [section, bypasses] of Object.entries(plugin.sections)) {{
                    script += '    ["' + section + '"] = {{\\n';
                    bypasses.forEach(bypass => {{
                        script += '      "' + bypass + '",\\n';
                    }});
                    script += '    }},\\n';
                }}
                
                script += '  }}\\n';
                script += '}}';
                
                return script;
            }}
        </script>
    </body>
    </html>
    """
    
    return html

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

@app.route('/api/find-channels', methods=['POST'])
def find_channels():
    try:
        data = request.get_json()
        usernames = data.get('usernames', [])
        
        if not usernames:
            return jsonify({'error': 'No usernames provided'}), 400
        
        channels = []
        for username in usernames:
            username = username.strip()
            if username:
                channel_data = youtube_finder.find_channel_by_username(username)
                channels.append(channel_data)
        
        return jsonify({'channels': channels})
    
    except Exception as e:
        logger.error(f"Error in find_channels: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/find-channel/<username>')
def find_single_channel(username):
    try:
        channel_data = youtube_finder.find_channel_by_username(username)
        return jsonify(channel_data)
    except Exception as e:
        logger.error(f"Error finding channel {username}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/showcasers')
def get_showcasers():
    try:
        with open('templates/home.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        url_pattern = r'href="(https://youtube\.com/@[^"]+)"'
        urls = re.findall(url_pattern, html_content)
        
        channels = []
        for url in urls:
            username = url.split('@')[-1]
            channel_data = youtube_finder.find_channel_by_username(username)
            channels.append(channel_data)
        
        return jsonify({'channels': channels})
        
    except FileNotFoundError:
        logger.error("home.html not found")
        return jsonify({'channels': []})
    except Exception as e:
        logger.error(f"Error parsing showcasers from HTML: {e}")
        return jsonify({'channels': []})

@app.route('/api/add-showcaser', methods=['POST'])
def add_showcaser():
    return jsonify({'message': 'Add showcasers directly to the HTML file'}), 200

@app.route('/api/remove-showcaser', methods=['DELETE'])
def remove_showcaser():
    return jsonify({'message': 'Remove showcasers directly from the HTML file'}), 200

@app.route('/api/cache/clear')
def clear_channel_cache():
    global channel_cache
    cache_size = len(channel_cache)
    channel_cache.clear()
    return jsonify({
        'message': f'Cache cleared successfully',
        'items_removed': cache_size
    })

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
                color: #9c88ff;
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
                color: #9c88ff;
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
        "nsfw_websites": "NSFW Websites"
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
    load_plugins_from_file()
    
    ping_thread = threading.Thread(target=server_pinger, daemon=True)
    ping_thread.start()
    logger.info("Server pinger started")
    
    reset_thread = threading.Thread(target=daily_reset_task, daemon=True)
    reset_thread.start()
    logger.info("Daily reset task started")
    
    cache_thread = threading.Thread(target=cache_cleanup_task, daemon=True)
    cache_thread.start()
    logger.info("Cache cleanup task started")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot thread started")
    
    run_flask()
