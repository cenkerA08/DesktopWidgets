"""Windows launch targets; shortcuts retain their arguments and working directory."""
import os
import hashlib


def app_entry(path, name=None):
    path = os.path.expandvars(str(path).strip().strip('"'))
    shell_app = path.lower().startswith('shell:appsfolder\\')
    if not shell_app and (not os.path.isfile(path) or
                         os.path.splitext(path)[1].lower() not in ('.exe', '.lnk', '.url', '.appref-ms')):
        raise ValueError('Choose an executable or app shortcut (.exe, .lnk, .url, .appref-ms).')
    return {'name': name or os.path.splitext(os.path.basename(path))[0], 'path': path}


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
