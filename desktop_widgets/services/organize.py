"""Organize folders: suggest a better folder for each app, and find clean-ups.

Nothing here changes data; `analyze` returns suggestions the user reviews
and `apply` (in the manager) carries out the ticked ones.

Categories come from the app's name and program file, plus Steam's own
genres for Steam games (fetched once, cached in data["steam_info"]). Your
folders are matched to categories by their names, so "Racing / Driving"
counts as the racing folder and "Programs" as a general catch-all.
An app only moves when it clearly does not belong where it is.
"""
from __future__ import annotations

import os
import re

# key: (default folder name, words in a folder name, hints in an app's name/exe)
CATEGORIES = {
    "launchers": ("Game Launchers", ("launcher", "launchers", "stores"),
                  ("epic games", "epicgameslauncher", "ubisoft", "uplay", "ea app", "ealauncher", "origin",
                   "riot client", "riotclient", "battle.net", "rockstar games launcher", "gog galaxy",
                   "xbox", "playnite", "heroic", "=steam")),
    "racing": ("Racing", ("racing", "driving", "race", "cars", "sim"),
               ("forza", "assetto", "truck simulator", "rocket league", "rocketleague", "carx", "dirt rally",
                "gran turismo", "need for speed", "beamng", "wreckfest", "iracing", "automobilista", "rfactor",
                "le mans", "moza", "simhub", "trackmania", "the crew", "f1 2", "f1®", "ea sports wrc",
                "project cars", "snowrunner", "mudrunner")),
    "shooter": ("Shooters", ("shooter", "shooters", "fps", "shoot"),
                ("counter-strike", "call of duty", "battlefield", "rainbow six", "pubg", "overwatch",
                 "valorant", "apex legends", "halo", "destiny", "the division", "left 4 dead", "doom",
                 "arena breakout", "tarkov", "the finals", "toxic commando", "insurgency", "hunt showdown",
                 "ready or not", "squad", "titanfall", "delta force", "xdefiant")),
    "story": ("Story & RPG", ("story", "rpg", "adventure", "single", "campaign"),
              ("witcher", "red dead", "cyberpunk", "assassin", "baldur", "elden ring", "last of us",
               "god of war", "ghost of tsushima", "mafia", "grand theft auto", "=gta", "hogwarts", "starfield",
               "fallout", "skyrim", "elder scrolls", "spider-man", "horizon zero", "horizon forbidden",
               "middle-earth", "mass effect", "dragon age", "far cry", "outlast", "resident evil",
               "high on life", "maneater")),
    "online": ("Online", ("online", "multiplayer", "mmo", "co-op", "coop"),
               ("roblox player", "=roblox", "fortnite", "league of legends", "warframe", "for honor",
                "brawlhalla", "diablo", "world of warcraft", "minecraft", "ea sports fc", "fifa", "dota",
                "path of exile", "sea of thieves", "among us", "fall guys", "rust", "dungeon defenders",
                "last man sitting", "tower dominion")),
    "games": ("Games", ("games", "gaming", "other", "play"), ()),
    "dev": ("Dev", ("dev", "code", "coding", "programming", "develop", "development"),
            ("idea64", "intellij", "pycharm", "datagrip", "webstorm", "rider", "clion", "goland", "=code",
             "visual studio", "vscode", "github", "=git", "postman", "docker", "windows terminal",
             "powershell", "=cmd", "sublime", "notepad++", "android studio", "unity hub", "unreal",
             "dbeaver", "robloxstudio", "roblox studio", "dadroit", "=node", "=python", "wsl")),
    "chat": ("Chat", ("chat", "social", "messag", "communication"),
             ("discord", "signal", "whatsapp", "telegram", "slack", "teams", "zoom", "skype", "messenger")),
    "internet": ("Internet", ("browser", "browsers", "internet", "web"),
                 ("firefox", "chrome", "msedge", "=edge", "microsoft edge", "brave", "opera", "vivaldi",
                  "tor browser", "=arc")),
    "media": ("Media", ("media", "music", "video", "creative", "editing", "design"),
              ("spotify", "vlc", "capcut", "=obs", "obs64", "premiere", "photoshop", "davinci", "resolve",
               "audacity", "itunes", "netflix", "media player", "blender", "gimp", "paint.net", "figma",
               "lightroom", "handbrake")),
    "office": ("Office", ("office", "work", "documents", "productivity", "school"),
               ("=word", "winword", "excel", "powerpoint", "outlook", "onenote", "notion", "obsidian",
                "acrobat", "libreoffice")),
    "tools": ("Tools", ("tools", "utilit", "system", "hardware"),
              ("nvidia", "amd software", "radeon", "geforce", "afterburner", "wootility", "g hub", "icue",
               "razer", "steelseries", "localsend", "7-zip", "winrar", "ccleaner", "powertoys", "hwinfo",
               "cpu-z", "=claude", "chatgpt")),
}
GAME_CATS = {"racing", "shooter", "story", "online", "games"}
CATCH_ALL_WORDS = ("programs", "apps", "applications", "software", "misc", "general", "start")
NEW_FOLDER_MIN = 3        # only suggest a new folder for at least this many apps

# Steam genres / categories → our categories.
STEAM_GENRES = {"Racing": "racing", "RPG": "story", "Adventure": "story",
                "Massively Multiplayer": "online", "Sports": "online"}
STEAM_CATEGORIES = {"Online PvP": "online", "PvP": "online", "MMO": "online"}


def steam_appid(app: dict) -> str | None:
    m = re.match(r"steam://rungameid/(\d+)", app.get("launch") or "")
    return m.group(1) if m else None


def _text(app: dict) -> str:
    stem = os.path.splitext(os.path.basename(app.get("path", "")))[0]
    return f"{app.get('name', '')} {stem}".casefold().replace("�", "")


def _hint_matches(hint: str, text: str, name: str) -> bool:
    if hint.startswith("="):                 # whole word or whole name
        word = hint[1:]
        return name == word or re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", text) is not None
    return hint in text


def categories_for(app: dict, steam_info: dict | None = None) -> list[str]:
    """Plausible categories for an app, most likely first."""
    text = _text(app)
    name = (app.get("name") or "").casefold().strip()
    found = []
    for key, (_, _, hints) in CATEGORIES.items():
        if any(_hint_matches(h, text, name) for h in hints):
            found.append(key)
    if "dev" in found and "online" in found and "studio" in text:
        found.remove("online")               # Roblox Studio is a dev tool
    info = (steam_info or {}).get(steam_appid(app) or "", {})
    for genre in info.get("genres", []):
        key = STEAM_GENRES.get(genre)
        if key and key not in found:
            found.append(key)
    for cat in info.get("categories", []):
        key = STEAM_CATEGORIES.get(cat)
        if key and key not in found:
            found.append(key)
    if is_game(app) and not (set(found) & GAME_CATS) and "launchers" not in found:
        found.append("games")
    return found


def is_game(app: dict) -> bool:
    launch = (app.get("launch") or "").lower()
    if launch.startswith(("steam://", "com.epicgames.launcher://", "uplay://", "origin://",
                          "battlenet://", "riotclient://")):
        return True
    from desktop_widgets.ui.app_picker import is_game as picker_is_game
    try:
        return picker_is_game(app)
    except Exception:
        return False


def folder_categories(name: str) -> set[str]:
    low = name.casefold()
    found = set()
    for key, (_, words, _) in CATEGORIES.items():
        if any(re.search(rf"\b{re.escape(w)}", low) for w in words):
            found.add(key)
    return found


def is_catch_all(name: str) -> bool:
    low = name.casefold()
    return not folder_categories(name) or any(w in low for w in CATCH_ALL_WORDS)


def clean_name(name: str) -> str:
    return re.sub(r"\s{2,}", " ", name.replace("�", "")).strip()


def _steam_libraries() -> list[str] | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = winreg.QueryValueEx(key, "SteamPath")[0]
    except OSError:
        return None
    libraries = [steam]
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, encoding="utf-8", errors="ignore") as f:
            libraries += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
    except OSError:
        pass
    return libraries


def steam_installed(appid: str, libraries: list[str]) -> bool:
    return any(os.path.isfile(os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf")) for lib in libraries)


def _works(app: dict) -> bool:
    path = app.get("path", "")
    if app.get("launch") or path.lower().startswith("shell:"):
        return True
    if os.path.exists(path):
        return True
    from desktop_widgets.utils import _find_versioned_app
    try:
        return bool(_find_versioned_app(path))
    except Exception:
        return False


def analyze(data: dict, steam_info: dict | None = None, check_steam: bool = True) -> dict:
    """Suggestions: moves, new folders, duplicates, broken, not installed,
    garbled names and empty folders. Each suggestion has a stable 'id'."""
    groups = data.get("groups", [])
    by_cat_folder: dict[str, dict] = {}
    for g in groups:
        for key in folder_categories(g["name"]):
            by_cat_folder.setdefault(key, g)
    plan = {"moves": [], "new_folders": [], "duplicates": [], "broken": [],
            "not_installed": [], "names": [], "empty": []}

    # Duplicates first: a copy that will be removed is not also moved.
    seen, dropped = {}, set()
    for g in groups:
        for app in g["apps"]:
            key = (app.get("launch") or os.path.normcase(app.get("path", ""))).casefold()
            if key in seen:
                plan["duplicates"].append({"id": f"dup:{g['id']}:{app['path']}", "gid": g["id"],
                                           "app": app, "keep": seen[key]["name"]})
                dropped.add((g["id"], app["path"]))
            else:
                seen[key] = g

    libraries = _steam_libraries() if check_steam else None
    pending_new: dict[str, list] = {}
    for g in groups:
        fcats = folder_categories(g["name"])
        catch_all = is_catch_all(g["name"])
        for app in g["apps"]:
            if (g["id"], app["path"]) in dropped:
                continue
            if "�" in app.get("name", ""):
                plan["names"].append({"id": f"name:{g['id']}:{app['path']}", "gid": g["id"], "app": app,
                                      "new": clean_name(app["name"])})
            if not _works(app):
                plan["broken"].append({"id": f"broken:{g['id']}:{app['path']}", "gid": g["id"], "app": app})
                continue
            appid = steam_appid(app)
            if appid and libraries and not steam_installed(appid, libraries):
                plan["not_installed"].append({"id": f"steam:{g['id']}:{app['path']}", "gid": g["id"],
                                              "app": app})
            cats = categories_for(app, steam_info)
            if not cats or set(cats) & fcats:
                continue
            game_folder = bool(fcats & GAME_CATS)
            if game_folder and set(cats) <= {"games"}:
                continue                      # a game in some game folder: fine
            if not catch_all and not (game_folder and is_game(app)) and not fcats & GAME_CATS:
                pass
            target = next((by_cat_folder[c] for c in cats if c in by_cat_folder
                           and by_cat_folder[c]["id"] != g["id"]), None)
            if target is not None:
                plan["moves"].append({"id": f"move:{g['id']}:{app['path']}", "gid": g["id"], "app": app,
                                      "to": target["id"], "to_name": target["name"],
                                      "from_name": g["name"]})
            elif catch_all:
                pending_new.setdefault(cats[0], []).append((g, app))
    for key, members in pending_new.items():
        if len(members) >= NEW_FOLDER_MIN and key != "games":
            plan["new_folders"].append({"id": f"new:{key}", "name": CATEGORIES[key][0],
                                        "apps": [{"gid": g["id"], "app": app, "from_name": g["name"]}
                                                 for g, app in members]})
    for g in groups:
        if not g["apps"]:
            plan["empty"].append({"id": f"empty:{g['id']}", "gid": g["id"], "name": g["name"]})
    return plan


def count(plan: dict) -> int:
    return sum(len(v) for v in plan.values())


def fetch_steam_info(appids: list[str], known: dict, timeout: float = 6.0) -> dict:
    """Genres and categories from the Steam store for app ids not seen yet.
    Only the ids are sent; failures are skipped (the keywords still work)."""
    import requests
    out = dict(known)
    for appid in appids:
        if appid in out:
            continue
        try:
            r = requests.get("https://store.steampowered.com/api/appdetails",
                             params={"appids": appid, "filters": "genres,categories"}, timeout=timeout)
            body = r.json().get(appid, {})
            info = body.get("data") or {}
            out[appid] = {"genres": [g["description"] for g in info.get("genres", [])],
                          "categories": [c["description"] for c in info.get("categories", [])]}
        except Exception:
            continue
    return out
