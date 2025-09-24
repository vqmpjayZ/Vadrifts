import json
import os
import uuid
import re
from datetime import datetime
from flask import jsonify
import logging
from config import PLUGINS_FILE

logger = logging.getLogger(__name__)

class PluginsManager:
    def __init__(self):
        self.plugins_data = []
        self.rate_limit_data = {}
        self.load_plugins()
    
    def load_plugins(self):
        try:
            if os.path.exists(PLUGINS_FILE):
                with open(PLUGINS_FILE, 'r') as f:
                    self.plugins_data = json.load(f)
            else:
                self.plugins_data = []
        except Exception as e:
            logger.error(f"Error loading plugins: {e}")
            self.plugins_data = []
    
    def save_plugins(self):
        try:
            os.makedirs(os.path.dirname(PLUGINS_FILE), exist_ok=True)
            with open(PLUGINS_FILE, 'w') as f:
                json.dump(self.plugins_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving plugins: {e}")
    
    def get_all_plugins(self):
        sorted_plugins = sorted(self.plugins_data, key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify(sorted_plugins[:50])

    def get_plugin_data(self, plugin_id):
    """Get raw plugin data for display"""
    return next((p for p in self.plugins_data if p['id'] == plugin_id), None)
    
    def create_plugin(self, request):
        try:
            data = request.get_json()
            client_ip = request.remote_addr
            now = datetime.now()
          
            if client_ip in self.rate_limit_data:
                user_data = self.rate_limit_data[client_ip]
                time_diff = (now - user_data['last_create']).total_seconds()
                
                if time_diff < 300 and user_data['count'] >= 2:
                    time_left = int(300 - time_diff)
                    return jsonify({"error": f"You're creating plugins too fast! Wait {time_left} seconds"}), 429
                
                if time_diff >= 300:
                    self.rate_limit_data[client_ip] = {'count': 0, 'last_create': now}
            else:
                self.rate_limit_data[client_ip] = {'count': 0, 'last_create': now}

            if not data.get('name') or not data.get('sections'):
                return jsonify({"error": "Missing required fields"}), 400
            
            name = data['name'][:25]
            author = data.get('author', 'Anonymous')[:20]
            
            if author and author != 'Anonymous':
                if not re.match(r'^[a-zA-Z0-9]+$', author):
                    return jsonify({"error": "Author name can only contain letters and numbers"}), 400
            
            plugin = {
                'id': str(uuid.uuid4()),
                'name': name,
                'author': author if author else 'Anonymous',
                'description': data.get('description', '')[:200],
                'icon': data.get('icon', ''),
                'sections': data['sections'],
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
                'uses': 0
            }
            
            self.plugins_data.append(plugin)
            
            self.rate_limit_data[client_ip]['count'] += 1
            self.rate_limit_data[client_ip]['last_create'] = now
            
            self.save_plugins()
            
            return jsonify(plugin), 201
            
        except Exception as e:
            logger.error(f"Error creating plugin: {e}")
            return jsonify({"error": "Failed to create plugin"}), 500
    
    def get_plugin(self, plugin_id):
        plugin = next((p for p in self.plugins_data if p['id'] == plugin_id), None)
        if plugin:
            plugin['uses'] = plugin.get('uses', 0) + 1
            self.save_plugins()
            return jsonify(plugin)
        return jsonify({"error": "Plugin not found"}), 404
    
    def update_plugin(self, plugin_id, request):
        try:
            data = request.get_json()
            
            plugin = next((p for p in self.plugins_data if p['id'] == plugin_id), None)
            if not plugin:
                return jsonify({"error": "Plugin not found"}), 404
            
            author = data.get('author', 'Anonymous')[:20]
            if author and author != 'Anonymous':
                if not re.match(r'^[a-zA-Z0-9]+$', author):
                    return jsonify({"error": "Author name can only contain letters and numbers"}), 400
            
            plugin['name'] = data.get('name', plugin['name'])[:25]
            plugin['author'] = author if author else 'Anonymous'
            plugin['description'] = data.get('description', '')[:200]
            plugin['icon'] = data.get('icon', '')
            plugin['sections'] = data.get('sections', plugin['sections'])
            plugin['updated_at'] = datetime.now().isoformat()
            
            self.save_plugins()
            
            return jsonify(plugin), 200
            
        except Exception as e:
            logger.error(f"Error updating plugin: {e}")
            return jsonify({"error": "Failed to update plugin"}), 500
    
    def delete_plugin(self, plugin_id):
        plugin = next((p for p in self.plugins_data if p['id'] == plugin_id), None)
        if not plugin:
            return jsonify({"error": "Plugin not found"}), 404
        
        self.plugins_data = [p for p in self.plugins_data if p['id'] != plugin_id]
        self.save_plugins()
        
        return jsonify({"message": "Plugin deleted successfully"}), 200
