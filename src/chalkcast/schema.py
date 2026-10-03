"""A bounded data contract. A planner can supply data, never executable code."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Visual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["bars", "chart", "flow", "equation"]
    labels: list[str] = Field(default_factory=list, max_length=6)
    values: list[float] = Field(default_factory=list, max_length=6)
    formula: str = Field(default="", max_length=100)
    caption: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def bounded(self):
        if any(any(c in text for c in "\r\n\t") for text in [*self.labels, self.formula, self.caption]):
            raise ValueError("Visual text must be single-line; use narration for paragraphs")
        if any(len(x) > 32 for x in self.labels):
            raise ValueError("Visual labels must be at most 32 characters")
        if any(not math.isfinite(x) or abs(x) > 1e6 for x in self.values):
            raise ValueError("Visual values must be finite and bounded")
        if self.kind in {"chart", "bars"} and (not self.values or len(self.values) != len(self.labels)):
            raise ValueError("Charts need matching labels and values")
        if self.kind == "flow" and not self.labels:
            raise ValueError("A flow needs at least one label")
        if self.kind == "equation" and not self.formula:
            raise ValueError("An equation needs a formula")
        return self


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=70)
    narration: str = Field(min_length=1, max_length=2000)
    visual: Visual

    @model_validator(mode="after")
    def title_single_line(self):
        if any(c in self.title for c in "\r\n\t"):
            raise ValueError("Scene titles must be single-line")
        if not self.narration.strip():
            raise ValueError("Narration must contain spoken text")
        return self


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    topic: str = Field(default="", max_length=300)
    audience: str = Field(default="curious beginners", max_length=200)
    language: str = Field(default="en", min_length=2, max_length=16)
    scenes: list[Scene] = Field(min_length=1, max_length=12)

    @property
    def characters(self):
        return sum(len(s.narration) for s in self.scenes)

    @model_validator(mode="after")
    def total_limit(self):
        if self.characters > 12000:
            raise ValueError("A storyboard is limited to 12,000 narration characters")
        return self


class RenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["silent", "elevenlabs", "openai"] = "silent"
    model_id: str = Field(default="eleven_flash_v2_5", pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    voice_id: str = Field(default="JBFqnCBsd6RMkjVDRZzb", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    max_cost_usd: float = Field(default=1, ge=0, le=100)
    max_characters: int = Field(default=10000, ge=1, le=12000)
    price_per_1k_characters: float | None = Field(default=None, ge=0, le=100)
    render: bool = True


class JobRequest(RenderOptions):
    storyboard: Storyboard
