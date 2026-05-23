import json
import os
from pathlib import Path


class Store:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(Path.home(), ".stcli")
        self._dir = data_dir
        os.makedirs(self._dir, exist_ok=True)

    def _path(self, name):
        return os.path.join(self._dir, f"{name}.json")

    def _read(self, name):
        p = self._path(name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _write(self, name, data):
        with open(self._path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_bearer_token(self):
        cfg = self._read("config") or {}
        return cfg.get("bearer_token")

    def set_bearer_token(self, token):
        cfg = self._read("config") or {}
        cfg["bearer_token"] = token
        self._write("config", cfg)

    def get_visitor_token(self):
        cfg = self._read("config") or {}
        return cfg.get("visitor_token")

    def set_visitor_token(self, token):
        cfg = self._read("config") or {}
        cfg["visitor_token"] = token
        self._write("config", cfg)

    def get_config(self):
        return self._read("config") or {}

    def set_config(self, config):
        self._write("config", config)

    def add_owner_token(self, file_id, token):
        tokens = self._read("owner_tokens") or {}
        tokens[file_id] = token
        self._write("owner_tokens", tokens)

    def get_owner_token(self, file_id):
        tokens = self._read("owner_tokens") or {}
        return tokens.get(file_id)

    def get_keepalive_files(self):
        return self._read("keepalive") or []

    def add_keepalive(self, file_id, owner_token, days=7, interval_days=6):
        files = self.get_keepalive_files()
        # Check for duplicate
        for f in files:
            if f["file_id"] == file_id:
                return False
        files.append({
            "file_id": file_id,
            "owner_token": owner_token,
            "days": days,
            "interval_days": interval_days,
            "last_renewed": None,
            "status": "pending",
        })
        self._write("keepalive", files)
        return True

    def remove_keepalive(self, file_id):
        files = [f for f in self.get_keepalive_files() if f["file_id"] != file_id]
        self._write("keepalive", files)

    def update_keepalive_status(self, file_id, last_renewed, status):
        files = self.get_keepalive_files()
        for f in files:
            if f["file_id"] == file_id:
                f["last_renewed"] = last_renewed
                f["status"] = status
        self._write("keepalive", files)

    def add_history(self, file_info):
        history = self.get_history()
        history.insert(0, file_info)
        self._write("history", history)

    def get_history(self):
        return self._read("history") or []
