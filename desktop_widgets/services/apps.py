"""Windows launch targets; shortcuts retain their arguments and working directory."""
import os
import hashlib


def normalize_path(path):
    """Explorer drops arrive as C:/x/y; Shell icon APIs only accept C:\\x\\y."""
    path = os.path.expandvars(str(path).strip().strip('{}').strip('"'))
    if not path or path.lower().startswith('shell:'):
        return path
    return os.path.normpath(path)


def app_entry(path, name=None):
    path = normalize_path(path)
    shell_app = path.lower().startswith('shell:appsfolder\\')
    if not shell_app and (not os.path.isfile(path) or
                         os.path.splitext(path)[1].lower() not in ('.exe', '.lnk', '.url', '.appref-ms')):
        raise ValueError('Choose an executable or app shortcut (.exe, .lnk, .url, .appref-ms).')
    entry = {'name': name or os.path.splitext(os.path.basename(path))[0], 'path': path}
    if path.lower().endswith('.url'):
        entry.update(_url_details(path))
    return entry


def _url_details(path):
    """Keep a .url shortcut's launch link and icon, so the entry still works
    after the shortcut file is moved or deleted (desktop clean-ups)."""
    details = {}
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                key, _, value = line.strip().partition('=')
                if key.upper() == 'URL' and value and not value.lower().startswith('http'):
                    details['launch'] = value
                elif key.upper() == 'ICONFILE':
                    icon = os.path.expandvars(value.strip('"').rsplit(',', 1)[0])
                    if os.path.isfile(icon):
                        details['icon_path'] = icon
    except OSError:
        pass
    return details


def _plain(name):
    return ''.join(ch for ch in str(name).casefold() if ch.isalnum())


def steam_games():
    """{normalised game name: appid} for installed Steam games."""
    import re
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            steam = winreg.QueryValueEx(key, 'SteamPath')[0]
    except OSError:
        return {}
    libraries = [steam]
    vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
    try:
        with open(vdf, encoding='utf-8', errors='ignore') as f:
            # .vdf escapes backslashes: "D:\\Games\\Steam"
            libraries += [m.replace('\\\\', '\\') for m in re.findall(r'"path"\s+"([^"]+)"', f.read())]
    except OSError:
        pass
    games = {}
    for library in libraries:
        folder = os.path.join(library, 'steamapps')
        try:
            names = [n for n in os.listdir(folder) if n.startswith('appmanifest_') and n.endswith('.acf')]
        except OSError:
            continue
        for manifest in names:
            try:
                with open(os.path.join(folder, manifest), encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            except OSError:
                continue
            appid, name = re.search(r'"appid"\s+"(\d+)"', text), re.search(r'"name"\s+"([^"]+)"', text)
            if appid and name:
                games[_plain(name.group(1))] = appid.group(1)
    return games


def repair_missing_shortcuts(data):
    """Give .url entries whose shortcut file is gone their Steam launch link back.
    Returns True when something was repaired."""
    broken = [app for group in data.get('groups', []) for app in group.get('apps', [])
              if app.get('path', '').lower().endswith('.url') and not app.get('launch')
              and not os.path.exists(app['path'])]
    if not broken:
        return False
    games = steam_games()
    fixed = False
    for app in broken:
        appid = games.get(_plain(app.get('name', '')))
        if appid:
            app['launch'] = f'steam://rungameid/{appid}'
            fixed = True
    return fixed


def installed_apps():
    """Enumerate registered desktop and Store apps without opening protected EXEs."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        folder = win32com.client.Dispatch('Shell.Application').NameSpace('shell:AppsFolder')
        if folder is None:
            raise RuntimeError('Windows did not return the installed apps folder.')
        shortcuts = {}
        for location in (os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows',
                                      'Start Menu', 'Programs'),
                         os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Windows',
                                      'Start Menu', 'Programs')):
            if not os.path.isdir(location):
                continue
            for parent, _, files in os.walk(location):
                for filename in files:
                    if filename.lower().endswith(('.lnk', '.url')):
                        key = os.path.splitext(filename)[0].casefold()
                        shortcuts.setdefault(key, os.path.join(parent, filename))
        result = {}
        for item in folder.Items():
            app_id = item.ExtendedProperty('System.AppUserModel.ID')
            path = shortcuts.get(str(item.Name).casefold())
            if not path:
                path = 'shell:AppsFolder\\' + str(app_id) if app_id else str(item.Path)
            if path and item.Name:
                result[path] = {'name': str(item.Name), 'path': path}
        return sorted(result.values(), key=lambda app: app['name'].casefold())
    finally:
        pythoncom.CoUninitialize()


def cache_store_icon(entry):
    """Keep Store artwork as a local PNG so it survives Shell icon lookup failures."""
    path = entry.get('path', '')
    if not path.lower().startswith('shell:appsfolder\\'):
        return entry
    try:
        from PIL import ImageTk
        from desktop_widgets.config import DATA_DIR
        from desktop_widgets.utils import _shell_icon
        photo = _shell_icon(path, 128)
        if photo is None:
            return entry
        folder = os.path.join(DATA_DIR, 'icons')
        os.makedirs(folder, exist_ok=True)
        digest = hashlib.sha256(path.encode('utf-8')).hexdigest()[:24]
        target = os.path.join(folder, digest + '.png')
        if not os.path.isfile(target):
            ImageTk.getimage(photo).save(target, 'PNG')
        return {**entry, 'icon_path': target}
    except (OSError, ValueError, RuntimeError):
        return entry
