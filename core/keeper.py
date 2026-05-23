import time
from datetime import datetime, timezone
from api.client import StorageToClient
from core.store import Store


class KeepAliveDaemon:
    def __init__(self, client: StorageToClient, store: Store):
        self.client = client
        self.store = store
        self._running = False
        self._thread = None
        self._log_callback = None
        self._status_callback = None
        self._threshold_days = 2
        self._check_interval = 3600  # seconds, default 1 hour

    def set_callbacks(self, log_cb, status_cb):
        self._log_callback = log_cb
        self._status_callback = status_cb

    def set_threshold(self, days):
        self._threshold_days = days

    def set_interval(self, seconds):
        self._check_interval = max(60, seconds)

    def start_daemon(self):
        if self._running:
            return
        import threading
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_daemon(self):
        self._running = False

    def _log(self, msg):
        if self._log_callback:
            self._log_callback(msg)

    def _status(self, file_id, status):
        if self._status_callback:
            self._status_callback(file_id, status)

    def _run(self):
        self._log("守护线程启动 (检测间隔: " + str(self._check_interval // 60) + " 分钟)")
        while self._running:
            self._check_all()
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_all(self):
        files = self.store.get_keepalive_files()
        now = datetime.now(timezone.utc)
        for entry in files:
            if not self._running:
                break
            self._check_and_renew(entry, now)

    def _check_and_renew(self, entry, now):
        file_id = entry["file_id"]
        owner_token = entry.get("owner_token", "")
        target_days = entry.get("days", 7)

        try:
            files = self.client.list_files()
            actual = None
            for f in files:
                if f.id == file_id:
                    actual = f
                    break

            if actual is None:
                self._log(file_id + ": 文件未找到，跳过")
                return

            if not actual.expires_at:
                self._log(file_id + ": 无过期时间，跳过")
                return

            expires_dt = datetime.fromisoformat(actual.expires_at.replace("Z", "+00:00"))
            remaining = (expires_dt - now).total_seconds() / 86400

            self._log(file_id + " (" + actual.filename + "): 剩余 " + str(round(remaining, 1)) + " 天")

            if remaining > self._threshold_days:
                self._status(file_id, "ok")
                return

            self._log(file_id + ": 剩余 ≤ " + str(self._threshold_days) + " 天，开始续命...")
            self._do_renew(file_id, owner_token, target_days)

        except Exception as e:
            self._log(file_id + ": 检查失败 — " + str(e))
            self._status(file_id, "error")

    def _do_renew(self, file_id, owner_token, days):
        last_err = None
        for attempt in range(1, 4):
            try:
                # Try owner_token first, fall back to regular token auth
                if owner_token:
                    new_expires = self.client.set_file_expiry_owner(file_id, owner_token, days)
                else:
                    new_expires = self.client.set_file_expiry(file_id, days)
                now_str = datetime.now(timezone.utc).isoformat()
                self.store.update_keepalive_status(file_id, now_str, "ok")
                self._log(file_id + ": 续命成功，新过期: " + str(new_expires))
                self._status(file_id, "ok")
                return
            except Exception as e:
                last_err = e
                self._log(file_id + ": 第" + str(attempt) + "次续命失败 — " + str(e))
                if attempt < 3:
                    time.sleep(2)
        self.store.update_keepalive_status(file_id, None, "error")
        self._log(file_id + ": 续命失败(已重试3次) — " + str(last_err))
        self._status(file_id, "error")
