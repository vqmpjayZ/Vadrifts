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

bypass_data = {
    "words": {"asshole", "ass", "anal", "breasts", "blowjob", "boobs", "beaner", "bitches", "bitch", "bullshit", "butthole", "bootyhole", "booty", "bbc", "cocaine", "creampie", "cumming", "cum", "clit", "coochies", "cuckold", "cuck", "cunny", "cock", "cunt", "dickhead", "dick", "discord", "doggystyle", "dumbass", "dildo", "damn", "E-Rape", "E-Sex", "fatass", "fucked", "fucker", "fuck", "faggot", "fag", "fap", "femboy", "fanny", "hitler", "hentai", "horny", "hoes", "hoe", "kys", "kkk", "lmfao", "lmao", "motherfucker", "masturbate", "molest", "milf", "meth", "nigger", "nigga", "negro", "nipples", "nazi", "nudes", "onlyfans", "orgasm", "pedophile", "penis", "pussies", "pussy", "pornhub", "porn", "piss", "queer", "retarded", "retard", "rapist", "rape", "schlong", "stripper", "slave", "slut", "shit","stfu", "sexy", "sex", "titties", "tits", "tranny", "thot", "virgin", "vagina", "whore", "weed", "ASSHOLE", "ASS", "ANAL", "BULLSHIT", "BASTARD", "BONER", "BITCHES", "BITCH", "BOOBS", "BOOTY", "CUNT", "COCK", "CUCKOLD", "CUCK", "CUM", "DUMBAS", "DICKHEAD", "DAMN", "FAGGOT", "FAG", "FATASS", "FEMBOY", "FUCKER", "FUCKED", "FUCK", "HENTAI", "HOE", "KYS", "KKK", "LMFAO", "LMAO", "MOTHERFUCKER", "METH", "PORNHUB", "PISS", "STFU", "SLIT", "SHIT", "VIRGIN", "VAGINA", "WHORE", "WEED"},
    
    "sentences": {"anal sex pls", "anal sex", "ass sex pls", "ass sex", "Boom cockshot!", "boner alert!", "butt sex", "big cock", "boobs or ass?", "big ass thighs", "big black cock", "big ass", "Be my wife!", "Can I see those cute boobs of yours?", "cock sucker", "Cum on me please!", "cum please", "cut yourself", "child porn",  "Cock incoming!", "Cock in bedroom", "cock or boobs?", "damn you got a long schlong daddy", "dirty hoe","fuck yourself", "fuck you", "fuck off", "free porn", "fatass hoe", "fat ass", "go end your life", "hail hitler", "hardcore sex", "holy fuck", "i eat pussy", "i love minors", "i love you", "i love cocks", "i love boobs", "i love titties", "i'm gonna make you pregnant mommy", "i'm sexy, and you know it", "i'm horny so moan", "i'm mad horny", "i'm gonna bang you hard", "i'm so hard rn", "i'm so wet daddy", "i'm so wet", "i'm craving titties", "i would like to see some titties", "i wanna kms", "i wanna smash you", "i want to drink your breasts", "I banged your girl so hard", "i dont give a shit", "i love sex", "I'll make you pregnant", "Imagine getting no bitches", "kill yourself", "keep moaning", "lets do doggystyle", "lets have sex", "let me squish those titties", "lgbtq+ is related to autistm", "lil nigga", "Mind if you let me squish those titties", "my condom fell off!", "Mr breast is so cool", "my cock is dirty", "make me pregnant", "Naked Boys", "Naked Girls", "nice tits", "oral sex", "pussy licker", "rape me", "spank me daddy", "sex slave", "Sweet cock dude", "suck my cock", "Sweet cock you got up there", "shit on", "shut the fuck up", "shut yo goofy ass up", "shut yo broke ass up", "suck my cock retard", "son of a bitch", "small penis", "Theres cum everywhere!", "that bbc dont play", "ur gf was craving my raging schlong", "ur moms booty is delicous", "why is this nigger not getting whipped?", "wanna have sex?", "wsg bbg you lookin sexy", "what the fuck", "you like to rape and suck black oiled up men", "you fucking retard", "yo my shaft is hard, mind jerking it?", "you're such a whore", "you're a pedophile", "you pathetic slut", "you're a pussy", "you're so sexy", "BE MY WIFE!", "BIG BOOTY LATINAS", "BIG BOOTY ASIANS", "BIG BOOTY FEMBOYS", "BIG BOOTY", "BIG BOOBS", "CAN I PISS INSIDE YOUR BUTTHOLE?", "CAN I PISS ON YOUR?", "COCK IN BEDROOM", "CUM ON ME", "CUM ON MY FACE", "DO YOU HAVE TITS?", "EAT PUSSY BITCH", "FATASS HOE", "FAT ASS", "FREE HENTAI", "FUCK YOU", "HELP! THERES A COCK IN MY ASS!", "HELP! THERES A HOE CHASING ME!", "I AM ABOUT TO CUM", "I EAT PUSSY", "I PREFER PUSSY", "I HAVE A MASSIVE COCK", "I HAD AWESOME SEX WITH UR MOM!!!!", "ILL MAKE YOU PREGNANT", "LET ME SQUISH THOSE TITTIES", "LETS HAVE SEX", "LETS FUCK", "MY CONDOM FELL OFF!", "NAKED GIRLS", "NAKED BOYS", "oh my god, not this DUMBASS", "STRAIGHT POWER MOTHERFUCKERS", "SUCK MY COCK", "SHUT THE FUCK UP", "SHUT UP FAGGOT", "SHUT UP CUNT", "SHUT UP HOE", "SHAKE THAT ASS", "SON OF A BITCH", "YOU ARE SO ASS AT THIS GAME"},
    
    "roleplay": {"*moans*", "*screams*", "*cries*", "*dies*", "*kisses you*", "*hugs you*", "*slaps you*", "*punches you*", "*shoots you*", "*stabs you*", "*murders you*", "*rapes you*", "*fucks you*", "*makes love to you*", "*gets naked*", "*takes off clothes*", "*shows boobs*", "*shows ass*", "*shows penis*", "*shows vagina*", "*masturbates*", "*has sex*", "*gives blowjob*", "*gets pregnant*", "*gives birth*", "*commits suicide*", "*hangs self*", "*cuts wrists*", "*overdoses*", "*drinks bleach*", "*jumps off building*", "*gets run over*"},
    
    "nsfw_websites": {"pornhub.com", "xvideos.com", "xhamster.com", "redtube.com", "youporn.com", "tube8.com", "spankbang.com", "xnxx.com", "sex.com", "porn.com", "brazzers.com", "bangbros.com", "realitykings.com", "mofos.com", "teamskeet.com", "naughtyamerica.com", "digitalplayground.com", "evilangel.com", "kink.com", "chaturbate.com", "cam4.com", "myfreecams.com", "livejasmin.com", "onlyfans.com", "manyvids.com", "clips4sale.com", "iwantclips.com", "adultfriendfinder.com", "ashley madison", "seeking.com"},
    
    "not_legit": {"i have robux generator", "free robux here", "get free robux", "robux hack", "unlimited robux", "robux generator 2024", "robux giveaway", "free limiteds", "account seller", "selling accounts", "buying accounts", "scam link", "fake link", "virus link", "ip grabber", "cookie logger", "account stealer", "roblox hack", "exploit download", "free executor", "synapse crack", "krnl free", "jjsploit", "oxygen u", "scriptware crack", "free scripts", "op scripts", "admin scripts", "fe scripts", "trolling scripts"}
}

bypass_results = {
    "words": {"last_updated": None, "success_rate": None, "status": "unknown", "is_testing": False},
    "sentences": {"last_updated": None, "success_rate": None, "status": "unknown", "is_testing": False},
    "roleplay": {"last_updated": None, "success_rate": None, "status": "unknown", "is_testing": False},
    "nsfw_websites": {"last_updated": None, "success_rate": None, "status": "unknown", "is_testing": False},
    "not_legit": {"last_updated": None, "success_rate": None, "status": "unknown", "is_testing": False}
}

testing_queue = []
testing_lock = threading.Lock()

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

def is_data_expired(last_updated):
    if not last_updated:
        return True
    return datetime.now() - last_updated > timedelta(hours=24)

def reset_daily_data():
    current_time = datetime.now()
    for category in bypass_results:
        if is_data_expired(bypass_results[category]["last_updated"]):
            bypass_results[category] = {
                "last_updated": None,
                "success_rate": None,
                "status": "unknown",
                "is_testing": False
            }

def add_to_testing_queue(category, user_id):
    with testing_lock:
        if category not in [item[0] for item in testing_queue] and not bypass_results[category]["is_testing"]:
            testing_queue.append((category, user_id))
            return True
    return False

async def process_testing_queue():
    while True:
        with testing_lock:
            if testing_queue and not any(bypass_results[cat]["is_testing"] for cat in bypass_results):
                category, user_id = testing_queue.pop(0)
                bypass_results[category]["is_testing"] = True
                bypass_results[category]["status"] = f"testing_by_{user_id}"
        await asyncio.sleep(1)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(process_testing_queue())

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

@app.route('/api/bypass-status')
def get_bypass_status():
    reset_daily_data()
    
    response_data = {}
    for category, data in bypass_results.items():
        response_data[category] = {
            "success_rate": data["success_rate"],
            "status": data["status"],
            "last_updated": data["last_updated"].isoformat() if data["last_updated"] else None,
            "is_testing": data["is_testing"]
        }
    
    return jsonify(response_data)

@app.route('/api/bypass-data/<category>')
def get_bypass_data(category):
    if category not in bypass_data:
        return jsonify({"error": "Invalid category"}), 400
    
    return jsonify({
        "category": category,
        "data": list(bypass_data[category]),
        "total_count": len(bypass_data[category])
    })

@app.route('/api/request-testing', methods=['POST'])
def request_testing():
    data = request.get_json()
    if not data or 'category' not in data or 'user_id' not in data:
        return jsonify({"error": "Missing category or user_id"}), 400
    
    category = data['category']
    user_id = data['user_id']
    
    if category not in bypass_data:
        return jsonify({"error": "Invalid category"}), 400
    
    reset_daily_data()
    
    if is_data_expired(bypass_results[category]["last_updated"]):
        if add_to_testing_queue(category, user_id):
            return jsonify({
                "status": "queued",
                "message": "You're the first today! Testing will begin shortly.",
                "position": len(testing_queue)
            })
        else:
            return jsonify({
                "status": "already_queued",
                "message": "Testing for this category is already in progress or queued."
            })
    else:
        return jsonify({
            "status": "recent_data",
            "message": "Recent data available",
            "success_rate": bypass_results[category]["success_rate"]
        })

@app.route('/api/submit-results', methods=['POST'])
def submit_results():
    data = request.get_json()
    if not data or 'category' not in data or 'success_rate' not in data or 'user_id' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    category = data['category']
    success_rate = data['success_rate']
    user_id = data['user_id']
    
    if category not in bypass_results:
        return jsonify({"error": "Invalid category"}), 400
    
    if not bypass_results[category]["is_testing"]:
        return jsonify({"error": "No active testing session for this category"}), 400
    
    bypass_results[category] = {
        "last_updated": datetime.now(),
        "success_rate": success_rate,
        "status": "completed",
        "is_testing": False
    }
    
    logger.info(f"Results submitted for {category}: {success_rate}% success rate by user {user_id}")
    
    return jsonify({
        "status": "success",
        "message": "Results submitted successfully"
    })

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
