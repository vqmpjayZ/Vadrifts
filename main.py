import os
import logging
from flask import Flask, request, jsonify, send_file, redirect
from datetime import datetime

from config import *
from discord_bot import start_bot
from youtube_grabber import YouTubeChannelFinder
from image_converter import convert_image_endpoint
from plugins_manager import PluginsManager
from scripts_data import scripts_data, process_script_data
from utils import inject_meta_tags, server_pinger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

youtube_finder = YouTubeChannelFinder()
plugins_manager = PluginsManager()

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

@app.route('/plugins')
def plugins_page():
    try:
        with open('templates/plugins.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return inject_meta_tags(html_content, PLUGINS_META_TAGS)
    except FileNotFoundError:
        logger.error("plugins.html template not found")
        return jsonify({"error": "Plugins page not found"}), 404

@app.route('/discord')
def discord_invite():
    return redirect("https://discord.com/invite/WDbJ5wE2cR")

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
    logger.info("Discord bot started")

    ping_thread = threading.Thread(target=server_pinger, daemon=True)
    ping_thread.start()
    logger.info("Server pinger started")

    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Vadrifts Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
