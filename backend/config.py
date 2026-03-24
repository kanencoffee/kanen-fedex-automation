from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # FedEx REST API v1 credentials
    fedex_client_id: str
    fedex_client_secret: str
    fedex_account_number: str
    fedex_base_url: str = "https://apis.fedex.com"

    # PostgreSQL (Railway provides this as DATABASE_URL)
    database_url: str

    # Used in webhook subscription so FedEx knows where to POST
    app_base_url: str = "https://your-app.railway.app"

    # Shared secret sent by FedEx in X-FedEx-Webhook-Secret header
    fedex_webhook_secret: str = "kanen-fedex-webhook-secret"

    # Billing discrepancy alert threshold (dollars)
    billing_alert_threshold: float = 5.00

    # Optional: email alerts for discrepancies / delivery exceptions
    alert_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
