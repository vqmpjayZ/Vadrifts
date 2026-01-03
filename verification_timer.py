import time
import secrets
import threading
from typing import Dict, Any
from datetime import datetime

class VerificationTimer:
    def __init__(self, min_verification_time=75):
        self.timers: Dict[str, Dict[str, Any]] = {}
        self.min_verification_time = min_verification_time
        self.cleanup_interval = 3600
        self.start_cleanup_thread()
    
    def start_cleanup_thread(self):
        """Start a background thread to clean up expired timers."""
        def cleanup_loop():
            while True:
                self.cleanup_expired_timers()
                time.sleep(self.cleanup_interval)
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def create_timer(self, ip: str) -> str:
        """Create a new timer and return its token."""
        token = secrets.token_urlsafe(32)
        self.timers[token] = {
            'ip': ip,
            'started_at': time.time(),
            'used': False
        }
        return token
    
    def check_timer(self, token: str, ip: str) -> Dict[str, Any]:
        """
        Check if a timer exists and has elapsed the minimum time.
        
        Returns:
            Dict with keys:
                valid: bool - whether timer is valid and elapsed min time
                reason: str - reason why timer is invalid (if applicable)
                elapsed: float - seconds elapsed (if timer exists)
        """
        if token not in self.timers:
            return {'valid': False, 'reason': 'invalid_token'}
        
        timer_data = self.timers[token]
        
        if timer_data['used']:
            return {'valid': False, 'reason': 'token_used'}
        
        if timer_data['ip'] != ip:
            return {'valid': False, 'reason': 'ip_mismatch'}
        
        elapsed = time.time() - timer_data['started_at']
        
        if elapsed < self.min_verification_time:
            return {
                'valid': False, 
                'reason': 'time_not_elapsed',
                'elapsed': elapsed,
                'required': self.min_verification_time
            }
        
        return {'valid': True, 'elapsed': elapsed}
    
    def mark_used(self, token: str) -> bool:
        """Mark a timer as used. Returns success."""
        if token in self.timers:
            self.timers[token]['used'] = True
            return True
        return False
    
    def cleanup_expired_timers(self):
        """Remove timers older than 24 hours."""
        current_time = time.time()
        expired_time = 24 * 3600
        
        tokens_to_remove = [
            token for token, data in self.timers.items()
            if current_time - data['started_at'] > expired_time
        ]
        
        for token in tokens_to_remove:
            if token in self.timers:
                del self.timers[token]
