from flask import jsonify, request
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class BypassDashboard:
    def __init__(self):
        self.bypass_status = {
            "words": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0},
            "sentences": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0},
            "roleplay": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0},
            "nsfw_websites": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0},
            "not_legit": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0},
            "Pre-made Bypasses": {"testing": False, "success_rate": "unknown", "last_tested": None, "tester": None, "test_count": 0}
        }
        self.test_history = []

    def get_bypass_status(self, category):
        if category not in self.bypass_status:
            return jsonify({"error": "Category not found"}), 404
        return jsonify({category: self.bypass_status[category]})

    def start_bypass_test(self, category, data):
        if category not in self.bypass_status:
            return jsonify({"error": "Category not found"}), 404
        
        player_id = data.get('player_id', 'Unknown')
        
        if self.bypass_status[category]['testing']:
            return jsonify({
                "success": False, 
                "message": "Already testing",
                "first_tester": False
            })
        
        last_tested = self.bypass_status[category].get('last_tested')
        if last_tested:
            last_tested_date = datetime.fromisoformat(last_tested)
            if datetime.now() - last_tested_date < timedelta(hours=24):
                return jsonify({
                    "success": False,
                    "message": "Already tested today",
                    "first_tester": False
                })
        
        self.bypass_status[category]['testing'] = True
        self.bypass_status[category]['tester'] = player_id
        
        logger.info(f"Bypass test started for {category} by {player_id}")
        
        return jsonify({
            "success": True,
            "message": "Test started",
            "first_tester": True
        })

    def complete_bypass_test(self, category, data):
        if category not in self.bypass_status:
            return jsonify({"error": "Category not found"}), 404
        
        success_rate = data.get('success_rate', 0)
        
        self.bypass_status[category]['testing'] = False
        self.bypass_status[category]['success_rate'] = f"{success_rate}%"
        self.bypass_status[category]['last_tested'] = datetime.now().isoformat()
        self.bypass_status[category]['test_count'] += 1
        
        self.test_history.append({
            "category": category,
            "success_rate": success_rate,
            "tester": self.bypass_status[category]['tester'],
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.test_history) > 100:
            self.test_history = self.test_history[-100:]
        
        logger.info(f"Bypass test completed for {category}: {success_rate}%")
        
        return jsonify({
            "success": True,
            "message": "Test completed",
            "success_rate": f"{success_rate}%"
        })

    def get_all_bypass_status(self):
        return jsonify(self.bypass_status)

    def get_dashboard_stats(self):
        total_categories = len(self.bypass_status)
        tested_today = sum(1 for status in self.bypass_status.values() if status['success_rate'] != 'unknown')
        currently_testing = sum(1 for status in self.bypass_status.values() if status['testing'])
        
        rates = []
        for status in self.bypass_status.values():
            if status['success_rate'] != 'unknown':
                rate = int(status['success_rate'].replace('%', ''))
                rates.append(rate)
        
        avg_success_rate = sum(rates) / len(rates) if rates else 0
        
        return jsonify({
            "total_categories": total_categories,
            "tested_today": tested_today,
            "currently_testing": currently_testing,
            "average_success_rate": round(avg_success_rate, 1),
            "categories": self.bypass_status
        })

    def get_test_history(self):
        return jsonify({
            "history": self.test_history[-20:],
            "total_tests": len(self.test_history)
        })

    def register_routes(self, app):
        @app.route('/dashboard')
        def dashboard():
            try:
                with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                from utils import inject_meta_tags
                meta_tags = '''
    <meta property="og:title" content="Bypass Dashboard - Vadrifts">
    <meta property="og:description" content="Real-time bypass testing statistics and status">
    <meta property="og:url" content="https://vadrifts.onrender.com/dashboard">
    <meta property="og:type" content="website">
    <meta name="theme-color" content="#9c88ff">'''
                
                return inject_meta_tags(html_content, meta_tags)
            except FileNotFoundError:
                logger.error("dashboard.html template not found")
                return jsonify({"error": "Dashboard page not found"}), 404

        @app.route('/api/bypass-status/<category>', methods=['GET'])
        def get_bypass_status_route(category):
            return self.get_bypass_status(category)

        @app.route('/api/bypass-status/<category>/start', methods=['POST'])
        def start_bypass_test_route(category):
            return self.start_bypass_test(category, request.get_json())

        @app.route('/api/bypass-status/<category>/complete', methods=['POST'])
        def complete_bypass_test_route(category):
            return self.complete_bypass_test(category, request.get_json())

        @app.route('/api/bypass-status/all', methods=['GET'])
        def get_all_bypass_status_route():
            return self.get_all_bypass_status()

        @app.route('/api/dashboard/stats', methods=['GET'])
        def get_dashboard_stats_route():
            return self.get_dashboard_stats()

        @app.route('/api/dashboard/history', methods=['GET'])
        def get_test_history_route():
            return self.get_test_history()
