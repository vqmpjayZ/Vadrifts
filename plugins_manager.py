import uuid
import re
from datetime import datetime
from flask import jsonify
import logging
from pymongo import MongoClient
from config import MONGODB_URI

logger = logging.getLogger(__name__)

class PluginsManager:
    def __init__(self):
        self.rate_limit_data = {}
        try:
            self.client = MongoClient(MONGODB_URI)
            self.db = self.client['vadrifts']
            self.plugins = self.db['plugins']
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.plugins = None
    
    def get_all_plugins(self):
        try:
            if not self.plugins:
                return jsonify([])
            
            plugins_list = list(self.plugins.find({}, {'_id': 0}).sort('created_at', -1).limit(50))
            return jsonify(plugins_list)
        except Exception as e:
            logger.error(f"Error getting plugins: {e}")
            return jsonify([])
    
    def get_plugin_data(self, plugin_id):
        try:
            if not self.plugins:
                return None
            return self.plugins.find_one({'id': plugin_id}, {'_id': 0})
        except Exception as e:
            logger.error(f"Error getting plugin data: {e}")
            return None
    
    def create_plugin(self, request):
        try:
            if not self.plugins:
                return jsonify({"error": "Database not available"}), 500
            
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
            
            self.plugins.insert_one(plugin.copy())

            self.rate_limit_data[client_ip]['count'] += 1
            self.rate_limit_data[client_ip]['last_create'] = now
            
            return jsonify(plugin), 201
            
        except Exception as e:
            logger.error(f"Error creating plugin: {e}")
            return jsonify({"error": "Failed to create plugin"}), 500
    
    def get_plugin(self, plugin_id):
        try:
            if not self.plugins:
                return jsonify({"error": "Database not available"}), 500
            
            plugin = self.plugins.find_one({'id': plugin_id}, {'_id': 0})
            
            if plugin:
                self.plugins.update_one(
                    {'id': plugin_id},
                    {'$inc': {'uses': 1}}
                )
                plugin['uses'] = plugin.get('uses', 0) + 1
                return jsonify(plugin)
            
            return jsonify({"error": "Plugin not found"}), 404
        except Exception as e:
            logger.error(f"Error getting plugin: {e}")
            return jsonify({"error": "Failed to get plugin"}), 500
    
    def update_plugin(self, plugin_id, request):
        try:
            if not self.plugins:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json()
            
            plugin = self.plugins.find_one({'id': plugin_id}, {'_id': 0})
            if not plugin:
                return jsonify({"error": "Plugin not found"}), 404
            
            author = data.get('author', 'Anonymous')[:20]
            if author and author != 'Anonymous':
                if not re.match(r'^[a-zA-Z0-9]+$', author):
                    return jsonify({"error": "Author name can only contain letters and numbers"}), 400
            
            update_data = {
                'name': data.get('name', plugin['name'])[:25],
                'author': author if author else 'Anonymous',
                'description': data.get('description', '')[:200],
                'icon': data.get('icon', ''),
                'sections': data.get('sections', plugin['sections']),
                'updated_at': datetime.now().isoformat()
            }
            
            self.plugins.update_one({'id': plugin_id}, {'$set': update_data})
            
            updated_plugin = self.plugins.find_one({'id': plugin_id}, {'_id': 0})
            return jsonify(updated_plugin), 200
            
        except Exception as e:
            logger.error(f"Error updating plugin: {e}")
            return jsonify({"error": "Failed to update plugin"}), 500
    
    def delete_plugin(self, plugin_id):
        try:
            if not self.plugins:
                return jsonify({"error": "Database not available"}), 500
            
            result = self.plugins.delete_one({'id': plugin_id})
            
            if result.deleted_count == 0:
                return jsonify({"error": "Plugin not found"}), 404
            
            return jsonify({"message": "Plugin deleted successfully"}), 200
        except Exception as e:
            logger.error(f"Error deleting plugin: {e}")
            return jsonify({"error": "Failed to delete plugin"}), 500
