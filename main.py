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

feature_credits = {}

FEATURE_CONFIG = {
    "copy-art": {
        "name": "Copy Art Credits",
        "credits_per_unlock": 2,
        "icon": "🎨",
        "description": "Copy art with special brushes from other players",
        "workink_url": "https://work.ink/YOUR_COPY_ART_LINK"
    },
    "auto-farm": {
        "name": "Auto Farm Credits",
        "credits_per_unlock": 5,
        "icon": "🌾",
        "description": "Automatically farm resources",
        "workink_url": "https://work.ink/YOUR_AUTO_FARM_LINK"
    }
}

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

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header != API_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/unlock/<feature_id>')
def feature_unlock_page(feature_id):
    if feature_id not in FEATURE_CONFIG:
        return render_feature_error("Feature Not Found", "This feature doesn't exist.")
    
    config = FEATURE_CONFIG[feature_id]
    return render_feature_unlock_page(feature_id, config)

@app.route('/start-unlock/<feature_id>')
def start_feature_unlock(feature_id):
    if feature_id not in FEATURE_CONFIG:
        return jsonify({"success": False, "error": "Feature not found"})
    
    client_ip = get_client_ip()
    verification_timer.start_timer(client_ip)
    logger.info(f"Feature unlock timer started for IP: {client_ip}, feature: {feature_id}")
    
    return jsonify({"success": True})

@app.route('/complete-unlock/<feature_id>')
def complete_feature_unlock(feature_id):
    if feature_id not in FEATURE_CONFIG:
        return render_feature_error("Feature Not Found", "This feature doesn't exist.")
    
    client_ip = get_client_ip()
    referer = request.headers.get('Referer', '')
    config = FEATURE_CONFIG[feature_id]
    
    timer_check = verification_timer.check_timer(client_ip)
    
    if not timer_check['valid']:
        return render_feature_error("Access Denied", "Please start the unlock process from the proper page first.")
    
    if not is_valid_referrer(referer):
        return render_feature_error("Invalid Access", "You must complete the verification task to unlock this feature.")
    
    verification_timer.mark_verified(client_ip)
    
    if client_ip not in feature_credits:
        feature_credits[client_ip] = {}
    
    if feature_id not in feature_credits[client_ip]:
        feature_credits[client_ip][feature_id] = 0
    
    credits_to_add = config.get("credits_per_unlock", 2)
    feature_credits[client_ip][feature_id] += credits_to_add
    new_total = feature_credits[client_ip][feature_id]
    
    logger.info(f"Feature '{feature_id}' credits granted to IP: {client_ip}, total: {new_total}")
    
    return render_feature_success(config, credits_to_add, new_total)

@app.route('/check-credits/<feature_id>')
def check_feature_credits(feature_id):
    client_ip = get_client_ip()
    
    if client_ip not in feature_credits:
        return jsonify({"credits": 0})
    
    credits = feature_credits[client_ip].get(feature_id, 0)
    return jsonify({"credits": credits})

@app.route('/use-credit/<feature_id>')
def use_feature_credit(feature_id):
    client_ip = get_client_ip()
    
    if client_ip not in feature_credits:
        return jsonify({"success": False, "remaining": 0})
    
    current = feature_credits[client_ip].get(feature_id, 0)
    
    if current <= 0:
        return jsonify({"success": False, "remaining": 0})
    
    feature_credits[client_ip][feature_id] = current - 1
    
    logger.info(f"Credit used for '{feature_id}' by IP: {client_ip}, remaining: {current - 1}")
    
    return jsonify({"success": True, "remaining": current - 1})

def render_feature_unlock_page(feature_id, config):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unlock {config['name']} - Vadrifts</title>
    <link rel="icon" href="https://i.imgur.com/ePueN25.png" type="image/png">
    <script defer src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --gradient-primary: linear-gradient(90deg, #ffffff 0%, #7209b7 100%);
            --gradient-button: linear-gradient(135deg, #7209b7 0%, #9c88ff 100%);
            --accent-color: #7209b7;
            --accent-glow: rgba(114, 9, 183, 0.5);
        }}

        body {{
            background: #000;
            color: #fff;
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
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
            opacity: 0.35;
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

        .particles {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 2;
            pointer-events: none;
        }}

        .particle {{
            position: absolute;
            width: 3px;
            height: 3px;
            background: #a855f7;
            border-radius: 50%;
            opacity: 0.6;
            animation: floatUp 20s linear infinite;
        }}

        @keyframes floatUp {{
            0% {{ transform: translateY(100vh) translateX(0); opacity: 0; }}
            10% {{ opacity: 0.6; }}
            90% {{ opacity: 0.4; }}
            100% {{ transform: translateY(-50px) translateX(50px); opacity: 0; }}
        }}

        .navbar {{
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 100;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 20px;
            padding: 24px 32px;
            max-width: 1000px;
            width: 90%;
        }}

        .nav-content {{
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .nav-logo {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 24px;
            font-weight: 700;
            background: var(--gradient-primary);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
        }}

        .nav-logo-img {{
            width: 28px;
            height: 28px;
        }}

        .nav-links {{
            display: flex;
            gap: 30px;
        }}

        .nav-link {{
            color: #ccc;
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.3s ease;
            padding: 8px 12px;
        }}

        .nav-link:hover {{
            color: #fff;
        }}

        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 140px 20px 40px;
            position: relative;
            z-index: 10;
        }}

        .main-box {{
            background: rgba(0,0,0,0.5);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 50px 40px;
            animation: fadeIn 0.8s ease;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .header {{
            text-align: center;
            margin-bottom: 35px;
        }}

        .icon-wrapper {{
            width: 80px;
            height: 80px;
            margin: 0 auto 25px;
            background: linear-gradient(135deg, #7209b7, #9c88ff);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            box-shadow: 0 15px 40px rgba(114, 9, 183, 0.4);
        }}

        h1 {{
            font-size: 32px;
            font-weight: 800;
            background: var(--gradient-primary);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }}

        .subtitle {{
            color: #888;
            font-size: 15px;
            line-height: 1.6;
        }}

        .vpn-warning {{
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(251, 191, 36, 0.06) 100%);
            border: 1px solid rgba(251, 191, 36, 0.25);
            border-radius: 14px;
            padding: 18px 22px;
            margin-bottom: 25px;
            display: flex;
            align-items: flex-start;
            gap: 14px;
        }}

        .vpn-warning-icon {{
            font-size: 22px;
            flex-shrink: 0;
        }}

        .vpn-warning-content {{
            flex: 1;
        }}

        .vpn-warning-title {{
            color: #fbbf24;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}

        .vpn-warning-text {{
            color: #d4a574;
            font-size: 13px;
            line-height: 1.6;
        }}

        .vpn-warning-text strong {{
            color: #fbbf24;
        }}

        .instruction-box {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.03) 100%);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 14px;
            padding: 22px;
            margin-bottom: 30px;
        }}

        .instruction-title {{
            color: #10b981;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .instruction-title i {{
            width: 18px;
            height: 18px;
        }}

        .instruction-steps {{
            color: #bbb;
            font-size: 14px;
            line-height: 1.9;
            list-style: none;
            counter-reset: step;
        }}

        .instruction-steps li {{
            counter-increment: step;
            position: relative;
            padding-left: 36px;
            margin-bottom: 8px;
        }}

        .instruction-steps li:last-child {{
            margin-bottom: 0;
        }}

        .instruction-steps li::before {{
            content: counter(step);
            position: absolute;
            left: 0;
            top: 1px;
            width: 22px;
            height: 22px;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 700;
            color: #10b981;
        }}

        .unlock-btn {{
            width: 100%;
            padding: 18px 24px;
            background: linear-gradient(135deg, #7209b7 0%, #9c88ff 100%);
            border: none;
            border-radius: 14px;
            color: #fff;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-family: 'Inter', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            box-shadow: 0 10px 30px rgba(114, 9, 183, 0.35);
            position: relative;
            overflow: hidden;
            margin-bottom: 25px;
        }}

        .unlock-btn::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s ease;
        }}

        .unlock-btn:hover {{
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(114, 9, 183, 0.5);
        }}

        .unlock-btn:hover::before {{
            left: 100%;
        }}

        .unlock-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}

        .unlock-btn i {{
            width: 20px;
            height: 20px;
        }}

        .info-badges {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            justify-content: center;
        }}

        .info-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            padding: 10px 16px;
            border-radius: 10px;
            font-size: 13px;
            color: #888;
            font-weight: 500;
        }}

        .info-badge i {{
            width: 16px;
            height: 16px;
        }}

        .status-msg {{
            padding: 14px 18px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 20px;
            display: none;
            align-items: center;
            gap: 10px;
        }}

        .status-msg.show {{
            display: flex;
        }}

        .status-msg.loading {{
            background: rgba(251, 191, 36, 0.12);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.25);
        }}

        .status-msg.error {{
            background: rgba(239, 68, 68, 0.12);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.25);
        }}

        .loading-spinner {{
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 50%;
            border-top-color: currentColor;
            animation: spin 0.8s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        @media (max-width: 768px) {{
            .navbar {{
                left: 10px;
                right: 10px;
                width: auto;
                transform: none;
                padding: 16px 18px;
            }}

            .nav-links {{
                gap: 15px;
            }}

            .nav-link {{
                font-size: 12px;
            }}

            .container {{
                padding: 120px 15px 30px;
            }}

            .main-box {{
                padding: 35px 25px;
            }}

            h1 {{
                font-size: 26px;
            }}

            .info-badges {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="bg-lights">
        <div class="light light-1"></div>
        <div class="light light-2"></div>
    </div>

    <div class="particles" id="particles"></div>

    <nav class="navbar">
        <div class="nav-content">
            <a href="/" class="nav-logo">
                <img src="https://i.imgur.com/ePueN25.png" alt="Vadrifts" class="nav-logo-img">
                Vadrifts
            </a>
            <div class="nav-links">
                <a href="/scripts" class="nav-link">Scripts</a>
                <a href="/plugins" class="nav-link">Plugins</a>
            </div>
        </div>
    </nav>

    <div class="container">
        <div class="main-box">
            <div class="header">
                <div class="icon-wrapper">{config['icon']}</div>
                <h1>Unlock {config['name']}</h1>
                <p class="subtitle">{config['description']}</p>
            </div>

            <div class="vpn-warning">
                <div class="vpn-warning-icon">⚠️</div>
                <div class="vpn-warning-content">
                    <div class="vpn-warning-title">Important: VPN/Proxy Notice</div>
                    <div class="vpn-warning-text">
                        Please <strong>disable any VPN or proxy</strong> before continuing and <strong>keep it off</strong> during the entire process.
                    </div>
                </div>
            </div>

            <div class="instruction-box">
                <div class="instruction-title">
                    <i data-lucide="list-ordered"></i>
                    <span>How to unlock:</span>
                </div>
                <ol class="instruction-steps">
                    <li>Click the unlock button below</li>
                    <li>Complete the quick task (~2 minutes)</li>
                    <li>Return to Roblox and use the feature</li>
                </ol>
            </div>

            <div class="status-msg" id="statusMsg"></div>

            <button class="unlock-btn" id="unlockBtn" onclick="startUnlock()">
                <i data-lucide="unlock"></i>
                Unlock +{config['credits_per_unlock']} Credits
            </button>

            <div class="info-badges">
                <div class="info-badge">
                    <i data-lucide="clock"></i>
                    <span>Takes ~2 minutes</span>
                </div>
                <div class="info-badge">
                    <i data-lucide="zap"></i>
                    <span>+{config['credits_per_unlock']} credits per unlock</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        const FEATURE_ID = "{feature_id}";
        const WORKINK_URL = "{config['workink_url']}";

        function createParticles() {{
            const container = document.getElementById('particles');
            for (let i = 0; i < 20; i++) {{
                const p = document.createElement('div');
                p.className = 'particle';
                p.style.left = Math.random() * 100 + '%';
                p.style.animationDelay = -Math.random() * 20 + 's';
                p.style.animationDuration = (15 + Math.random() * 10) + 's';
                container.appendChild(p);
            }}
        }}

        function showStatus(msg, type) {{
            const el = document.getElementById('statusMsg');
            el.className = 'status-msg show ' + type;
            if (type === 'loading') {{
                el.innerHTML = '<span class="loading-spinner"></span> ' + msg;
            }} else {{
                el.textContent = msg;
            }}
        }}

        async function startUnlock() {{
            const btn = document.getElementById('unlockBtn');
            btn.disabled = true;
            showStatus('Starting verification...', 'loading');

            try {{
                const res = await fetch('/start-unlock/' + FEATURE_ID);
                const data = await res.json();

                if (data.success) {{
                    showStatus('Redirecting...', 'loading');
                    setTimeout(() => {{
                        window.location.href = WORKINK_URL;
                    }}, 800);
                }} else {{
                    showStatus('Failed to start. Please try again.', 'error');
                    btn.disabled = false;
                }}
            }} catch (e) {{
                showStatus('Network error. Please try again.', 'error');
                btn.disabled = false;
            }}
        }}

        window.addEventListener('load', () => {{
            createParticles();
            if (window.lucide) lucide.createIcons();
        }});
    </script>
</body>
</html>
"""

def render_feature_success(config, credits_added, total):
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
            <div class="icon">{config['icon']}</div>
            <h1>Credits Unlocked!</h1>
            <p class="subtitle">You've earned <strong>+{credits_added} {config['name'].lower()}</strong>!</p>
            
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

def render_feature_error(title, message):
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
