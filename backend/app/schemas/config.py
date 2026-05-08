from pydantic import BaseModel, Field, field_validator

from app.models.enums import OperationMode


class NotificationConfig(BaseModel):
    telegram_enabled: bool = True
    telegram_chat_id: str | None = None
    whatsapp_enabled: bool = False
    whatsapp_recipient: str | None = None
    whatsapp_bridge_url: str | None = None
    email_enabled: bool = False
    email_to: str | None = None
    email_from: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True


class SystemConfigBase(BaseModel):
    operation_mode: OperationMode = OperationMode.SIGNAL_ONLY
    asset_pool: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL"])
    risk_per_trade: float = Field(default=1.5, ge=0.01, le=25)
    notification_config: NotificationConfig = Field(default_factory=NotificationConfig)

    @field_validator("asset_pool")
    @classmethod
    def normalize_asset_pool(cls, value: list[str]) -> list[str]:
        assets = [item.strip().upper() for item in value if item and item.strip()]
        if not assets:
            raise ValueError("asset_pool cannot be empty")
        if "ALL" in assets:
            return ["ALL"]
        return sorted(set(assets))


class SystemConfigUpdate(SystemConfigBase):
    pass


class SystemConfigRead(SystemConfigBase):
    id: int

    model_config = {"from_attributes": True}
