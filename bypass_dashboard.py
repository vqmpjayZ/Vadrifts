from datetime import datetime, timedelta
import time
from flask import jsonify

class BypassDashboard:
    TESTING_TIMEOUT = 300
    
    def __init__(self):
        self.statuses = {}
    
    def check_and_clear_stale_tests(self):
        current_time = time.time()
        
        for category, status in self.statuses.items():
            if status.get('testing') and status.get('started_at'):
                elapsed = current_time - status['started_at']
                if elapsed > self.TESTING_TIMEOUT:
                    print(f"Clearing stale test for {category} (ran for {elapsed:.0f}s)")
                    status['testing'] = False
                    status['started_at'] = None
                    status['tester'] = None
    
    def get_bypass_status(self, category):
        self.check_and_clear_stale_tests()
        
        if category not in self.statuses:
            self.statuses[category] = {
                'success_rate': 'unknown',
                'last_tested': None,
                'testing': False,
                'tester': None,
                'started_at': None,
                'test_count': 0
            }
        
        status = self.statuses[category].copy()
        if 'started_at' in status:
            del status['started_at']
        
        return status
    
    def start_bypass_test(self, category, player_id):
        self.check_and_clear_stale_tests()
        
        if category not in self.statuses:
            self.statuses[category] = {
                'success_rate': 'unknown',
                'last_tested': None,
                'testing': False,
                'tester': None,
                'started_at': None,
                'test_count': 0
            }
        
        status = self.statuses[category]
        
        if status['testing']:
            return {'first_tester': False, 'reason': 'already_testing'}

        if status['last_tested']:
            last_test = datetime.fromisoformat(status['last_tested'])
            if last_test.date() == datetime.now().date():
                return {'first_tester': False, 'reason': 'already_tested_today'}

        status['testing'] = True
        status['tester'] = player_id
        status['started_at'] = time.time()

        return {'first_tester': True}
    
    def complete_bypass_test(self, category, success_rate):
        if category not in self.statuses:
            return {'success': False, 'error': 'Category not found'}
        
        status = self.statuses[category]
        status['success_rate'] = f'{success_rate}%'
        status['last_tested'] = datetime.now().isoformat()
        status['testing'] = False
        status['tester'] = None
        status['started_at'] = None
        status['test_count'] = status.get('test_count', 0) + 1
        
        return {'success': True, 'success_rate': status['success_rate']}
    
    def cancel_bypass_test(self, category):
        if category in self.statuses:
            self.statuses[category]['testing'] = False
            self.statuses[category]['tester'] = None
            self.statuses[category]['started_at'] = None
            return {'success': True}
        return {'success': False, 'error': 'Category not found'}
    
    def get_dashboard_stats(self):
        self.check_and_clear_stale_tests()
        
        total_categories = len(self.statuses)
        tested_today = 0
        currently_testing = 0
        total_success = 0
        tested_count = 0
        
        for status in self.statuses.values():
            if status['testing']:
                currently_testing += 1
            
            if status['last_tested']:
                last_test = datetime.fromisoformat(status['last_tested'])
                if datetime.now() - last_test < timedelta(hours=24):
                    tested_today += 1
            
            if status['success_rate'] != 'unknown':
                rate = int(status['success_rate'].replace('%', ''))
                total_success += rate
                tested_count += 1
        
        avg_success_rate = int(total_success / tested_count) if tested_count > 0 else 0
        
        return {
            'total_categories': total_categories,
            'tested_today': tested_today,
            'currently_testing': currently_testing,
            'average_success_rate': avg_success_rate,
            'categories': self.statuses
        }
    
    def register_routes(self, app):
        @app.route('/api/bypass-status/<category>', methods=['GET'])
        def get_status(category):
            status = self.get_bypass_status(category)
            return jsonify(status)
        
        @app.route('/api/bypass-status/<category>/start', methods=['POST'])
        def start_test(category):
            from flask import request
            data = request.get_json()
            player_id = data.get('player_id')
            result = self.start_bypass_test(category, player_id)
            return jsonify(result)
        
        @app.route('/api/bypass-status/<category>/complete', methods=['POST'])
        def complete_test(category):
            from flask import request
            data = request.get_json()
            success_rate = data.get('success_rate')
            result = self.complete_bypass_test(category, success_rate)
            return jsonify(result)
        
        @app.route('/api/bypass-status/<category>/cancel', methods=['POST'])
        def cancel_test(category):
            result = self.cancel_bypass_test(category)
            return jsonify(result)
        
        @app.route('/api/dashboard/stats', methods=['GET'])
        def dashboard_stats():
            stats = self.get_dashboard_stats()
            return jsonify(stats)
        
        @app.route('/dashboard')
        def dashboard_page():
            from flask import send_file
            try:
                return send_file('templates/dashboard.html')
            except FileNotFoundError:
                return jsonify({"error": "Dashboard page not found"}), 404
