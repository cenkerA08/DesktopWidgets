"""Windows launch targets; shortcuts retain their arguments and working directory."""
import os


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
        result = {}
        for item in folder.Items():
            app_id = item.ExtendedProperty('System.AppUserModel.ID')
            path = 'shell:AppsFolder\\' + str(app_id) if app_id else str(item.Path)
            if path and item.Name:
                result[path] = {'name': str(item.Name), 'path': path}
        return sorted(result.values(), key=lambda app: app['name'].casefold())
    finally:
        pythoncom.CoUninitialize()
