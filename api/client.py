import os
import re
import uuid
import requests
from api.models import (
    FileInfo, CloudFileInfo, InitUploadResult, ConfirmResult,
    ReserveResult, FileStatus, CollectionInfo, CollectionStatus,
    BandwidthStatus, UserInfo, PartETag, BatchInitResult,
)
from api.exceptions import (
    StorageToError, AuthError, RateLimitError,
    QuotaExceededError, NotFoundError,
)


class StorageToClient:
    def __init__(self, token=None, visitor_token=None,
                 base_url="https://storage.to/api"):
        self._base_url = base_url
        self._session = requests.Session()
        self._session.timeout = 30

        if token:
            self._bearer_token = token
            self._visitor_token = None
        else:
            env_token = os.getenv("STCLIO_TOKEN")
            if env_token:
                self._bearer_token = env_token
                self._visitor_token = None
            else:
                self._bearer_token = None
                self._visitor_token = visitor_token or f"stcli-{uuid.uuid4().hex[:16]}"

    # ── HTTP helpers ──

    def _headers(self, content_type="application/json"):
        h = {"Accept": "application/json"}
        if self._bearer_token:
            h["Authorization"] = f"Bearer {self._bearer_token}"
        elif self._visitor_token:
            h["X-Visitor-Token"] = self._visitor_token
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _post(self, path, data=None):
        resp = self._session.post(
            f"{self._base_url}{path}",
            headers=self._headers(),
            json=data,
        )
        return self._check(resp)

    def _get(self, path, headers=None):
        h = self._headers(content_type=None)
        if headers:
            h.update(headers)
        resp = self._session.get(f"{self._base_url}{path}", headers=h)
        return self._check(resp)

    def _delete(self, path):
        resp = self._session.delete(
            f"{self._base_url}{path}",
            headers=self._headers(content_type=None),
        )
        return self._check(resp)

    def raw_put(self, url, data, headers=None):
        return self._session.put(url, data=data, headers=headers or {})

    def raw_get(self, url, **kwargs):
        h = kwargs.pop("headers", {})
        if self._bearer_token:
            h["Authorization"] = f"Bearer {self._bearer_token}"
        elif self._visitor_token:
            h["X-Visitor-Token"] = self._visitor_token
        return self._session.get(url, headers=h, **kwargs)

    def _check(self, resp):
        if resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 60))
            body = resp.json() if resp.content else {}
            msg = body.get("error", body.get("message", "Rate limited"))
            raise RateLimitError(msg, retry_after=retry)
        if resp.status_code in (401, 403):
            body = resp.json() if resp.content else {}
            raise AuthError(body.get("error", "Unauthorized"))
        if resp.status_code == 404:
            raise NotFoundError("Resource not found")
        if resp.status_code == 422:
            body = resp.json() if resp.content else {}
            raise QuotaExceededError(body.get("error", "Quota exceeded"))
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            msg = body.get("error", body.get("message", f"HTTP {resp.status_code}"))
            raise StorageToError(msg)
        if resp.content:
            try:
                return resp.json()
            except Exception:
                return {}
        return {}

    # ── Upload ──

    def init_upload(self, filename, content_type, size):
        data = self._post("/upload/init", {
            "filename": filename,
            "content_type": content_type,
            "size": size,
        })
        return InitUploadResult(
            type=data["type"],
            upload_url=data.get("upload_url", ""),
            r2_key=data["r2_key"],
            headers=data.get("headers", {}),
            upload_id=data.get("upload_id", ""),
            part_size=data.get("part_size", 0),
            total_parts=data.get("total_parts", 0),
            initial_urls=data.get("initial_urls", {}),
            owner_token=data.get("owner_token", ""),
        )

    def upload_part_urls(self, upload_id, part_numbers):
        data = self._post("/upload/parts", {
            "upload_id": upload_id,
            "part_numbers": part_numbers,
        })
        urls = {}
        part_urls = data.get("part_urls", data.get("urls", []))
        if isinstance(part_urls, dict):
            for k, v in part_urls.items():
                urls[int(k)] = v
        else:
            for item in part_urls:
                if isinstance(item, dict):
                    urls[item["partNumber"]] = item["url"]
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    urls[item[0]] = item[1]
        return urls

    def complete_multipart(self, upload_id, parts):
        self._post("/upload/complete-multipart", {
            "upload_id": upload_id,
            "parts": [{"partNumber": p.part_number, "etag": p.etag} for p in parts],
        })

    def abort_upload(self, upload_id):
        self._post("/upload/abort", {"upload_id": upload_id})

    def confirm_upload(self, filename, size, content_type, r2_key,
                       collection_id=None, crc32=None, file_id=None):
        payload = {
            "filename": filename,
            "size": size,
            "content_type": content_type,
            "r2_key": r2_key,
        }
        if collection_id:
            payload["collection_id"] = collection_id
        if crc32 is not None:
            payload["crc32"] = crc32
        if file_id:
            payload["file_id"] = file_id
        data = self._post("/upload/confirm", payload)
        file_data = data.get("file", data)
        file_info = FileInfo(
            id=file_data["id"],
            url=file_data["url"],
            raw_url=file_data.get("raw_url", ""),
            filename=file_data.get("filename", filename),
            size=file_data.get("size", size),
            human_size=file_data.get("human_size", ""),
            expires_at=file_data.get("expires_at", ""),
        )
        return ConfirmResult(file=file_info, owner_token=data.get("owner_token", ""))

    def reserve_file(self, filename=None, content_type=None):
        payload = {}
        if filename:
            payload["filename"] = filename
        if content_type:
            payload["content_type"] = content_type
        data = self._post("/file/reserve", payload or None)
        file_data = data["file"]
        file_info = FileInfo(
            id=file_data["id"],
            url=file_data["url"],
            raw_url=file_data.get("raw_url", ""),
            filename=file_data.get("filename", filename or "Pending"),
            size=file_data.get("size", 0),
            human_size=file_data.get("human_size", ""),
            expires_at=file_data.get("expires_at", ""),
        )
        return ReserveResult(file=file_info, owner_token=data.get("owner_token", ""))

    # ── Batch Upload ──

    def init_batch(self, files):
        data = self._post("/upload/init-batch", {"files": files})
        results = {}
        for name, info in data.get("results", {}).items():
            results[name] = BatchInitResult(
                type=info.get("type", ""),
                upload_url=info.get("upload_url", ""),
                r2_key=info.get("r2_key", ""),
                upload_id=info.get("upload_id", ""),
                part_size=info.get("part_size", 0),
                total_parts=info.get("total_parts", 0),
                initial_urls=info.get("initial_urls", {}),
            )
        return results

    def confirm_batch(self, files, collection_id=None):
        payload = {"files": files}
        if collection_id:
            payload["collection_id"] = collection_id
        data = self._post("/upload/confirm-batch", payload)
        results = {}
        for name, info in data.get("results", {}).items():
            if info.get("success") and info.get("file"):
                fd = info["file"]
                results[name] = FileInfo(
                    id=fd["id"], url=fd["url"], raw_url=fd.get("raw_url", ""),
                    filename=fd.get("filename", name), size=fd.get("size", 0),
                    human_size=fd.get("human_size", ""), expires_at=fd.get("expires_at", ""),
                )
        return results

    # ── File Management ──

    def get_file_status(self, file_id):
        data = self._get(f"/file/{file_id}/status")
        return FileStatus(pending=data.get("pending", False))

    def delete_file(self, file_id):
        self._delete(f"/file/{file_id}")

    def set_file_password(self, file_id, password):
        self._post(f"/file/{file_id}/password", {"password": password})

    def remove_file_password(self, file_id):
        self._delete(f"/file/{file_id}/password")

    def verify_file_password(self, file_id, password):
        try:
            self._post(f"/file/{file_id}/verify-password", {"password": password})
            return True
        except AuthError:
            return False

    def set_file_expiry(self, file_id, days):
        data = self._post(f"/file/{file_id}/expiry", {"days": days})
        return data.get("expires_at", "")

    def set_file_expiry_owner(self, file_id, owner_token, days):
        resp = self._session.post(
            f"{self._base_url}/file/{file_id}/expiry",
            headers={"Content-Type": "application/json", "Authorization": f"Owner {owner_token}"},
            json={"days": days},
        )
        data = self._check(resp)
        return data.get("expires_at", "")

    def set_file_max_downloads(self, file_id, max_downloads):
        self._post(f"/file/{file_id}/max-downloads", {"max_downloads": max_downloads})

    def upload_thumbnail(self, file_id, image_path):
        with open(image_path, "rb") as f:
            h = {}
            if self._bearer_token:
                h["Authorization"] = f"Bearer {self._bearer_token}"
            elif self._visitor_token:
                h["X-Visitor-Token"] = self._visitor_token
            resp = self._session.post(
                f"{self._base_url}/file/{file_id}/thumbnail",
                headers=h, files={"thumbnail": f},
            )
            result = self._check(resp)
            return result.get("thumbnail_url", "")

    # ── Cloud File List ──

    def list_files(self):
        data = self._get("/files")
        files = []
        for item in data.get("files", []):
            files.append(CloudFileInfo(
                id=item["id"], filename=item["filename"], url=item["url"],
                size=item["size"], uploaded_at=item.get("uploaded_at", ""),
                is_collection=item.get("is_collection", False),
                password_protected=item.get("password_protected", False),
                burn_after_reading=item.get("burn_after_reading", False),
                expires_at=item.get("expires_at", ""),
                thumbnail_url=item.get("thumbnail_url"),
            ))
        return files

    def get_download_url(self, file_id):
        resp = self._session.get(
            f"https://storage.to/{file_id}",
            headers={"Accept": "text/html"},
        )
        match = re.search(
            r"/download\?expires=(\d+)&amp;signature=([a-f0-9]+)", resp.text
        )
        if not match:
            return None
        expires, signature = match.group(1), match.group(2)
        dl_url = f"https://storage.to/{file_id}/download?expires={expires}&signature={signature}"
        # Follow redirect to get CDN URL
        r = self._session.get(dl_url, allow_redirects=False)
        if r.status_code == 302:
            return r.headers.get("Location", dl_url)
        return dl_url

    def get_download_count(self, file_id):
        resp = self._session.get(
            f"https://storage.to/{file_id}",
            headers={"Accept": "text/html"},
        )
        match = re.search(
            r"/download\?expires=(\d+)&amp;signature=([a-f0-9]+)", resp.text
        )
        if not match:
            return 0
        expires, signature = match.group(1), match.group(2)
        h = {"Accept": "application/json"}
        if self._bearer_token:
            h["Authorization"] = f"Bearer {self._bearer_token}"
        r = self._session.get(
            f"https://storage.to/{file_id}/download?expires={expires}&signature={signature}",
            headers=h,
        )
        if r.status_code == 200:
            return r.json().get("downloads", 0)
        return 0

    # ── Collection ──

    def create_collection(self, expected_file_count=0):
        data = self._post("/collection", {"expected_file_count": max(1, expected_file_count)})
        c = data["collection"]
        return CollectionInfo(id=c["id"], url=c["url"], expires_at=c["expires_at"])

    def get_collection_status(self, coll_id):
        data = self._get(f"/collection/{coll_id}/status")
        files = []
        for item in data.get("files", []):
            files.append(FileInfo(
                id=item["id"], url=item.get("url", ""),
                raw_url=item.get("raw_url", ""),
                filename=item.get("filename", ""),
                size=item.get("size", 0),
                human_size=item.get("human_size", ""),
                expires_at=item.get("expires_at", ""),
            ))
        return CollectionStatus(
            files=files,
            is_uploading=data.get("is_uploading", False),
            file_count=data.get("file_count", 0),
            expected_file_count=data.get("expected_file_count", 0),
            total_size=data.get("total_size", 0),
            human_total_size=data.get("human_total_size", "0 B"),
        )

    def mark_collection_ready(self, coll_id):
        self._post(f"/collection/{coll_id}/ready", {})

    def delete_collection(self, coll_id):
        self._delete(f"/collection/{coll_id}")

    def set_collection_password(self, coll_id, password):
        self._post(f"/collection/{coll_id}/password", {"password": password})

    def remove_collection_password(self, coll_id):
        self._delete(f"/collection/{coll_id}/password")

    def verify_collection_password(self, coll_id, password):
        try:
            self._post(f"/collection/{coll_id}/verify-password", {"password": password})
            return True
        except AuthError:
            return False

    def set_collection_expiry(self, coll_id, days):
        data = self._post(f"/collection/{coll_id}/expiry", {"days": days})
        return data.get("expires_at", "")

    def set_collection_max_downloads(self, coll_id, max_downloads):
        self._post(f"/collection/{coll_id}/max-downloads", {"max_downloads": max_downloads})

    # ── User & Quota ──

    def get_user(self):
        data = self._get("/user")
        return UserInfo(
            id=data["id"], name=data["name"],
            email=data["email"], is_premium=data.get("is_premium", False),
        )

    def logout(self):
        self._post("/auth/logout")

    def get_bandwidth_status(self):
        data = self._get("/bandwidth/status")
        return BandwidthStatus(
            authenticated=data.get("authenticated", False),
            limit_gb=data.get("limit_gb", 0),
            used_gb=data.get("used_gb", 0),
            remaining_gb=data.get("remaining_gb", 0),
            window_hours=data.get("window_hours", 24),
        )

    def get_health(self):
        return self._get("/health")

    # ── ShareX ──

    def sharex_upload(self, filepath):
        h = {}
        if self._bearer_token:
            h["Authorization"] = f"Bearer {self._bearer_token}"
        with open(filepath, "rb") as f:
            resp = self._session.post(
                f"{self._base_url}/sharex/upload",
                headers=h,
                files={"file": (os.path.basename(filepath), f)},
            )
            data = self._check(resp)
            return FileInfo(
                id=data.get("id", ""), url=data.get("url", ""),
                raw_url=data.get("raw_url", ""),
                filename=data.get("filename", os.path.basename(filepath)),
                size=0, human_size="",
                expires_at=data.get("expires_at", ""),
            )
