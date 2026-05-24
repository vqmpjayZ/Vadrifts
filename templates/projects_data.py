projects = [
    {
        "id": "arrayfield",
        "title": "ArrayField",
        "category": "roblox",
        "description": "Roblox UI library — a modified Rayfield with the deepest feature set of any library in the scene.",
        "logo": "https://i.imgur.com/W9FaXAY.png",
        "icon": "https://i.imgur.com/ePueN25.png",
        "logo_animation": "shine",
        "stack": ["Lua", "Roblox"],
        "link": "/docs/arrayfield",
        "link_internal": True,
        "status": "live",
        "spotlight": True,
        "spotlight_image": "https://i.imgur.com/W9FaXAY.png",
        "spotlight_eyebrow": "Just shipped",
        "spotlight_blurb": "Tabs, sections, dropdowns, sliders, color pickers, key binds, notifications — read the docs and drop it in.",
    },
    {
        "id": "roblox-scripts",
        "title": "Roblox Scripts",
        "category": "roblox",
        "description": "The full script collection — Vadrifts.byp, Starving Artists, Horrific Housing, and more, all in one hub.",
        "logo": "blob:https://imgur.com/a6be7141-1b67-4d8b-95ec-a1643a438bc8",
        "icon": "https://i.imgur.com/qTlJ8NW_d.png?maxwidth=520&shape=thumb&fidelity=high",
        "logo_animation": "spin-slow",
        "stack": ["Lua", "Roblox"],
        "link": "/scripts",
        "link_internal": True,
        "status": "live",
        "spotlight": True,
        "spotlight_image": "https://i.imgur.com/jI8qDiR.jpeg",
        "spotlight_eyebrow": "Browse the catalog",
        "spotlight_blurb": "Bypassers, ESP, auto-claim, godmode — every script Vadrifts has ever shipped, free, with active updates.",
    },
    {
        "id": "image-converter",
        "title": "Image Converter",
        "category": "webapp",
        "description": "Drag a file, pick a format, download. Web app for fast PNG ↔ JPG ↔ WEBP ↔ AVIF conversions, no upload limits.",
        "logo": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ7ZGXZbvAayG-OlsNXKP8ji-YJCNpUyF7-8Q&s",
        "icon": "https://i.imgur.com/f582ocU.png",
        "logo_animation": "spin-slow",
        "stack": ["Python", "Flask", "Pillow"],
        "link": "/converter",
        "link_internal": True,
        "status": "live",
        "spotlight": False,
        "spotlight_image": "",
        "spotlight_eyebrow": "",
        "spotlight_blurb": "",
    },
    {
        "id": "audio-editor",
        "title": "Audio Editor",
        "category": "webapp",
        "description": "In-browser waveform editor — trim, fade, crossfade, export. Zero installs, runs on WebAudio + Wavesurfer.",
        "logo": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ7ZGXZbvAayG-OlsNXKP8ji-YJCNpUyF7-8Q&s",
        "icon": "",
        "logo_animation": "pulse",
        "stack": ["React", "WebAudio"],
        "link": "#",
        "link_internal": True,
        "status": "coming-soon",
        "spotlight": True,
        "spotlight_image": "",
        "spotlight_eyebrow": "In the workshop",
        "spotlight_blurb": "Soon™ — a real audio editor in the browser. Trim, fade, crossfade, export. No accounts, no upload caps.",
    },
]


project_categories = [
    {"id": "all",        "label": "All"},
    {"id": "roblox",     "label": "Roblox"},
    {"id": "webapp",     "label": "Web Apps"},
    {"id": "userscript", "label": "Userscripts"},
    {"id": "extension",  "label": "Extensions"},
]


def process_projects_data(project_list):
    status_map = {
        "live":        ("LIVE",        "status-live"),
        "beta":        ("BETA",        "status-beta"),
        "coming-soon": ("COMING SOON", "status-soon"),
    }
    for p in project_list:
        p["is_external"] = not p.get("link_internal", True)
        label, klass = status_map.get(p.get("status", "live"), ("LIVE", "status-live"))
        p["status_badge"] = label
        p["status_class"] = klass
    return project_list


def get_spotlight_projects(project_list):
    return [p for p in project_list if p.get("spotlight")]