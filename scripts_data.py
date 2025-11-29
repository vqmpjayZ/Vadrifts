scripts_data = [
    {
        "id": 1,
        "title": "Vadrifts.byp",
        "game": "Universal",
        "thumbnail": "https://i.imgur.com/jI8qDiR.jpeg",
        "description": "Best and undetected Roblox Chat Bypasser. Bypasses the Roblox Chat Filters allowing you to Swear on roblox!",
        "features": [
            "Chat Bypass",
            "Mobile Friendly",
            "User Friendly", 
            "Works on ALL executors",
            "Automatic chat bypasser",
            "Tag Detection",
            "70+ Premade bypasses",
            "Mod-watch",
            "Client-chat report bypass",
            "Animations",
            "Bang",
            "Chat tools AND MORE!!",
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/Bypass/main/vadrifts.lua"))()''',
        "key_type": "discord",
        "key_link": "https://discord.com/invite/WDbJ5wE2cR"
    },
    {
        "id": 8916037983,
        "title": "Starving Artists Script",
        "game": "Starving Artists",
        "thumbnail": "https://tr.rbxcdn.com/180DAY-808f20386cb8582fcd0075aae67cd039/768/432/Image/Webp/noFilter",
        "description": "A Free starving artists script by Vadrifts with a simple and easy Discord Key System.",
        "features": [
            "Advanced and Customizable Image Generator (bypasses anti-cheat)",
            "Advanced Art Stealer / Art Copier (also bypasses anti-cheat)", 
            "Auto Claim Booth",
            "Auto Claim Daily Rewards",
            "Advanced and Customizable Server Hopper (will not server hop you if someone is on your plot; serverhop timer gets automatically increased every time someone buys art from you or tips you)",
            "Auto Chat (Auto Thank you, Customizable Auto Beg)",
            "Discord Webhook notifier",
            "Duplicate art checker",
            "Modwatch",
            "Anti-AFK",
            "Mobile Support",
            "User-Friendly",
            "Supports All executors",
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/Vadrifts-Hub/refs/heads/main/Games/Starving-Artists/source.lua"))()''',
        "key_type": "discord",
        "key_link": "https://discord.com/invite/WDbJ5wE2cR"
    },
    {
        "id": 263761432,
        "title": "Horrific Housing Script",
        "game": "Horrific Housing",
        "thumbnail": "https://tr.rbxcdn.com/180DAY-8598e6c1626e3ccf16eb8b3acbd618fe/768/432/Image/Webp/noFilter",
        "description": "Best keyless Horrific Housing script with tons of features!",
        "features": [
            "Keyless",
            "Mobile Friendly", 
            "ALL executor support",
            "Infinite tokens (patched)",
            "Unlock all items (patched)",
            "ESP",
            "Reach",
            "Item Grabber",
            "Weapon Exploit",
            "Godmode",
            "Fly",
            "Teleportation",
            "Auto Complete Obby"
        ],
        "script": '''loadstring(game:HttpGet("https://raw.githubusercontent.com/vqmpjayZ/More-Scripts/refs/heads/main/Vadrifts-Horrific-Housing.lua"))()''',
        "key_type": "no-key"
    },
]

def process_script_data(scripts):
    for script in scripts:
        if str(script.get('id', '')).isdigit():
            script['game_link'] = f"https://www.roblox.com/games/{script['id']}"
        elif script.get('game', '').lower() == 'universal':
            script['game_link'] = "https://www.roblox.com/games"
        else:
            script['game_link'] = "https://www.roblox.com/games"
    
    return scripts
