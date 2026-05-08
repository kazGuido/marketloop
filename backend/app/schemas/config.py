from pydantic import BaseModel, Field, field_validator

from app.models.enums import OperationMode


class SystemConfigBase(BaseModel):
    operation_mode: OperationMode = OperationMode.SIGNAL_ONLY
    asset_pool: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL"])
    risk_per_trade: float = Field(default=1.5, ge=0.01, le=25)

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
