from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.settings import get_settings
from src.infrastructure.db.repositories import UserRepository
from src.shared.exceptions import AppError
from src.shared.schemas.auth import AuthResponse, LoginRequest, RegisterRequest

try:
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover
    import base64
    import hashlib
    import hmac
    import json

    class JWTError(Exception):
        pass

    class _SimpleJwt:
        @staticmethod
        def encode(payload: dict, secret: str, algorithm: str = "HS256") -> str:
            if algorithm != "HS256":
                raise JWTError("Unsupported algorithm")

            header = {"alg": algorithm, "typ": "JWT"}
            signing_input = b".".join(
                _b64encode(part)
                for part in (
                    json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                    json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                )
            )
            signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            return b".".join([signing_input, _b64encode(signature)]).decode("utf-8")

        @staticmethod
        def decode(token: str, secret: str, algorithms: list[str]) -> dict:
            if "HS256" not in algorithms:
                raise JWTError("Unsupported algorithm")
            parts = token.split(".")
            if len(parts) != 3:
                raise JWTError("Invalid token")

            signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
            signature = _b64decode(parts[2])
            expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise JWTError("Invalid signature")
            return json.loads(_b64decode(parts[1]).decode("utf-8"))

    def _b64encode(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    def _b64decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(f"{data}{padding}".encode("utf-8"))

    jwt = _SimpleJwt()

try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover
    import base64
    import hashlib
    import hmac
    import os

    class CryptContext:  # type: ignore[override]
        def __init__(self, schemes: list[str], deprecated: str = "auto") -> None:
            _ = schemes, deprecated
            self._iterations = 390_000

        def hash(self, password: str) -> str:
            salt = os.urandom(16)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self._iterations)
            encoded_salt = base64.urlsafe_b64encode(salt).decode("utf-8")
            encoded_digest = base64.urlsafe_b64encode(digest).decode("utf-8")
            return f"pbkdf2_sha256${self._iterations}${encoded_salt}${encoded_digest}"

        def verify(self, password: str, hashed: str) -> bool:
            if not hashed.startswith("pbkdf2_sha256$"):
                return False

            try:
                _, iterations, encoded_salt, encoded_digest = hashed.split("$", 3)
                salt = base64.urlsafe_b64decode(encoded_salt.encode("utf-8"))
                expected_digest = base64.urlsafe_b64decode(encoded_digest.encode("utf-8"))
                candidate_digest = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt,
                    int(iterations),
                )
            except (TypeError, ValueError):
                return False

            return hmac.compare_digest(candidate_digest, expected_digest)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._settings = get_settings()

    @property
    def admin_code(self) -> str:
        return getattr(self._settings, "auth_admin_code", "letmein")

    async def register(self, request: RegisterRequest) -> AuthResponse:
        role = request.role.lower()
        if role not in {"admin", "user"}:
            raise AppError("VALIDATION_ERROR", "Invalid role", detail={"role": request.role}, status_code=422)

        if role == "admin" and request.admin_code != self.admin_code:
            raise AppError("ADMIN_CODE_REQUIRED", "Admin code required", status_code=403)

        existing = await self._users.get_by_username(username=request.username)
        if existing is not None:
            raise AppError("RESOURCE_CONFLICT", "Username already exists", status_code=409)

        password_hash = pwd_context.hash(request.password)
        user = await self._users.create_user(username=request.username, password_hash=password_hash, role=role)
        await self._session.commit()
        return self._build_auth_response(username=user.username, role=user.role)

    async def login(self, request: LoginRequest) -> AuthResponse:
        user = await self._users.get_by_username(username=request.username)
        if user is None or not pwd_context.verify(request.password, user.password_hash):
            raise AppError("AUTH_BAD_CREDENTIALS", "Invalid username or password", status_code=401)
        return self._build_auth_response(username=user.username, role=user.role)

    def create_access_token(self, *, username: str, role: str) -> str:
        return jwt.encode(
            {"sub": username, "role": role},
            self._settings.auth_jwt_secret,
            algorithm=self._settings.auth_jwt_algorithm,
        )

    def decode_access_token(self, token: str) -> dict[str, str]:
        try:
            payload = jwt.decode(
                token,
                self._settings.auth_jwt_secret,
                algorithms=[self._settings.auth_jwt_algorithm],
            )
        except JWTError as exc:
            raise AppError("AUTH_INVALID_TOKEN", "Invalid or expired token", status_code=401) from exc

        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in {"admin", "user"}:
            raise AppError("AUTH_INVALID_TOKEN", "Invalid or expired token", status_code=401)
        return {"username": username, "role": role}

    def _build_auth_response(self, *, username: str, role: str) -> AuthResponse:
        return AuthResponse(
            access_token=self.create_access_token(username=username, role=role),
            token_type="bearer",
            username=username,
            role=role,
        )
