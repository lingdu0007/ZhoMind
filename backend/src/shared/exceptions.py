class AppError(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None, status_code: int = 400):
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)


class NotImplementedErrorApp(AppError):
    def __init__(self, message: str = "Endpoint not implemented"):
        super().__init__(
            code="NOT_IMPLEMENTED",
            message=message,
            detail=None,
            status_code=501,
        )


class AuthError(AppError):
    def __init__(self, code: str = "AUTH_INVALID_TOKEN", message: str = "Invalid or expired token"):
        super().__init__(code=code, message=message, detail=None, status_code=401)
