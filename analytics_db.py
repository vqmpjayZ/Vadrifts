import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGODB_URI = os.environ.get("MONGODB_URI")
analytics_collection = None

if MONGODB_URI:
    try:
        client = MongoClient(MONGODB_URI)
        db = client["vadrifts"]
        analytics_collection = db["execution_logs"]
        analytics_collection.create_index("timestamp", expireAfterSeconds=5184000)
        client.admin.command('ping')
        logger.info("✅ Connected to MongoDB for analytics")
    except Exception as e:
        logger.error(f"❌ MongoDB analytics connection failed: {e}")


def log_execution(hwid, script):
    if not analytics_collection:
        return
    try:
        analytics_collection.insert_one({
            "hwid": hwid,
            "script": script,
            "timestamp": datetime.utcnow()
        })
    except Exception as e:
        logger.error(f"Failed to log execution: {e}")


def get_analytics():
    empty = {
        'total_executions': 0, 'week_executions': 0, 'month_executions': 0,
        'prev_week_executions': 0, 'prev_month_executions': 0,
        'unique_users_week': 0, 'unique_users_month': 0,
        'script_breakdown': {}, 'chart_labels': [], 'chart_data': [],
        'script_daily_data': {}
    }

    if not analytics_collection:
        return empty

    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=60)
        logs = list(analytics_collection.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}))

        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        month_ago = now - timedelta(days=30)

        week_count = 0
        prev_week_count = 0
        month_count = 0
        prev_month_count = 0
        script_counts = defaultdict(int)
        unique_week = set()
        unique_month = set()
        daily_data = defaultdict(int)
        script_daily = defaultdict(lambda: defaultdict(int))

        for log in logs:
            ts = log["timestamp"]
            script = log.get("script", "Unknown")
            hwid = log.get("hwid", "")

            script_counts[script] += 1
            day_key = ts.strftime("%Y-%m-%d")
            daily_data[day_key] += 1
            script_daily[script][day_key] += 1

            if ts >= week_ago:
                week_count += 1
                unique_week.add(hwid)
            elif ts >= two_weeks_ago:
                prev_week_count += 1

            if ts >= month_ago:
                month_count += 1
                unique_month.add(hwid)
            else:
                prev_month_count += 1

        last_30 = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(29, -1, -1)]
        chart_data = [daily_data.get(d, 0) for d in last_30]

        script_chart = {}
        for script in script_counts:
            script_chart[script] = [script_daily[script].get(d, 0) for d in last_30]

        return {
            'total_executions': len(logs),
            'week_executions': week_count,
            'month_executions': month_count,
            'prev_week_executions': prev_week_count,
            'prev_month_executions': prev_month_count,
            'unique_users_week': len(unique_week),
            'unique_users_month': len(unique_month),
            'script_breakdown': dict(script_counts),
            'chart_labels': last_30,
            'chart_data': chart_data,
            'script_daily_data': script_chart
        }
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return empty
