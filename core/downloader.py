import os
import re
import subprocess
import webbrowser
from api.client import StorageToClient
from core.store import Store


class DownloadEngine:
    def __init__(self, client: StorageToClient, store: Store):
        self.client = client
        self.store = store

    def download(self, file_id_or_url, filename=None):
        file_id = self._extract_file_id(file_id_or_url)
        url = f"https://storage.to/{file_id}"

        config = self.store.get_config()
        mode = config.get("download_mode", "browser")

        if mode == "idm":
            idm_path = config.get("idm_path") or self.detect_idm_path()
            if idm_path and os.path.isfile(idm_path):
                self._download_via_idm(url, idm_path, filename)
                return
        self._open_in_browser(url)

    def _download_via_idm(self, url, idm_path, filename=None):
        cmd = [idm_path, "/d", url]
        if filename:
            cmd += ["/f", filename]
        cmd.append("/a")
        subprocess.Popen(cmd)

    def _open_in_browser(self, url):
        webbrowser.open(url)

    def detect_idm_path(self):
        common_paths = [
            r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe",
            r"C:\Program Files\Internet Download Manager\IDMan.exe",
        ]
        for path in common_paths:
            if os.path.isfile(path):
                return path
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\DownloadManager",
            )
            path, _ = winreg.QueryValueEx(key, "ExePath")
            winreg.CloseKey(key)
            if os.path.isfile(path):
                return path
        except Exception:
            pass
        return None

    def _extract_file_id(self, url_or_id):
        if "/" in url_or_id:
            match = re.search(r"storage\.to/(?:r/|c/)?([A-Za-z0-9]+)", url_or_id)
            if match:
                return match.group(1)
        return url_or_id
