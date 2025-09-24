import requests
import re
import time
import logging
from flask import jsonify

logger = logging.getLogger(__name__)

class YouTubeChannelFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })
        self.cache = {}
        self.cache_duration = 7200
    
    def find_channel_by_username(self, username):
        cache_key = username.lower().strip()
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']
        
        logger.info(f"Fetching channel data for: {username}")
        
        channel_data = self._try_direct_url(username)
        if channel_data and channel_data.get('found'):
            self._cache_result(cache_key, channel_data)
            return channel_data
        
        channel_data = self._search_channel(username)
        if channel_data:
            self._cache_result(cache_key, channel_data)
            return channel_data
        
        return {
            'name': username,
            'handle': f'@{username}',
            'url': f'https://www.youtube.com/@{username}',
            'pfp_url': None,
            'found': False
        }
    
    def _try_direct_url(self, username):
        urls = [
            f"https://www.youtube.com/@{username}",
            f"https://www.youtube.com/c/{username}",
            f"https://www.youtube.com/user/{username}"
        ]
        
        for url in urls:
            try:
                response = self.session.get(url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    return self._extract_channel_data(response.text, response.url, username)
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                continue
        
        return None
    
    def _search_channel(self, username):
        try:
            search_url = f"https://www.youtube.com/results?search_query={username}&sp=EgIQAg%253D%253D"
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                data = self._extract_from_search(response.text, username)
                if data:
                    return data
        except Exception as e:
            logger.error(f"Search failed for {username}: {e}")
        
        return None
    
    def _extract_channel_data(self, html_content, url, username):
        try:
            name_match = re.search(r'"name":\s*"([^"]+)"', html_content)
            if not name_match:
                name_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
            
            channel_name = name_match.group(1) if name_match else username

            pfp_url = None

            patterns = [
            r'"channelMetadataRenderer":{"title":"([^"]+)"',
            r'<meta property="og:title" content="([^"]+)"',
            r'"title":"([^"]+)","navigationEndpoint"',
            r'<title>([^<]+)</title>'
        ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content)
                if match:
                    pfp_url = match.group(1).replace('\\u003d', '=')
                    if 'yt3.ggpht.com' in pfp_url or 'ytimg.com' in pfp_url:
                        break
            
            return {
                'name': channel_name,
                'handle': f'@{username}',
                'url': url,
                'pfp_url': pfp_url,
                'found': True
            }
        except Exception as e:
            logger.error(f"Error extracting channel data: {e}")
            return None
    
    def _extract_from_search(self, html_content, username):
        try:
            pattern = r'"channelRenderer":({[^}]+})'
            matches = re.finditer(pattern, html_content)
            
            for match in matches:
                try:
                    channel_json = match.group(1)

                    channel_id_match = re.search(r'"channelId":"([^"]+)"', channel_json)
                    if channel_id_match:
                        channel_url = f"https://www.youtube.com/channel/{channel_id_match.group(1)}"

                        response = self.session.get(channel_url, timeout=10)
                        if response.status_code == 200:
                            return self._extract_channel_data(response.text, response.url, username)
                except:
                    continue
        except Exception as e:
            logger.error(f"Error extracting from search: {e}")
        
        return None
    
    def _cache_result(self, key, data):
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def find_multiple_channels(self, usernames):
        if not usernames:
            return jsonify({'error': 'No usernames provided'}), 400
        
        channels = []
        for username in usernames:
            username = username.strip()
            if username:
                channel_data = self.find_channel_by_username(username)
                channels.append(channel_data)
        
        return jsonify({'channels': channels})
