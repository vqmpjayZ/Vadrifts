import os
import logging
from flask import Flask, request, jsonify, send_file, redirect, send_from_directory, make_response
from datetime import datetime

from config import *
from discord_bot import start_bot
from youtube_grabber import YouTubeChannelFinder
from image_converter import convert_image_endpoint
from plugins_manager import PluginsManager
from scripts_data import scripts_data, process_script_data
from utils import inject_meta_tags, server_pinger
from key_system import KeySystemManager

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
        plugin = next((p for p in plugins_manager.plugins_data if str(p.get('id')) == str(plugin_id)), None)
        
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

@app.route('/key-system')
def key_system_page():
    """Serve the key system page"""
    try:
        return send_file('templates/key-system.html')
    except FileNotFoundError:
        logger.error("key-system.html template not found")
        return jsonify({"error": "Key system page not found"}), 404

@app.route('/verify')
def verify_page():
    """Serve the verification page"""
    try:
        return send_file('templates/verify.html')
    except FileNotFoundError:
        logger.error("verify.html template not found")
        return jsonify({"error": "Verify page not found"}), 404

@app.route('/create')
def create_key():
    """Create a key link with HWID"""
    hwid = request.args.get('hwid')
    if not hwid:
        return "Missing HWID", 400
    
    slug = key_system.create_slug(hwid)
    host = request.headers.get('host', 'vadrifts.onrender.com')
    
    logger.info(f"Created key slug for HWID: {hwid[:8]}...")
    return f"https://{host}/getkey/{slug}"

@app.route('/getkey/<slug>')
def get_key(slug):
    """Get key from slug and consume it"""
    hwid = key_system.get_hwid_from_slug(slug)
    
    if not hwid:
        logger.warning(f"Invalid or expired slug attempted: {slug}")
        return "Invalid or expired key link", 404
    
    key_system.consume_slug(slug)
    key = key_system.generate_key(hwid)
    
    logger.info(f"Key generated for HWID: {hwid[:8]}... Key: {key}")
    return key

@app.route('/plugin/<plugin_id>')
def plugin_detail(plugin_id):
    plugin = plugins_manager.get_plugin_data(plugin_id)
    if not plugin:
        return jsonify({"error": "Plugin not found"}), 404
    
    import json
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

from bypass_dashboard import BypassDashboard

bypass_dashboard = BypassDashboard()
bypass_dashboard.register_routes(app)

if __name__ == '__main__':
    import threading

    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    ping_thread = threading.Thread(target=server_pinger, daemon=True)
    ping_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
