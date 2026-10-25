"""Provider-neutral project/part models; custom facts remain user assertions."""
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomPart(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=200)
    category: str = Field("custom", max_length=60)
    kind: str = Field("module", max_length=40)
    manufacturer: str = Field("用户录入", max_length=100)
    source_url: str = Field("", max_length=1200)
    facts: dict = Field(default_factory=dict)
    notes: str = Field("", max_length=2000)


class BomLine(StrictModel):
    ref: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,30}$")
    part_id: str = Field(min_length=1, max_length=80)
    quantity: int = Field(1, ge=1, le=100000)
    unit_price_cny: float | None = Field(None, ge=0, le=1e8)
    quote_source: str = Field("", max_length=1200)
    quote_at: datetime | None = None
    quote_kind: Literal["user_quote", "search_lead", "test", "unknown"] = "unknown"
    notes: str = Field("", max_length=1500)


class Connection(StrictModel):
    from_ref: str = Field(max_length=31)
    to_ref: str = Field(max_length=31)
    kind: Literal["power", "signal", "protocol", "mechanical", "software"] = "protocol"
    protocol: str = Field("", max_length=100)
    voltage_v: float | None = Field(None, gt=0, le=10000)
    load_a: float | None = Field(None, ge=0, le=100000)
    notes: str = Field("", max_length=1200)


class HardwareProject(StrictModel):
    conversation_id: str | None = Field(None,pattern=r"^[a-f0-9-]{36}$")
    name: str = Field("未命名硬件项目", min_length=1, max_length=200)
    description: str = Field("", max_length=16000)
    domain: str = Field("auto", max_length=60)
    requirements: dict[str, str] = Field(default_factory=dict, max_length=30)
    budget_cny: float | None = Field(None, ge=0, le=1e9)
    bom: list[BomLine] = Field(default_factory=list, max_length=80)
    connections: list[Connection] = Field(default_factory=list, max_length=160)
    custom_parts: list[CustomPart] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def unique_references(self):
        refs = [line.ref for line in self.bom]
        if len(refs) != len(set(refs)):
            raise ValueError("BOM位号必须唯一")
        ids = [part.id for part in self.custom_parts]
        if len(ids) != len(set(ids)):
            raise ValueError("自定义器件ID必须唯一")
        for edge in self.connections:
            if edge.from_ref not in refs or edge.to_ref not in refs or edge.from_ref == edge.to_ref:
                raise ValueError("连接必须指向两个不同的现有BOM位号")
        return self


class ReviewRequest(StrictModel):
    project: HardwareProject
    previous_project: HardwareProject | None = None
    search_mode: Literal["off", "mock", "live"] = "off"
    review_id: str | None = Field(None,pattern=r"^[a-f0-9-]{36}$")


class DialogueRequest(StrictModel):
    project: HardwareProject = Field(default_factory=HardwareProject)
    message: str = Field(min_length=1, max_length=6000)
    pending_key: str | None = Field(None, max_length=80)
    history: list[dict] = Field(default_factory=list, max_length=50)
    decision_mode: Literal["live", "rules_demo"] = "live"


class SearchRequest(StrictModel):
    query: str = Field(min_length=2, max_length=400)
    category: str = Field("", max_length=80)
    mode: Literal["mock", "live"] = "mock"


class PriceRequest(StrictModel):
    mpn: str = Field(min_length=2, max_length=160)
    item_type: str = Field("模块", max_length=100)
    mode: Literal["mock", "live"] = "mock"


class DocumentInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=10, max_length=300000)
    source_url: str = Field("", max_length=1200)


class QuestionInput(StrictModel):
    question: str = Field(min_length=2, max_length=1000)
    document_ids: list[str] = Field(default_factory=list, max_length=30)
    part_ids: list[str] = Field(default_factory=list, max_length=80)


class CsvInput(StrictModel):
    csv_text: str = Field(min_length=1, max_length=300000)
