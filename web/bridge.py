from datetime import datetime, timezone
import threading


class ApiBridge:
    def __init__(self):
        self._window = None
        self._client = None
        self._store = None
        self._upload_progress = {}
        self._upload_lock = threading.Lock()

    def set_window(self, window):
        self._window = window

    def _ensure_client(self):
        if self._client is None:
            from core.store import Store
            from api.client import StorageToClient
            self._store = Store()
            token = self._store.get_bearer_token()
            visitor_token = self._store.get_visitor_token()
            if token:
                self._client = StorageToClient(token=token)
            elif visitor_token:
                self._client = StorageToClient(visitor_token=visitor_token)
            else:
                self._client = StorageToClient()
                self._store.set_visitor_token(self._client._visitor_token)
        return self._client

    def _js(self, js_code):
        if self._window:
            self._window.evaluate_js(js_code)

    # ── Auth ──

    def get_auth_mode(self):
        client = self._ensure_client()
        if client._bearer_token:
            try:
                user = client.get_user()
                return {"mode": "token", "username": user.name, "is_premium": user.is_premium}
            except Exception:
                return {"mode": "token", "username": None, "is_premium": False}
        return {"mode": "anonymous"}

    def set_token(self, token):
        try:
            from api.client import StorageToClient
            client = StorageToClient(token=token)
            user = client.get_user()
            self._client = client
            self._store.set_bearer_token(token)
            return {"ok": True, "username": user.name, "is_premium": user.is_premium}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def clear_token(self):
        from api.client import StorageToClient
        visitor_token = self._store.get_visitor_token()
        if visitor_token:
            self._client = StorageToClient(visitor_token=visitor_token)
        else:
            self._client = StorageToClient()
            self._store.set_visitor_token(self._client._visitor_token)
        self._store.set_bearer_token(None)
        return {"ok": True}

    # ── Quota ──

    def get_quota(self):
        client = self._ensure_client()
        try:
            bw = client.get_bandwidth_status()
            return {
                "authenticated": bw.authenticated,
                "limit_gb": bw.limit_gb,
                "used_gb": bw.used_gb,
                "remaining_gb": bw.remaining_gb,
                "window_hours": bw.window_hours,
            }
        except Exception:
            return {"authenticated": False, "limit_gb": 0, "used_gb": 0, "remaining_gb": 0, "window_hours": 24}

    # ── Settings ──

    def get_settings(self):
        cfg = self._store.get_config()
        return {
            "download_mode": cfg.get("download_mode", "browser"),
            "idm_path": cfg.get("idm_path", ""),
            "default_expiry_days": cfg.get("default_expiry_days", 3),
            "default_keepalive_days": cfg.get("default_keepalive_days", 7),
            "keepalive_threshold": cfg.get("keepalive_threshold", 2),
            "keepalive_check_interval": cfg.get("keepalive_check_interval", 60),
            "keepalive_autostart": cfg.get("keepalive_autostart", False),
            "file_mode": cfg.get("file_mode", "merge"),
        }

    def save_settings(self, settings):
        cfg = self._store.get_config()
        cfg.update({
            "download_mode": settings.get("download_mode", "browser"),
            "idm_path": settings.get("idm_path", ""),
            "default_expiry_days": settings.get("default_expiry_days", 3),
            "default_keepalive_days": settings.get("default_keepalive_days", 7),
            "keepalive_threshold": settings.get("keepalive_threshold", 2),
            "keepalive_check_interval": settings.get("keepalive_check_interval", 60),
            "keepalive_autostart": settings.get("keepalive_autostart", False),
            "file_mode": settings.get("file_mode", "merge"),
        })
        self._store.set_config(cfg)
        return {"ok": True}

    def detect_idm_path(self):
        import os
        paths = [
            r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe",
            r"C:\Program Files\Internet Download Manager\IDMan.exe",
        ]
        for p in paths:
            if os.path.isfile(p):
                return {"path": p}
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\DownloadManager")
            path, _ = winreg.QueryValueKey(key, "ExePath")
            if os.path.isfile(path):
                return {"path": path}
        except Exception:
            pass
        return {"path": None}

    def browse_file(self, title="选择文件"):
        if self._window:
            result = self._window.create_file_dialog()
            if result:
                return {"path": result[0]}
        return {"path": None}

    # ── Files ──

    def list_files(self, keyword=""):
        from api.client import StorageToClient
        cfg = self._store.get_config() if self._store else {}
        file_mode = cfg.get("file_mode", "merge")
        client = self._ensure_client()

        def fetch_files(c):
            try:
                return c.list_files()
            except Exception:
                return []

        def format_files(files_list, source=""):
            result = []
            for f in files_list:
                result.append({
                    "id": f.id,
                    "filename": f.filename,
                    "url": f.url,
                    "size": f.size,
                    "human_size": self._human_size(f.size),
                    "expires_at": f.expires_at[:10] if f.expires_at else "",
                    "is_collection": f.is_collection,
                    "password_protected": f.password_protected,
                    "source": source,
                })
            return result

        try:
            if file_mode == "merge" and client._bearer_token:
                # Merge: fetch both visitor and account files
                visitor_token = self._store.get_visitor_token()
                anon_client = StorageToClient(visitor_token=visitor_token) if visitor_token else StorageToClient()
                anon_files = fetch_files(anon_client)
                cloud_files = fetch_files(client)
                seen_ids = set()
                merged = []
                for f, src in [(x, "local") for x in anon_files] + [(x, "cloud") for x in cloud_files]:
                    if f.id not in seen_ids:
                        seen_ids.add(f.id)
                        merged.append((f, src))
                result = format_files([x[0] for x in merged], "")
                # Set source on each item
                for i, (_, src) in enumerate(merged):
                    result[i]["source"] = src
            elif file_mode == "local":
                # Local only: use visitor token
                visitor_token = self._store.get_visitor_token()
                anon_client = StorageToClient(visitor_token=visitor_token) if visitor_token else StorageToClient()
                result = format_files(fetch_files(anon_client), "local")
            else:
                # Cloud only (or merge without token): use current client
                result = format_files(fetch_files(client), "cloud")

            if keyword:
                kw = keyword.lower()
                result = [f for f in result if kw in f["filename"].lower()]
            return {"files": result}
        except Exception as e:
            return {"files": [], "error": str(e)}

    def _client_for_file(self, file_id):
        """Get the correct client for a file - try current client first, fallback to visitor token."""
        from api.client import StorageToClient
        client = self._ensure_client()
        # Test if current client can access the file
        try:
            client.list_files()
            return client
        except Exception:
            pass
        # Fallback to visitor token
        visitor_token = self._store.get_visitor_token() if self._store else None
        if visitor_token:
            return StorageToClient(visitor_token=visitor_token)
        return client

    def delete_files(self, file_ids):
        from api.client import StorageToClient
        client = self._ensure_client()
        # Also prepare visitor token client for local files
        visitor_token = self._store.get_visitor_token() if self._store else None
        anon_client = StorageToClient(visitor_token=visitor_token) if visitor_token else None

        deleted = 0
        for fid in file_ids:
            try:
                client.delete_file(fid)
                deleted += 1
            except Exception:
                # Try with visitor token for local files
                if anon_client:
                    try:
                        anon_client.delete_file(fid)
                        deleted += 1
                    except Exception:
                        pass
        return {"ok": True, "deleted": deleted}

    def get_file_url(self, file_id):
        return {"url": "https://storage.to/" + file_id}

    def get_collection_url(self, collection_id):
        return {"url": "https://storage.to/c/" + collection_id}

    def get_download_url(self, file_id):
        client = self._ensure_client()
        try:
            url = client.get_download_url(file_id)
            if url:
                return {"ok": True, "url": url}
            return {"ok": False, "error": "无法获取下载链接"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_qrcode(self, url):
        import base64
        try:
            import qrcode
            from io import BytesIO
            img = qrcode.make(url)
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            return {"ok": True, "image": "data:image/png;base64," + b64}
        except ImportError:
            return {"ok": False, "error": "未安装 qrcode 库"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_file_expiry(self, file_id, days):
        client = self._ensure_client()
        try:
            new_expires = client.set_file_expiry(file_id, days)
            return {"ok": True, "new_expires": new_expires[:10] if new_expires else ""}
        except Exception:
            # Try with visitor token for local files
            visitor_token = self._store.get_visitor_token() if self._store else None
            if visitor_token:
                from api.client import StorageToClient
                try:
                    anon = StorageToClient(visitor_token=visitor_token)
                    new_expires = anon.set_file_expiry(file_id, days)
                    return {"ok": True, "new_expires": new_expires[:10] if new_expires else ""}
                except Exception as e2:
                    return {"ok": False, "error": str(e2)}
            return {"ok": False, "error": "操作失败"}

    def set_file_password(self, file_id, password):
        client = self._ensure_client()
        try:
            if password:
                client.set_file_password(file_id, password)
            else:
                client.remove_file_password(file_id)
            return {"ok": True}
        except Exception:
            visitor_token = self._store.get_visitor_token() if self._store else None
            if visitor_token:
                from api.client import StorageToClient
                try:
                    anon = StorageToClient(visitor_token=visitor_token)
                    if password:
                        anon.set_file_password(file_id, password)
                    else:
                        anon.remove_file_password(file_id)
                    return {"ok": True}
                except Exception as e2:
                    return {"ok": False, "error": str(e2)}
            return {"ok": False, "error": "操作失败"}

    def set_max_downloads(self, file_id, count):
        client = self._ensure_client()
        try:
            client.set_file_max_downloads(file_id, count)
            return {"ok": True}
        except Exception:
            visitor_token = self._store.get_visitor_token() if self._store else None
            if visitor_token:
                from api.client import StorageToClient
                try:
                    anon = StorageToClient(visitor_token=visitor_token)
                    anon.set_file_max_downloads(file_id, count)
                    return {"ok": True}
                except Exception as e2:
                    return {"ok": False, "error": str(e2)}
            return {"ok": False, "error": "操作失败"}

    # ── Upload ──

    def upload_file(self, file_path, collection_id=None, expiry_days=None):
        import os
        if not file_path:
            return {"ok": False, "error": "未选择文件"}
        from core.uploader import UploadEngine
        client = self._ensure_client()
        engine = UploadEngine(client)
        filename = os.path.basename(file_path)

        with self._upload_lock:
            self._upload_progress[filename] = {"percent": 0, "speed": "", "eta": "", "done": False, "result": None}

        def on_progress(pct, speed, eta):
            speed_str = str(round(speed, 1)) + " MB/s" if speed > 0 else ""
            eta_str = str(int(eta)) + "s" if eta > 0 else ""
            with self._upload_lock:
                self._upload_progress[filename] = {
                    "percent": pct, "speed": speed_str, "eta": eta_str,
                    "done": False, "result": None
                }

        def do_upload():
            try:
                confirm = engine.upload_file_full(file_path, collection_id=collection_id, on_progress=on_progress)
                # Store owner_token for keepalive
                if confirm.owner_token and self._store:
                    self._store.add_owner_token(confirm.file.id, confirm.owner_token)
                with self._upload_lock:
                    self._upload_progress[filename] = {
                        "percent": 100, "speed": "", "eta": "",
                        "done": True, "result": {"ok": True, "file_id": confirm.file.id, "url": confirm.file.url}
                    }
            except Exception as e:
                with self._upload_lock:
                    self._upload_progress[filename] = {
                        "percent": 0, "speed": "", "eta": "",
                        "done": True, "result": {"ok": False, "error": str(e)}
                    }

        t = threading.Thread(target=do_upload, daemon=True)
        t.start()
        return {"ok": True, "pending": True, "filename": filename}

    def get_upload_progress(self):
        with self._upload_lock:
            return dict(self._upload_progress)

    def browse_files(self, title="选择文件"):
        if self._window:
            result = self._window.create_file_dialog(allow_multiple=True)
            if result:
                return {"paths": list(result)}
        return {"paths": []}

    # ── Collections ──

    def list_collections(self):
        client = self._ensure_client()
        try:
            files = client.list_files()
            collections = []
            for f in files:
                if f.is_collection:
                    collections.append({
                        "id": f.id,
                        "filename": f.filename,
                        "url": f.url,
                        "expires_at": f.expires_at[:10] if f.expires_at else "",
                    })
            return {"collections": collections}
        except Exception as e:
            return {"collections": [], "error": str(e)}

    def create_collection(self, name=""):
        client = self._ensure_client()
        try:
            coll = client.create_collection(expected_file_count=0)
            return {"ok": True, "collection_id": coll.id, "url": coll.url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_collection(self, collection_id):
        client = self._ensure_client()
        try:
            client.delete_collection(collection_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _human_size(size):
        if size < 1024:
            return str(size) + " B"
        if size < 1024 * 1024:
            return str(round(size / 1024, 1)) + " KB"
        if size < 1024 * 1024 * 1024:
            return str(round(size / 1024 / 1024, 1)) + " MB"
        return str(round(size / 1024 / 1024 / 1024, 2)) + " GB"

    # ── Keepalive ──

    def keepalive_list(self):
        client = self._ensure_client()
        files_list = self._store.get_keepalive_files()
        result = []
        try:
            cloud_files = client.list_files()
            cloud_map = {f.id: f for f in cloud_files}
        except Exception:
            cloud_map = {}

        now = datetime.now(timezone.utc)
        for entry in files_list:
            file_id = entry["file_id"]
            cloud = cloud_map.get(file_id)
            filename = cloud.filename if cloud else file_id
            size = cloud.size if cloud else 0
            expires_at = cloud.expires_at[:10] if cloud and cloud.expires_at else "未知"

            remaining_days = "-"
            if cloud and cloud.expires_at:
                try:
                    expires_dt = datetime.fromisoformat(cloud.expires_at.replace("Z", "+00:00"))
                    remaining = (expires_dt - now).total_seconds() / 86400
                    remaining_days = str(round(remaining, 1))
                except Exception:
                    pass

            result.append({
                "file_id": file_id,
                "filename": filename,
                "size": ApiBridge._human_size(size),
                "expires_at": expires_at,
                "remaining_days": remaining_days,
                "target_days": entry.get("days", 7),
                "status": entry.get("status", "pending"),
            })
        return {"files": result}

    def keepalive_add(self, file_id, owner_token, target_days=7):
        if not owner_token:
            owner_token = self._store.get_owner_token(file_id) or ""
        added = self._store.add_keepalive(file_id, owner_token, days=target_days)
        if not added:
            return {"ok": False, "error": "此文件已在守护列表中"}
        return {"ok": True}

    def keepalive_remove(self, file_id):
        self._store.remove_keepalive(file_id)
        return {"ok": True}

    def keepalive_start(self):
        client = self._ensure_client()
        from core.keeper import KeepAliveDaemon
        self._daemon = KeepAliveDaemon(client, self._store)
        cfg = self._store.get_config()
        self._daemon.set_threshold(cfg.get("keepalive_threshold", 2))
        check_interval_min = cfg.get("keepalive_check_interval", 60)
        self._daemon.set_interval(check_interval_min * 60)

        def on_log(msg):
            now = datetime.now().strftime("%H:%M")
            self._js("window.onKeepaliveLog('[" + now + "] " + esc_js(msg) + "')")

        def on_status(file_id, status):
            self._js("window.onKeepaliveStatus('" + esc_js(file_id) + "', '" + status + "')")

        self._daemon.set_callbacks(on_log, on_status)
        self._daemon.start_daemon()
        return {"ok": True}

    def keepalive_stop(self):
        if hasattr(self, '_daemon'):
            self._daemon.stop_daemon()
        return {"ok": True}

    def keepalive_check_now(self):
        if hasattr(self, '_daemon') and self._daemon._running:
            import threading
            def do_check():
                self._daemon._check_all()
            threading.Thread(target=do_check, daemon=True).start()
            return {"ok": True}
        return {"ok": False, "error": "守护未运行"}


def esc_js(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
