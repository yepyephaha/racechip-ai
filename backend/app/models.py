from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget_cny: float | None = Field(None, ge=0, le=1_000_000)
    max_power_w: float | None = Field(None, ge=0, le=100_000)
    required_interfaces: list[str] = Field(default_factory=list, max_length=10)
    logic_voltage_v: float | None = Field(None, gt=0, le=100)
    offline_required: bool = False
    banned_hardware: list[str] = Field(default_factory=list, max_length=20)
    only_existing_hardware: bool = False

    @field_validator("required_interfaces")
    @classmethod
    def normalize_interfaces(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(v.strip().upper().replace("I²C", "I2C") for v in values))
        if any(v not in {"UART", "I2C", "SPI", "USB", "CSI"} for v in normalized):
            raise ValueError("接口仅支持 UART、I2C、SPI、USB、CSI")
        return normalized

    @field_validator("banned_hardware")
    @classmethod
    def normalize_bans(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(v.strip()[:100] for v in values if v.strip()))


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=5, max_length=2000)
    hardware_id: str = Field(max_length=100)
    field: Literal["io_tolerance", "algorithm_fps", "lifecycle", "interface"]
    source_url: str = Field("", max_length=1000)
    sensor: str = Field("", max_length=100)
    firmware: str = Field("", max_length=100)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    programming: Literal["unknown", "c", "python", "both"] = "unknown"
    linux_experience: Literal["unknown", "none", "some"] = "unknown"
    available_hours: float | None = Field(None, ge=0, le=1000)
    existing_hardware: list[str] = Field(default_factory=list, max_length=20)
    tools: list[str] = Field(default_factory=list, max_length=20)


class SignalContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: Literal["unspecified", "to_board", "from_board"] = "unspecified"
    voltage_v: float | None = Field(None, gt=0, le=100)
    pin: str = Field("", max_length=100)
    level_shifter: bool | None = None


class PreviousInputs(BaseModel):
    constraints: Constraints = Field(default_factory=Constraints)
    profile: Profile = Field(default_factory=Profile)
    signal_context: SignalContext = Field(default_factory=SignalContext)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_text: str = Field(min_length=5, max_length=12_000)
    search_mode: Literal["mock", "live"] = "mock"
    constraints: Constraints = Field(default_factory=Constraints)
    claim: Claim | None = None
    profile: Profile = Field(default_factory=Profile)
    signal_context: SignalContext = Field(default_factory=SignalContext)
    previous_inputs: PreviousInputs | None = None
    reuse_case_id: str | None = Field(None, max_length=50)

    @field_validator("problem_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if len(value.strip()) < 5:
            raise ValueError("请至少输入 5 个有效字符")
        return value.strip()
