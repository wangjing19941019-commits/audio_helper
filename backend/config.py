from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"
    backend_port: int = 8003

    bailian_api_key: str = ""
    bailian_asr_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    bailian_asr_model: str = "qwen3-asr-flash"
    bailian_tts_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )
    bailian_tts_model: str = "qwen3-tts-flash"
    bailian_tts_voice: str = "Cherry"

    deepseek_api_key: str = ""
    deepseek_url: str = "https://api.deepseek.com/chat/completions"
    deepseek_model: str = "deepseek-v4-flash"

    amap_api_key: str = ""

    storage_dir: str = str(BACKEND_ROOT / "storage")
    max_upload_bytes: int = 5 * 1024 * 1024
    min_duration_s: float = 1.0
    max_duration_s: float = 60.0
    audio_ttl_hours: int = 24
    ffprobe_timeout_s: float = 3.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
