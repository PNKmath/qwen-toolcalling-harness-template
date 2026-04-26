from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class HarnessConfig:
    base_url: str = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8008/v1")
    api_key: str = os.getenv("OPENAI_API_KEY", "dummy")
    model: str = os.getenv("MODEL", "Qwen3.6-27B-UD-MLX-4bit")
    max_turns: int = int(os.getenv("MAX_TURNS", "6"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "120"))
