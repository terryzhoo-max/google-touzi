import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8888",
    "http://localhost:8888",
]


def parse_origins(value: str) -> list[str]:
    origins = [item.strip() for item in value.split(",") if item.strip()]
    if not origins or "*" in origins:
        return DEFAULT_ALLOWED_ORIGINS.copy()
    return origins


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # API Keys
    TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    SERVERCHAN_SENDKEY: str = os.getenv("SERVERCHAN_SENDKEY", "")
    QQ_MAIL_USER: str = os.getenv("QQ_MAIL_USER", "")
    QQ_MAIL_PASS: str = os.getenv("QQ_MAIL_PASS", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # Quantitative Thresholds
    TNX_LOOSE_THRESH: float = 3.8
    TNX_TIGHT_THRESH: float = 4.5
    VIX_CAUTION_THRESH: float = 20.0
    VIX_PANIC_THRESH: float = 30.0
    CORR_DUAL_KILL_THRESH: float = 0.15

    # System Settings
    CACHE_TTL: int = 3600
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "240"))
    ALLOWED_ORIGINS: list[str] = parse_origins(os.getenv("ALLOWED_ORIGINS", ""))
    ALLOW_CREDENTIALS: bool = parse_bool(os.getenv("ALLOW_CREDENTIALS", "false"))

settings = Settings()
