"""Version 1 data/run contracts. Semantic checks live in validation.py."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Category = Literal["tops", "bottoms", "outerwear"]
Partition = Literal["development", "test"]
Nonempty = Annotated[str, Field(min_length=1)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ItemRef(Contract):
    wardrobe_id: Identifier
    item_id: Identifier

    @property
    def key(self) -> tuple[str, str]:
        return self.wardrobe_id, self.item_id


class Wardrobe(Contract):
    wardrobe_id: Identifier
    person_id: Identifier
    partition: Partition


class Image(Contract):
    image_id: Identifier
    path: Nonempty
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    kind: Literal["garment", "inspiration", "crop"]
    partition: Partition
    provenance: Nonempty
    permission_reference: Nonempty
    permitted_use: Literal["synthetic-engineering", "feasibility-evaluation"]
    capture_group: Identifier
    source_group: Identifier
    parent_image_id: Identifier | None = None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        # Reject Windows drive/UNC paths and traversal on every host OS.
        from pathlib import PurePosixPath, PureWindowsPath

        path = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if (
            "\\" in value or ":" in value or path.is_absolute() or windows.drive
            or any(part in ("", ".", "..") for part in value.split("/"))
        ):
            raise ValueError("image path must be a normalized relative POSIX path")
        return value


class Garment(Contract):
    ref: ItemRef
    category: Category
    image_ids: Annotated[list[Identifier], Field(min_length=1)]


class Query(Contract):
    query_id: Identifier
    active_wardrobe_id: Identifier
    image_id: Identifier
    component_category: Category
    partition: Partition
    crop_image_id: Identifier | None = None


class Grade(Contract):
    ref: ItemRef
    relevance: Annotated[int, Field(ge=0, le=3)]


class Judgment(Contract):
    query_id: Identifier
    reviewer_id: Identifier
    no_match: bool
    uncertain: bool
    notes: str
    grades: list[Grade]


class Dataset(Contract):
    schema_version: Literal[1]
    dataset_id: Identifier
    synthetic: bool
    wardrobes: Annotated[list[Wardrobe], Field(min_length=1)]
    images: Annotated[list[Image], Field(min_length=1)]
    garments: list[Garment]
    queries: Annotated[list[Query], Field(min_length=1)]
    judgments: list[Judgment]


class Prediction(Contract):
    ref: ItemRef
    score: Annotated[float, Field(allow_inf_nan=False)] | None = None


class Ranking(Contract):
    query_id: Identifier
    predictions: list[Prediction]


class Resources(Contract):
    device: Nonempty
    wall_time_ms: Nonnegative | None
    peak_ram_bytes: Annotated[int, Field(ge=0)] | None
    peak_vram_bytes: Annotated[int, Field(ge=0)] | None
    missing_reasons: dict[str, Nonempty]

    @model_validator(mode="after")
    def explain_missing(self) -> "Resources":
        fields = ("wall_time_ms", "peak_ram_bytes", "peak_vram_bytes")
        missing = {name for name in fields if getattr(self, name) is None}
        if set(self.missing_reasons) != missing:
            raise ValueError("missing_reasons must explain exactly the unmeasured resources")
        return self


class ModelMetadata(Contract):
    name: Nonempty
    checkpoint: Nonempty
    revision: Nonempty
    preprocessing: Nonempty
    dependency_lock_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    notes: Nonempty


class Run(Contract):
    schema_version: Literal[1]
    run_id: Identifier
    dataset_id: Identifier
    dataset_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    status: Literal["complete", "failed"]
    failures: list[Nonempty]
    model: ModelMetadata
    threshold: Annotated[float, Field(allow_inf_nan=False)] | None
    threshold_selection_partition: Literal["development"]
    resources: Resources
    rankings: list[Ranking]

    @model_validator(mode="after")
    def failure_status(self) -> "Run":
        if (self.status == "failed") != bool(self.failures):
            raise ValueError("failed runs need failures; complete runs cannot have failures")
        return self
