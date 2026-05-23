import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from api.client import StorageToClient
from api.models import PartETag


class UploadEngine:
    def __init__(self, client: StorageToClient):
        self.client = client

    def upload_file(self, filepath, collection_id=None,
                    on_progress=None, on_complete=None):
        confirm = self.upload_file_full(filepath, collection_id, on_progress, on_complete)
        return confirm.file

    def upload_file_full(self, filepath, collection_id=None,
                         on_progress=None, on_complete=None):
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        content_type = self._guess_mime(filename)

        init = self.client.init_upload(filename, content_type, size)

        if init.type == "single":
            self._upload_single(init, filepath, content_type, on_progress)
        else:
            self._upload_multipart(init, filepath, content_type, size, on_progress)

        confirm = self.client.confirm_upload(
            filename, size, content_type, init.r2_key,
            collection_id=collection_id,
        )
        if on_complete:
            on_complete(confirm.file)
        return confirm

    def upload_files(self, filepaths, collection_id=None,
                     on_progress=None, on_file_complete=None):
        results = []
        for fp in filepaths:
            info = self.upload_file(fp, collection_id, on_progress, on_file_complete)
            results.append(info)
        return results

    def _upload_single(self, init, filepath, content_type, on_progress):
        put_headers = {"Content-Type": content_type}
        for k, v in init.headers.items():
            put_headers[k] = v[0] if isinstance(v, list) else v

        file_size = os.path.getsize(filepath)
        # Simulate progress for single-file uploads (no chunked callbacks)
        import threading as _threading
        progress_pct = [0]
        stop_event = _threading.Event()

        def simulate_progress():
            while not stop_event.is_set():
                if progress_pct[0] < 90:
                    progress_pct[0] += max(1, int((90 - progress_pct[0]) * 0.1))
                elapsed = time.time() - start
                speed = file_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
                if on_progress:
                    on_progress(min(progress_pct[0], 90), speed, 0)
                stop_event.wait(0.3)

        start = time.time()
        t = _threading.Thread(target=simulate_progress, daemon=True)
        t.start()

        try:
            with open(filepath, "rb") as f:
                data = f.read()
            resp = self.client.raw_put(init.upload_url, data, headers=put_headers)
            if not resp.ok:
                raise Exception("上传失败 (HTTP " + str(resp.status_code) + ")")
        finally:
            stop_event.set()
            t.join(timeout=1)

        elapsed = time.time() - start
        speed = file_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
        if on_progress:
            on_progress(100, speed, 0)

    def _upload_multipart(self, init, filepath, content_type, size, on_progress):
        chunk_size = init.part_size
        total_parts = init.total_parts
        uploaded_parts = []
        start_time = time.time()

        def upload_chunk(part_num, data, url):
            resp = self.client.raw_put(url, data, headers={"Content-Type": "application/octet-stream"})
            if not resp.ok:
                raise Exception("分片 " + str(part_num) + " 上传失败 (HTTP " + str(resp.status_code) + ")")
            etag = resp.headers.get("ETag", "")
            return PartETag(part_number=part_num, etag=etag)

        with open(filepath, "rb") as f:
            futures = {}
            part_urls = dict(init.initial_urls)
            next_part = 1
            completed = 0

            with ThreadPoolExecutor(max_workers=3) as pool:
                while completed < total_parts:
                    while len(futures) < 3 and next_part <= total_parts:
                        if next_part not in part_urls:
                            needed = list(range(next_part, min(next_part + 3, total_parts + 1)))
                            new_urls = self.client.upload_part_urls(init.upload_id, needed)
                            part_urls.update(new_urls)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        url = part_urls[next_part]
                        fut = pool.submit(upload_chunk, next_part, data, url)
                        futures[fut] = next_part
                        next_part += 1

                    if not futures:
                        break

                    done_futures = list(as_completed(futures.keys()))
                    for fut in done_futures:
                        part_num = futures.pop(fut)
                        part_etag = fut.result()
                        uploaded_parts.append(part_etag)
                        completed += 1
                        elapsed = time.time() - start_time
                        speed = (completed * chunk_size) / elapsed / 1024 / 1024 if elapsed > 0 else 0
                        percent = completed / total_parts * 100
                        eta = (total_parts - completed) * chunk_size / (speed * 1024 * 1024) if speed > 0 else 0
                        if on_progress:
                            on_progress(percent, speed, eta)

        uploaded_parts.sort(key=lambda p: p.part_number)
        self.client.complete_multipart(init.upload_id, uploaded_parts)

    def _guess_mime(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".txt": "text/plain", ".pdf": "application/pdf",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".zip": "application/zip", ".7z": "application/x-7z-compressed",
            ".mp4": "video/mp4", ".mp3": "audio/mpeg",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        return mime_map.get(ext, "application/octet-stream")
