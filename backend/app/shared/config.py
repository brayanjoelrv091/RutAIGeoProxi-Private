"""
Configuración centralizada del monolito modular.
Lee variables de entorno (.env) y expone un singleton ``settings``.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings:
    # ── Base de datos ──────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://rutai_db_user:tRtlGpIRVZJqeznt5DXpIRnM00b9ly7v@dpg-d7nbd8dckfvc73et4mjg-a.oregon-postgres.render.com/rutai_db"
    )
    POSTGRES_DATABASE_URL: str | None = os.getenv("POSTGRES_DATABASE_URL")

    # ── JWT ────────────────────────────────────────────────────────────
    _secret_key = os.getenv("SECRET_KEY")
    if not _secret_key:
        raise ValueError("SECRET_KEY environment variable is required. Set it in your .env file.")
    SECRET_KEY: str = _secret_key
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )

    # ── Admin seed ─────────────────────────────────────────────────────
    ADMIN_EMAIL: str | None = os.getenv("ADMIN_EMAIL") or None
    ADMIN_PASSWORD: str | None = os.getenv("ADMIN_PASSWORD") or None

    # ── Debug ──────────────────────────────────────────────────────────
    DEBUG_RESET_TOKEN: bool = os.getenv("DEBUG_RESET_TOKEN", "").lower() in (
        "1",
        "true",
        "yes",
    )

    # ── CORS ───────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in (
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://localhost:4200,"
                "http://localhost:5173,http://127.0.0.1:3000,"
                "http://127.0.0.1:4200,http://127.0.0.1:5173,"
                "https://rutaigeoproxi-frontend.onrender.com",
            )
        ).split(",")
        if o.strip()
    ]

    # ── Firebase Storage (opcional) ────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str | None = (
        os.getenv("FIREBASE_CREDENTIALS_PATH") or None
    )
    FIREBASE_STORAGE_BUCKET: str | None = (
        os.getenv("FIREBASE_STORAGE_BUCKET") or None
    )

    # ── Almacenamiento local (fallback si Firebase no configurado) ─────
    UPLOAD_DIR: Path = BASE_DIR / "uploads"

    # ── IA — Clasificación de incidentes (APIs Externas) ───────────────
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    ROBOFLOW_API_KEY: str | None = os.getenv("ROBOFLOW_API_KEY")
    ROBOFLOW_MODEL: str = os.getenv("ROBOFLOW_MODEL", "rutai-vision-pro")
    ROBOFLOW_VERSION: int = int(os.getenv("ROBOFLOW_VERSION", "2"))

    # ── SMTP (Brevo) ───────────────────────────────────────────────────
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp-relay.brevo.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str | None = os.getenv("SMTP_USER") or None
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD") or None
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "si2psicologiaproy@gmail.com")

    # ── Stripe (Pagos) ─────────────────────────────────────────────────
    STRIPE_PUBLIC_KEY: str | None = os.getenv("STRIPE_PUBLIC_KEY")
    STRIPE_SECRET_KEY: str | None = os.getenv("STRIPE_SECRET_KEY")

    @property
    def firebase_enabled(self) -> bool:
        return bool(self.FIREBASE_CREDENTIALS_PATH and self.FIREBASE_STORAGE_BUCKET)


settings = Settings()
