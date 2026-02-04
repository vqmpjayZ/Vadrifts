import os
import logging
import json
import secrets
import time
import requests
from functools import wraps
from flask import Flask, request, jsonify, send_file, redirect, send_from_directory, make_response
from datetime import datetime, timedelta

from config import *
from discord_bot import start_bot
from stickied_message_bot import start_stickied_bot
from youtube_grabber import YouTubeChannelFinder
from image_converter import convert_image_endpoint
from plugins_manager import PluginsManager
from scripts_data import scripts_data, process_script_data
from utils import inject_meta_tags, server_pinger
from collections import defaultdict
from key_system import KeySystemManager
from verification_timer import VerificationTimer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

youtube_finder = YouTubeChannelFinder()
plugins_manager = PluginsManager()
key_system = KeySystemManager()
verification_timer = VerificationTimer(min_verification_time=25)
verification_tokens = {}

API_SECRET = "vadriftsisalwaysinseason"
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY")

JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")

def cleanup_old_logs(logs):
    if not logs:
        return []
    
    cutoff = datetime.now() - timedelta(days=30)
    cleaned = []
    removed = 0
    
    for log in logs:
        try:
            timestamp = datetime.fromisoformat(log['timestamp'])
            if timestamp >= cutoff:
                cleaned.append(log)
            else:
                removed += 1
        except:
            cleaned.append(log)
    
    if removed > 0:
        logger.info(f"Cleaned up {removed} logs older than 30 days")
    
    return cleaned

def load_analytics_from_jsonbin():
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        logger.warning("JSONBin credentials not configured")
        return None
    
    try:
        response = requests.get(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest",
            headers={"X-Master-Key": JSONBIN_API_KEY}
        )
        if response.status_code == 200:
            data = response.json()
            record = data.get('record', {})
            if 'execution_logs' in record:
                record['execution_logs'] = cleanup_old_logs(record['execution_logs'])
            return record
        else:
            logger.error(f"JSONBin load failed: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"JSONBin load error: {str(e)}")
        return None

def save_analytics_to_jsonbin(data):
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        logger.warning("JSONBin credentials not configured")
        return False
    
    if 'execution_logs' in data:
        data['execution_logs'] = cleanup_old_logs(data['execution_logs'])
    
    try:
        response = requests.put(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}",
            headers={
                "Content-Type": "application/json",
                "X-Master-Key": JSONBIN_API_KEY
            },
            json=data
        )
        if response.status_code == 200:
            logger.info("Analytics saved to JSONBin")
            return True
        else:
            logger.error(f"JSONBin save failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"JSONBin save error: {str(e)}")
        return False

def get_client_ip():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    return client_ip

def is_valid_referrer(referer):
    allowed_referrers = ['work.ink', 'www.work.ink', 'lootdest.org', 'lootlabs.gg', 'www.lootlabs.gg']
    return any(domain in referer for domain in allowed_referrers)

def verify_turnstile(token, ip):
    try:
        response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data={
            'secret': TURNSTILE_SECRET_KEY,
            'response': token,
            'remoteip': ip
        })
        result = response.json()
        return result.get('success', False)
    except Exception as e:
        logger.error(f"Turnstile verification error: {str(e)}")
        return False

copy_credits_data = {}

@app.route('/copy-unlock-start')
def copy_unlock_start_page():
    try:
        return send_file('templates/copy-unlock-start.html')
    except FileNotFoundError:
        return jsonify({"error": "Page not found"}), 404

@app.route('/start-copy-unlock')
def start_copy_unlock():
    client_ip = get_client_ip()
    verification_timer.start_timer(client_ip)
    return jsonify({"success": True})

@app.route('/check-copy-credits')
def check_copy_credits_route():
    client_ip = get_client_ip()
    credits_info = copy_credits_data.get(client_ip, {"credits": 0})
    return jsonify({"credits": credits_info.get("credits", 0)})

@app.route('/use-copy-credit')
def use_copy_credit():
    client_ip = get_client_ip()
    
    if client_ip not in copy_credits_data:
        return jsonify({"success": False, "remaining": 0})
    
    current = copy_credits_data[client_ip].get("credits", 0)
    
    if current <= 0:
        return jsonify({"success": False, "remaining": 0})
    
    copy_credits_data[client_ip]["credits"] = current - 1
    
    return jsonify({"success": True, "remaining": current - 1})

@app.route('/copy-unlock')
def copy_unlock():
    client_ip = get_client_ip()
    referer = request.headers.get('Referer', '')
    
    timer_check = verification_timer.check_timer(client_ip)
    
    if not timer_check['valid']:
        return render_copy_error("Access Denied", "Please start the unlock process from the proper page first.")
    
    if not is_valid_referrer(referer):
        return render_copy_error("Invalid Access", "You must complete the verification task to unlock credits.")
    
    verification_timer.mark_verified(client_ip)
    
    if client_ip not in copy_credits_data:
        copy_credits_data[client_ip] = {"credits": 0}
    
    copy_credits_data[client_ip]["credits"] = copy_credits_data[client_ip].get("credits", 0) + 2
    new_total = copy_credits_data[client_ip]["credits"]
    
    return render_copy_success(new_total)

    def render_copy_success(total):
        return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Credits Unlocked! - Vadrifts</title>
        <link rel="icon" href="https://i.imgur.com/ePueN25.png" type="image/png">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                background: #000;
                color: #fff;
                font-family: 'Inter', sans-serif;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }}
            
            .bg-lights {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 1;
                pointer-events: none;
            }}
            
            .light {{
                position: absolute;
                border-radius: 50%;
                filter: blur(150px);
                opacity: 0.4;
                animation: float 15s ease-in-out infinite;
            }}
            
            .light-1 {{
                width: 600px;
                height: 600px;
                background: radial-gradient(circle, #7209b7 0%, transparent 70%);
                top: -150px;
                left: -150px;
            }}
            
            .light-2 {{
                width: 500px;
                height: 500px;
                background: radial-gradient(circle, #9c88ff 0%, transparent 70%);
                bottom: -150px;
                right: -150px;
                animation-delay: -7s;
            }}
            
            @keyframes float {{
                0%, 100% {{ transform: translate(0, 0) scale(1); }}
                50% {{ transform: translate(30px, -30px) scale(1.1); }}
            }}
            
            .container {{
                position: relative;
                z-index: 10;
                animation: fadeIn 0.8s ease;
            }}
            
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(30px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            .box {{
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(30px);
                border: 1px solid rgba(114, 9, 183, 0.3);
                padding: 60px 50px;
                border-radius: 28px;
                box-shadow: 0 30px 60px rgba(0, 0, 0, 0.5), 0 0 100px rgba(114, 9, 183, 0.15);
                text-align: center;
                width: 480px;
                max-width: 90vw;
            }}
            
            .icon {{
                width: 100px;
                height: 100px;
                margin: 0 auto 30px;
                background: linear-gradient(135deg, #7209b7, #9c88ff);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 50px;
                animation: pulse 2s ease-in-out infinite;
                box-shadow: 0 20px 50px rgba(114, 9, 183, 0.4);
            }}
            
            @keyframes pulse {{
                0%, 100% {{ transform: scale(1); }}
                50% {{ transform: scale(1.05); }}
            }}
            
            h1 {{
                font-size: 38px;
                font-weight: 800;
                background: linear-gradient(135deg, #fff 0%, #9c88ff 100%);
                background-clip: text;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 15px;
            }}
            
            .subtitle {{
                color: #888;
                font-size: 16px;
                margin-bottom: 35px;
                line-height: 1.6;
            }}
            
            .subtitle strong {{
                color: #9c88ff;
            }}
            
            .credits-box {{
                background: rgba(114, 9, 183, 0.15);
                border: 1px solid rgba(114, 9, 183, 0.3);
                border-radius: 16px;
                padding: 30px;
                margin-bottom: 30px;
            }}
            
            .credits-number {{
                font-size: 72px;
                font-weight: 900;
                background: linear-gradient(135deg, #a855f7, #9c88ff);
                background-clip: text;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                line-height: 1;
            }}
            
            .credits-label {{
                color: #888;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-top: 10px;
            }}
            
            .info {{
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 12px;
                padding: 18px;
                color: #10b981;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="bg-lights">
            <div class="light light-1"></div>
            <div class="light light-2"></div>
        </div>
        
        <div class="container">
            <div class="box">
                <div class="icon">🎨</div>
                <h1>Credits Unlocked!</h1>
                <p class="subtitle">You've earned <strong>+2 copy credits</strong>!</p>
                
                <div class="credits-box">
                    <div class="credits-number">{total}</div>
                    <div class="credits-label">Total Credits</div>
                </div>
                
                <div class="info">
                    ✓ Close this page and return to Roblox to use your credits!
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    def render_copy_error(title, message):
        return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Vadrifts</title>
        <link rel="icon" href="https://i.imgur.com/ePueN25.png" type="image/png">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            
            body {{
                background: #000;
                color: #fff;
                font-family: 'Inter', sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            
            .box {{
                text-align: center;
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 50px 40px;
                border-radius: 24px;
                max-width: 450px;
            }}
            
            .icon {{
                font-size: 70px;
                margin-bottom: 25px;
            }}
            
            h1 {{
                color: #ef4444;
                font-size: 36px;
                margin-bottom: 15px;
            }}
            
            p {{
                color: #999;
                font-size: 15px;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <div class="icon">🚫</div>
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """, 403
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Feature Unlocked! - Vadrifts</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            body {
                background: #000;
                color: #fff;
                font-family: 'Inter', sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            .success-box {
                text-align: center;
                background: rgba(114, 9, 183, 0.15);
                border: 2px solid #9c88ff;
                padding: 60px 50px;
                border-radius: 24px;
                box-shadow: 0 0 60px rgba(114, 9, 183, 0.4);
                animation: slideIn 0.6s ease;
                max-width: 500px;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(30px) scale(0.95); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            h1 {
                color: #9c88ff;
                font-size: 52px;
                margin-bottom: 20px;
                font-weight: 800;
                letter-spacing: -1px;
            }
            p {
                font-size: 18px;
                color: #aaa;
                margin: 12px 0;
                line-height: 1.6;
            }
            .highlight {
                color: #9c88ff;
                font-weight: 600;
            }
            .icon {
                font-size: 100px;
                margin-bottom: 25px;
                animation: bounce 2s ease infinite;
            }
            @keyframes bounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-12px); }
            }
            .badge {
                display: inline-block;
                background: rgba(156, 136, 255, 0.2);
                border: 1px solid rgba(156, 136, 255, 0.4);
                padding: 10px 20px;
                border-radius: 12px;
                margin-top: 25px;
                font-size: 14px;
                color: #9c88ff;
                font-weight: 600;
            }
        </style>
    </head>
    <body>
        <div class="success-box">
            <div class="icon">🔓</div>
            <h1>Feature Unlocked!</h1>
            <p>You can now <span class="highlight">close this page</span> and return to Roblox.</p>
            <p style="margin-top: 20px;">The premium feature is now available in your script.</p>
            <div class="badge">✓ Active for 24 hours</div>
        </div>
    </body>
    </html>
    """

@app.route('/check-feature-unlock')
def check_feature_unlock():
    feature = request.args.get('feature', 'default')
    client_ip = get_client_ip()
    
    if client_ip in feature_unlocks and feature in feature_unlocks[client_ip]:
        unlock_data = feature_unlocks[client_ip][feature]
        
        if time.time() < unlock_data['expires_at']:
            return jsonify({
                "unlocked": True,
                "unlocked_at": unlock_data['unlocked_at'],
                "expires_at": unlock_data['expires_at']
            })
        else:
            del feature_unlocks[client_ip][feature]
    
    return jsonify({"unlocked": False})
    
@app.route('/')
def home():
    try:
        with open('templates/home.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        meta_tags = HOME_META_TAGS
        return inject_meta_tags(html_content, meta_tags)
    except FileNotFoundError:
        logger.error("home.html template not found")
        return jsonify({"error": "Home page not found"}), 404

@app.route('/scripts')
def scripts_page():
    try:
        with open('templates/scripts.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return inject_meta_tags(html_content, SCRIPTS_META_TAGS)
    except FileNotFoundError:
        logger.error("scripts.html template not found")
        return jsonify({"error": "Scripts page not found"}), 404

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header != API_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/start-verification')
def start_verification():
    client_ip = get_client_ip()
    verification_timer.start_timer(client_ip)
    logger.info(f"Verification timer started for IP: {client_ip}")
    
    return jsonify({
        "success": True,
        "message": "Timer started"
    })
        
@app.route('/plugins')
def plugins_page():
    try:
        with open('templates/plugins.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return inject_meta_tags(html_content, PLUGINS_META_TAGS)
    except FileNotFoundError:
        logger.error("plugins.html template not found")
        return jsonify({"error": "Plugins page not found"}), 404

@app.route('/plugin-details')
def plugin_details():
    try:
        return send_file('templates/plugin-details.html')
    except FileNotFoundError:
        logger.error("plugin-details.html template not found")
        return jsonify({"error": "Plugin details page not found"}), 404

@app.route('/api/plugins/<plugin_id>/raw')
def get_plugin_raw(plugin_id):
    try:
        plugin = plugins_manager.get_plugin_data(plugin_id)
        
        if not plugin:
            response = make_response("-- Plugin not found")
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            return response, 404
        
        def escape_lua_string(s):
            if s is None:
                return ""
            return str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        
        sections = []
        for section_name, bypasses in plugin.get('sections', {}).items():
            escaped_bypasses = [f'                "{escape_lua_string(bypass)}"' for bypass in bypasses]
            bypasses_str = ',\n'.join(escaped_bypasses)
            
            sections.append(f'''        {{
            Name = "{escape_lua_string(section_name)}",
            Bypasses = {{
{bypasses_str}
            }}
        }}''')
        
        sections_code = ',\n'.join(sections)
        
        lua_code = f'''-- {escape_lua_string(plugin['name'])} by {escape_lua_string(plugin.get('author', 'Anonymous'))}
-- {escape_lua_string(plugin.get('description', 'No description'))}

local Plugin = {{
    Name = "{escape_lua_string(plugin['name'])}",
    Author = "{escape_lua_string(plugin.get('author', 'Anonymous'))}",
    Description = "{escape_lua_string(plugin.get('description', 'No description'))}",
    Icon = "{escape_lua_string(plugin.get('icon', 'package'))}",
    Sections = {{
{sections_code}
    }}
}}

return Plugin'''

        response = make_response(lua_code)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Access-Control-Allow-Origin'] = '*'
        
        logger.info(f"Served raw plugin: {plugin_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error serving raw plugin {plugin_id}: {str(e)}", exc_info=True)
        response = make_response(f"-- Error generating plugin: {str(e)}")
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        return response, 500
        
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
        return jsonify({"error": "Converter page not found"}), 404

usage_data = {}
copy_usage_data = {}
execution_logs = []
cloud_data_loaded = False

def ensure_cloud_data_loaded():
    global execution_logs, cloud_data_loaded
    
    if cloud_data_loaded:
        return
    
    cloud_data = load_analytics_from_jsonbin()
    if cloud_data and 'execution_logs' in cloud_data:
        execution_logs = cloud_data['execution_logs']
        logger.info(f"Loaded {len(execution_logs)} logs from JSONBin")
    
    cloud_data_loaded = True

@app.route('/check-usage', methods=['GET'])
def check_usage():
    hwid = request.args.get('hwid')
    if not hwid:
        return jsonify({"error": "No HWID provided"}), 400
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if hwid in usage_data:
        if usage_data[hwid]['date'] != today:
            usage_data[hwid] = {'used': 0, 'date': today}
    else:
        usage_data[hwid] = {'used': 0, 'date': today}
    
    return jsonify(usage_data[hwid])

@app.route('/update-usage', methods=['GET'])
def update_usage():
    hwid = request.args.get('hwid')
    used = request.args.get('used', 0)
    
    if not hwid:
        return jsonify({"error": "No HWID provided"}), 400
    
    today = datetime.now().strftime("%Y-%m-%d")
    usage_data[hwid] = {'used': int(used), 'date': today}
    
    return jsonify({"success": True})

@app.route('/check-copy-usage', methods=['GET'])
def check_copy_usage():
    hwid = request.args.get('hwid')
    if not hwid:
        return jsonify({"error": "No HWID provided"}), 400
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if hwid in copy_usage_data:
        if copy_usage_data[hwid]['date'] != today:
            copy_usage_data[hwid] = {'texture': 0, 'normal': 0, 'date': today}
    else:
        copy_usage_data[hwid] = {'texture': 0, 'normal': 0, 'date': today}
    
    return jsonify(copy_usage_data[hwid])

@app.route('/update-copy-usage', methods=['GET'])
def update_copy_usage():
    hwid = request.args.get('hwid')
    texture = request.args.get('texture', 0)
    normal = request.args.get('normal', 0)
    
    if not hwid:
        return jsonify({"error": "No HWID provided"}), 400
    
    today = datetime.now().strftime("%Y-%m-%d")
    copy_usage_data[hwid] = {'texture': int(texture), 'normal': int(normal), 'date': today}
    
    return jsonify({"success": True})

@app.route('/log-execution', methods=['GET'])
def log_execution():
    global execution_logs
    ensure_cloud_data_loaded()
    
    hwid = request.args.get('hwid')
    script = request.args.get('script', 'Unknown')
    
    if hwid:
        execution_logs.append({
            'hwid': hwid,
            'script': script,
            'timestamp': datetime.now().isoformat()
        })
        
        if len(execution_logs) > 10000:
            execution_logs.pop(0)
        
        if len(execution_logs) % 10 == 0:
            save_analytics_to_jsonbin({
                'execution_logs': execution_logs,
                'last_updated': datetime.now().isoformat()
            })
    
    return jsonify({"success": True})

@app.route('/analytics-data', methods=['GET'])
def analytics_data():
    ensure_cloud_data_loaded()
    
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    week_execs = []
    month_execs = []
    script_counts = defaultdict(int)
    unique_users_week = set()
    unique_users_month = set()
    
    daily_data = defaultdict(int)
    script_daily_data = defaultdict(lambda: defaultdict(int))
    
    for log in execution_logs:
        timestamp = datetime.fromisoformat(log['timestamp'])
        script_counts[log['script']] += 1
        
        day_key = timestamp.strftime('%Y-%m-%d')
        daily_data[day_key] += 1
        script_daily_data[log['script']][day_key] += 1
        
        if timestamp >= week_ago:
            week_execs.append(log)
            unique_users_week.add(log['hwid'])
        
        if timestamp >= month_ago:
            month_execs.append(log)
            unique_users_month.add(log['hwid'])
    
    last_30_days = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(29, -1, -1)]
    chart_data = [daily_data.get(day, 0) for day in last_30_days]
    
    script_chart_data = {}
    for script in script_counts.keys():
        script_chart_data[script] = [script_daily_data[script].get(day, 0) for day in last_30_days]
    
    return jsonify({
        'total_executions': len(execution_logs),
        'week_executions': len(week_execs),
        'month_executions': len(month_execs),
        'unique_users_week': len(unique_users_week),
        'unique_users_month': len(unique_users_month),
        'script_breakdown': dict(script_counts),
        'chart_labels': last_30_days,
        'chart_data': chart_data,
        'script_daily_data': script_chart_data
    })

@app.route('/analytics-sync', methods=['POST'])
def analytics_sync():
    ensure_cloud_data_loaded()
    
    success = save_analytics_to_jsonbin({
        'execution_logs': execution_logs,
        'last_updated': datetime.now().isoformat()
    })
    
    if success:
        return jsonify({'success': True, 'message': 'Synced to cloud'})
    else:
        return jsonify({'success': False, 'error': 'Failed to sync'}), 500

@app.route('/analytics')
def analytics_page():
    try:
        return send_file('templates/analytics.html')
    except FileNotFoundError:
        logger.error("analytics.html template not found")
        return jsonify({"error": "Analytics page not found"}), 404
        
@app.route('/key-system')
def key_system_page():
    try:
        return send_file('templates/key-system.html')
    except FileNotFoundError:
        logger.error("key-system.html template not found")
        return jsonify({"error": "Key system page not found"}), 404

@app.route('/verify')
def verify_page():
    client_ip = get_client_ip()
    referer = request.headers.get('Referer', '')
    
    try:
        with open('templates/verify.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        logger.error("verify.html template not found")
        return jsonify({"error": "Verify page not found"}), 404
    
    html_content = html_content.replace('YOUR_SITE_KEY_HERE', TURNSTILE_SITE_KEY or '')
    
    html_content = html_content.replace(
        'let verificationToken = null;',
        'let verificationToken = null;'
    )
    
    timer_check = verification_timer.check_timer(client_ip)
    
    if not timer_check['valid']:
        reason = timer_check.get('reason')
        if reason == 'time_not_elapsed':
            elapsed = timer_check.get('elapsed', 0)
            required = timer_check.get('required', 25)
            logger.warning(f"Timer bypass attempt from IP: {client_ip}. Only {elapsed:.1f}s elapsed (need {required}s)")
        elif reason == 'already_verified':
            logger.warning(f"Already verified IP trying again: {client_ip}")
        else:
            logger.warning(f"No timer found for IP: {client_ip}")
        return html_content
    
    if not is_valid_referrer(referer):
        logger.warning(f"Invalid referer from IP: {client_ip}. Referer: {referer}")
        return html_content
    
    verification_timer.mark_verified(client_ip)
    
    token = secrets.token_urlsafe(32)
    
    verification_tokens[token] = {
        'ip': client_ip,
        'expires': time.time() + 300,
        'used': False
    }
    
    html_content = html_content.replace(
        'let verificationToken = null;',
        f'let verificationToken = "{token}";'
    )
    
    logger.info(f"Verification token created for IP: {client_ip} after {timer_check['elapsed']:.1f}s")
    return html_content

@app.route('/create')
def create_key():
    token = request.args.get('token')
    captcha = request.args.get('captcha')
    
    if not token:
        logger.warning(f"Create attempt without token")
        return "Missing verification token", 403
    
    if not captcha:
        logger.warning(f"Create attempt without captcha")
        return "Missing captcha token", 403
    
    client_ip = get_client_ip()
    
    if not verify_turnstile(captcha, client_ip):
        logger.warning(f"Invalid captcha from IP: {client_ip}")
        return "Captcha verification failed", 403
    
    token_data = verification_tokens.get(token)
    if not token_data:
        logger.warning(f"Invalid token attempt from IP: {client_ip}")
        return "Invalid or expired token", 403
    
    if token_data['used']:
        logger.warning(f"Reused token attempt from IP: {client_ip}")
        return "Token already used", 403
    
    if time.time() > token_data['expires']:
        del verification_tokens[token]
        return "Token expired", 403
    
    if token_data['ip'] != client_ip:
        logger.warning(f"Token IP mismatch. Expected {token_data['ip']}, got {client_ip}")
        return "Session mismatch", 403
    
    verification_tokens[token]['used'] = True
    
    slug = key_system.create_slug(client_ip)
    host = request.headers.get('host', 'vadrifts.onrender.com')
    
    logger.info(f"Created key slug for IP: {client_ip}")
    return f"https://{host}/getkey/{slug}"

@app.route('/getkey/<slug>')
def get_key(slug):
    ip = key_system.get_ip_from_slug(slug)
    
    if not ip:
        logger.warning(f"Invalid or expired slug attempted: {slug}")
        return "Invalid or expired key link", 404
    
    key_system.consume_slug(slug)
    key = key_system.generate_key(ip)
    
    logger.info(f"Key generated for IP: {ip} - Key: {key}")
    return key

@app.route('/validate')
def validate_key_route():
    key = request.args.get('key')
    
    if not key:
        return "false"
    
    client_ip = get_client_ip()
    is_valid = key_system.validate_key(client_ip, key)
    return "true" if is_valid else "false"

@app.route('/plugin/<plugin_id>')
def plugin_detail(plugin_id):
    plugin = plugins_manager.get_plugin_data(plugin_id)
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
        <p>By {plugin.get('author', 'Anonymous')}</p>
        <p>{plugin.get('description', 'No description')}</p>
        <p>Used {plugin.get('uses', 0)} times</p>
        
        <div id="sections">
    """
    
    for section_name, bypasses in plugin.get('sections', {}).items():
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
                script += '  author = "' + (plugin.author || 'Anonymous') + '",\\n';
                
                if (plugin.icon) {{
                    script += '  icon = "' + plugin.icon + '",\\n';
                }}
                
                script += '  sections = {{\\n';
                
                for (const [section, bypasses] of Object.entries(plugin.sections || {{}})) {{
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

@app.route('/templates/<path:filename>')
def serve_templates(filename):
    return send_from_directory('templates', filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/discord')
def discord_invite():
    return redirect("https://discord.com/invite/WDbJ5wE2cR")

@app.route('/.well-known/discord')
def discord_verification():
    response = make_response('dh=6a7d0bee33f82bdb67f20d7ac5d8254e1a36cb64')
    response.headers['Content-Type'] = 'text/plain'
    return response

@app.route('/status-check')
def status_check():
    response = jsonify({
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "code": "VADRIFTS_ONLINE_2025"
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response, 200
    
@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

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

@app.route('/api/plugins', methods=['GET'])
def get_plugins():
    return plugins_manager.get_all_plugins()

@app.route('/api/plugins', methods=['POST'])
def create_plugin():
    return plugins_manager.create_plugin(request)

@app.route('/api/plugins/<plugin_id>', methods=['GET'])
def get_plugin(plugin_id):
    return plugins_manager.get_plugin(plugin_id)

@app.route('/api/plugins/<plugin_id>', methods=['PUT'])
def update_plugin(plugin_id):
    return plugins_manager.update_plugin(plugin_id, request)

@app.route('/api/plugins/<plugin_id>', methods=['DELETE'])
def delete_plugin(plugin_id):
    return plugins_manager.delete_plugin(plugin_id)

@app.route('/convert-image')
def convert_image():
    return convert_image_endpoint(request)

@app.route('/api/find-channels', methods=['POST'])
def find_channels():
    data = request.get_json()
    usernames = data.get('usernames', [])
    return youtube_finder.find_multiple_channels(usernames)

if __name__ == '__main__':
    import threading

    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    stickied_bot_thread = threading.Thread(target=start_stickied_bot, daemon=True)
    stickied_bot_thread.start()

    ping_thread = threading.Thread(target=server_pinger, daemon=True)
    ping_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
