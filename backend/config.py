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
    max_asr_base64_bytes: int = 10 * 1024 * 1024
    asr_upstream_timeout_s: float = 20.0
    extract_upstream_timeout_s: float = 15.0
    extract_max_tokens: int = 512

    amap_geocode_url: str = "https://restapi.amap.com/v3/geocode/geo"
    amap_around_url: str = "https://restapi.amap.com/v3/place/around"
    amap_upstream_timeout_s: float = 5.0
    search_total_timeout_s: float = 18.0
    geo_merge_max_m: float = 80.0
    poi_first_radius_m: int = 2000
    poi_expand_radius_m: int = 5000
    poi_max_results: int = 3
    poi_fetch_size: int = 20

    public_base_url: str = "http://localhost:8003"
    reply_upstream_timeout_s: float = 12.0
    reply_max_tokens: int = 256
    tts_upstream_timeout_s: float = 10.0
    tts_download_timeout_s: float = 8.0
    finalize_total_timeout_s: float = 32.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
