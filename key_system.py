import hashlib
import time
import threading
import random
import string
from datetime import datetime

class KeySystemManager:
    def __init__(self):
        self.active_slugs = {}
    
    def generate_key(self, hwid):
        """Generate a key based on HWID and 48-hour time period"""
        period = int(time.time() // (60 * 60 * 48))
        hash_input = f"{hwid}{period}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def create_slug(self, hwid):
        """Create a temporary slug that expires in 5 minutes"""
        slug = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
        self.active_slugs[slug] = hwid
        
        def remove_slug():
            if slug in self.active_slugs:
                del self.active_slugs[slug]
        
        timer = threading.Timer(300, remove_slug)
        timer.start()
        
        return slug
    
    def get_hwid_from_slug(self, slug):
        """Retrieve and consume a slug"""
        return self.active_slugs.get(slug)
    
    def consume_slug(self, slug):
        """Remove slug after use"""
        if slug in self.active_slugs:
            del self.active_slugs[slug]
