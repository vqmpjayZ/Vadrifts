import os

STICKIED_TOKEN = os.environ.get('STICKIED_TOKEN')
MONGODB_URI = os.environ.get('MONGODB_URI')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PLUGINS_FILE = os.path.join(DATA_DIR, 'plugins_data.json')

def make_meta(title, description, path=""):
    url = f"https://vadrifts.onrender.com{path}"
    return f'''
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:url" content="{url}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Vadrifts">
    <meta property="og:image" content="https://i.imgur.com/ePueN25.png">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:image" content="https://i.imgur.com/ePueN25.png">
    <meta name="theme-color" content="#2B2D313">'''

HOME_META_TAGS = make_meta("Vadrifts - Roblox Scripts & Tools", "Vadrift's all-in-one website!")
SCRIPTS_META_TAGS = make_meta("Vadrifts Scripts - Collection", "Check out our collection of all Vadrifts Scripts!", "/scripts")
PLUGINS_META_TAGS = make_meta("Vadrifts Plugins - Community", "Create and share custom bypass plugins!", "/plugins")
