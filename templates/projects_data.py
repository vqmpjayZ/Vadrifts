"""
projects_data.py — single source of truth for the /projects hub.

Mirrors the scripts_data.py pattern. To add a project, append a dict
below and (optionally) drop a transparent PNG logo on imgur. The page
renders from this list — no template edits needed.

Card schema
-----------
id                : str   — url-safe slug, used as DOM id and filter key
title             : str   — display name (kept short, ~24 chars max)
category          : str   — one of: roblox | webapp | userscript | extension
description       : str   — 1–2 sentence pitch (~140 chars, truncated in CSS)
logo              : str   — transparent PNG url, imgur preferred
logo_animation    : str   — hover anim hint: spin-slow | pulse | tilt |
                            float | shine | none
stack             : list  — small badges shown at card foot
                            (e.g. ["Lua"], ["React", "Flask"])
link              : str   — destination (internal path or external url)
link_internal     : bool  — True for same-tab Flask routes, False opens
                            in a new tab with rel=noopener
status            : str   — live | coming-soon | beta
spotlight         : bool  — include in the auto-cycling top strip
spotlight_image   : str   — wide banner used in the strip (~1600x600)
spotlight_eyebrow : str   — small kicker copy ("Just shipped", "Soon", ...)
spotlight_blurb   : str   — 1 sentence shown next to the banner image

Order matters for the spotlight strip (top-down = cycle order).
"""

projects = [
    {
        "id": "arrayfield",
        "title": "ArrayField",
        "category": "roblox",
        "description": (
            "Roblox UI library — a modified Rayfield with the deepest "
            "feature set of any library in the scene."
        ),
        "logo": "https://i.imgur.com/W9FaXAY.png",
        "logo_animation": "shine",
        "stack": ["Lua", "Roblox"],
        "link": "/docs/arrayfield",
        "link_internal": True,
        "status": "live",
        "spotlight": True,
        "spotlight_image": "https://i.imgur.com/W9FaXAY.png",
        "spotlight_eyebrow": "Just shipped",
        "spotlight_blurb": (
            "Tabs, sections, dropdowns, sliders, color pickers, key "
            "binds, notifications — read the docs and drop it in."
        ),
    },
    {
        "id": "roblox-scripts",
        "title": "Roblox Scripts",
        "category": "roblox",
        "description": (
            "The full script collection — Vadrifts.byp, Starving "
            "Artists, Horrific Housing, and more, all in one hub."
        ),
        "logo": "https://i.imgur.com/ePueN25.png",
        "logo_animation": "spin-slow",
        "stack": ["Lua", "Roblox"],
        "link": "/scripts",
        "link_internal": True,
        "status": "live",
        "spotlight": True,
        "spotlight_image": "https://i.imgur.com/jI8qDiR.jpeg",
        "spotlight_eyebrow": "Browse the catalog",
        "spotlight_blurb": (
            "Bypassers, ESP, auto-claim, godmode — every script "
            "Vadrifts has ever shipped, free, with active updates."
        ),
    },
    {
        "id": "image-converter",
        "title": "Image Converter",
        "category": "webapp",
        "description": (
            "Drag a file, pick a format, download. Web app for fast "
            "PNG ↔ JPG ↔ WEBP ↔ AVIF conversions, no upload limits."
        ),
        "logo": "https://i.imgur.com/ePueN25.png",
        "logo_animation": "pulse",
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
        "description": (
            "In-browser waveform editor — trim, fade, crossfade, "
            "export. Zero installs, runs on WebAudio + Wavesurfer."
        ),
        "logo": "https://i.imgur.com/ePueN25.png",
        "logo_animation": "pulse",
        "stack": ["React", "WebAudio"],
        "link": "#",
        "link_internal": True,
        "status": "coming-soon",
        "spotlight": True,
        "spotlight_image": "https://i.imgur.com/ePueN25.png",
        "spotlight_eyebrow": "In the workshop",
        "spotlight_blurb": (
            "Soon™ — a real audio editor in the browser. Trim, fade, "
            "crossfade, export. No accounts, no upload caps."
        ),
    },
]


# Category metadata used by the filter chip row.
# Order here = chip order on the page.
project_categories = [
    {"id": "all",        "label": "All"},
    {"id": "roblox",     "label": "Roblox"},
    {"id": "webapp",     "label": "Web Apps"},
    {"id": "userscript", "label": "Userscripts"},
    {"id": "extension",  "label": "Extensions"},
]


def process_projects_data(project_list):
    """
    Hook for derived fields. Mirrors process_script_data() in shape so
    main.py can pipeline both the same way. Currently:
      - injects `is_external` boolean for template convenience
      - injects `status_badge` (display label) and `status_class`
        (css modifier) so the template stays dumb
    """
    status_map = {
        "live":        ("LIVE",        "status-live"),
        "beta":        ("BETA",        "status-beta"),
        "coming-soon": ("COMING SOON", "status-soon"),
    }
    for p in project_list:
        p["is_external"] = not p.get("link_internal", True)
        label, klass = status_map.get(
            p.get("status", "live"), ("LIVE", "status-live")
        )
        p["status_badge"] = label
        p["status_class"] = klass
    return project_list


def get_spotlight_projects(project_list):
    """Convenience accessor — keeps template logic minimal."""
    return [p for p in project_list if p.get("spotlight")]
