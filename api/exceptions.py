class StorageToError(Exception):
    pass


class AuthError(StorageToError):
    pass


class RateLimitError(StorageToError):
    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExceededError(StorageToError):
    pass


class NotFoundError(StorageToError):
    pass
