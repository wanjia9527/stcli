from dataclasses import dataclass


@dataclass
class FileInfo:
    id: str
    url: str
    raw_url: str
    filename: str
    size: int
    human_size: str
    expires_at: str


@dataclass
class CloudFileInfo:
    id: str
    filename: str
    url: str
    size: int
    uploaded_at: str
    is_collection: bool
    password_protected: bool
    burn_after_reading: bool
    expires_at: str
    thumbnail_url: str | None
    download_count: int | None = None


@dataclass
class InitUploadResult:
    type: str
    upload_url: str
    r2_key: str
    headers: dict
    upload_id: str
    part_size: int
    total_parts: int
    initial_urls: dict
    owner_token: str


@dataclass
class PartETag:
    part_number: int
    etag: str


@dataclass
class ConfirmResult:
    file: FileInfo
    owner_token: str


@dataclass
class BatchInitResult:
    type: str
    upload_url: str
    r2_key: str
    upload_id: str
    part_size: int
    total_parts: int
    initial_urls: dict


@dataclass
class BatchConfirmFile:
    filename: str
    size: int
    content_type: str
    r2_key: str


@dataclass
class ReserveResult:
    file: FileInfo
    owner_token: str


@dataclass
class FileStatus:
    pending: bool


@dataclass
class CollectionInfo:
    id: str
    url: str
    expires_at: str


@dataclass
class CollectionStatus:
    files: list[FileInfo]
    is_uploading: bool
    file_count: int
    expected_file_count: int
    total_size: int
    human_total_size: str


@dataclass
class BandwidthStatus:
    authenticated: bool
    limit_gb: float
    used_gb: float
    remaining_gb: float
    window_hours: int


@dataclass
class UserInfo:
    id: int
    name: str
    email: str
    is_premium: bool
