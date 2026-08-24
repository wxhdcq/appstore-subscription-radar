from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_STOREFRONTS = (
    "US", "CN", "HK", "TW", "JP", "KR", "GB", "DE", "FR", "IT",
    "ES", "BR", "MX", "IN", "ID", "TH", "VN", "PH", "MY", "SG",
    "AU", "CA", "AR", "TR", "NG", "EG", "ZA", "AE", "SA", "PL",
)

STOREFRONT_NAMES = {
    "US": "美国", "CN": "中国大陆", "HK": "中国香港", "TW": "中国台湾",
    "JP": "日本", "KR": "韩国", "GB": "英国", "DE": "德国", "FR": "法国",
    "IT": "意大利", "ES": "西班牙", "BR": "巴西", "MX": "墨西哥",
    "IN": "印度", "ID": "印度尼西亚", "TH": "泰国", "VN": "越南",
    "PH": "菲律宾", "MY": "马来西亚", "SG": "新加坡", "AU": "澳大利亚",
    "CA": "加拿大", "AR": "阿根廷", "TR": "土耳其", "NG": "尼日利亚",
    "EG": "埃及", "ZA": "南非", "AE": "阿联酋", "SA": "沙特阿拉伯",
    "PL": "波兰",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "App Store 全球订阅雷达"
    database_url: str = "sqlite:///./radar.db"
    admin_token: str = ""
    refresh_hour: int = 3
    refresh_minute: int = 20
    request_concurrency: int = 4
    request_timeout_seconds: float = 20
    seed_demo_apps: bool = True
    public_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

