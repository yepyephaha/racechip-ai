"""Model proposals are purchasing specifications, never verified device facts."""
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteOption(PlanModel):
    name: str = Field(min_length=1, max_length=120)
    suitable_for: str = Field(min_length=1, max_length=400)
    tradeoff: str = Field(min_length=1, max_length=500)
    selected: bool = False


class PurchaseSpec(PlanModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=1, max_length=60)
    kind: Literal["board", "module", "ic", "mechanical", "accessory", "tool"] = "module"
    quantity: int = Field(ge=1, le=100)
    unit: str = Field("个", max_length=20)
    specs: str = Field(min_length=2, max_length=800)
    purpose: str = Field(min_length=2, max_length=500)
    selection_reason: str = Field(min_length=2, max_length=600)
    compatibility_checks: list[str] = Field(default_factory=list, max_length=8)
    search_query: str = Field(min_length=2, max_length=220)
    match_terms: list[str] = Field(min_length=1, max_length=5)
    owned: bool = False
    owned_quote: str = Field("", max_length=1000)
    optional: bool = False
    package_note: str = Field("", max_length=600)


class CoverageItem(PlanModel):
    function: str = Field(min_length=1, max_length=100)
    item_ids: list[str] = Field(default_factory=list, max_length=12)
    note: str = Field("", max_length=600)


class BuildPlan(PlanModel):
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=2, max_length=1600)
    selected_route: str = Field(min_length=2, max_length=300)
    selection_reason: str = Field(min_length=2, max_length=1200)
    options: list[RouteOption] = Field(default_factory=list, max_length=4)
    purchase_items: list[PurchaseSpec] = Field(min_length=1, max_length=24)
    coverage: list[CoverageItem] = Field(default_factory=list, max_length=18)
    assembly_steps: list[str] = Field(min_length=1, max_length=18)
    acceptance_checks: list[str] = Field(min_length=1, max_length=12)
    unresolved: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def valid_references(self):
        ids = [item.id for item in self.purchase_items]
        if len(ids) != len(set(ids)):
            raise ValueError("采购项ID必须唯一")
        for item in self.purchase_items:
            if re.search(r'或|若干|待选',item.name):
                raise ValueError(f'采购项{item.id}的名称须选定一种规格，不能以“或/若干/待选”列出多个未选择的商品；配套核对条件可写入specs或unresolved。')
        for coverage in self.coverage:
            if not set(coverage.item_ids).issubset(ids):
                raise ValueError("完整性检查引用了不存在的采购项")
        return self
