import os
from dotenv import load_dotenv

load_dotenv()

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
    MAX_REQUESTS_PER_MINUTE: int = 60

settings = Settings()
