import os

MONGODB_URI = os.environ.get('MONGODB_URI')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PLUGINS_FILE = os.path.join(DATA_DIR, 'plugins_data.json')

HOME_META_TAGS = '''
    <meta property="og:title" content="Vadrifts - Roblox Scripts & Tools">
    <meta property="og:description" content="Vadrift's all-in-one website!">
    <meta property="og:url" content="https://vadrifts.onrender.com">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="theme-color" content="#9c88ff">'''

SCRIPTS_META_TAGS = '''
    <meta property="og:title" content="Vadrifts Scripts - Collection">
    <meta property="og:description" content="Check out our collection of all Vadrifts Scripts!">
    <meta property="og:url" content="https://vadrifts.onrender.com/scripts">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="theme-color" content="#9c88ff">'''

PLUGINS_META_TAGS = '''
    <meta property="og:title" content="Vadrifts Plugins - Community">
    <meta property="og:description" content="Create and share custom bypass plugins!">
    <meta property="og:url" content="https://vadrifts.onrender.com/plugins">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta name="theme-color" content="#9c88ff">'''
