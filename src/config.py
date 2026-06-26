import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    QWEN_API: str = os.getenv("QWEN_API", "")
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-plus")

    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    DEMO_REPO: str = os.getenv("DEMO_REPO", "salginci/oncall-autopilot")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    SLS_ENDPOINT: str = os.getenv("SLS_ENDPOINT", "")
    SLS_ACCESS_KEY_ID: str = os.getenv("SLS_ACCESS_KEY_ID", "")
    SLS_ACCESS_KEY_SECRET: str = os.getenv("SLS_ACCESS_KEY_SECRET", "")

    DEMO_SERVICE_URL: str = os.getenv("DEMO_SERVICE_URL", "http://localhost:3000")
    AGENT_POLL_INTERVAL: int = int(os.getenv("AGENT_POLL_INTERVAL", "5"))
    ERROR_RATE_THRESHOLD: float = float(os.getenv("ERROR_RATE_THRESHOLD", "0.10"))
    LATENCY_THRESHOLD_MS: int = int(os.getenv("LATENCY_THRESHOLD_MS", "500"))

    @property
    def is_configured(self) -> bool:
        return bool(self.QWEN_API and self.GITHUB_TOKEN)


settings = Settings()
