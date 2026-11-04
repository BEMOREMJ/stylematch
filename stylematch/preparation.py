"""Private, development-only image preparation. No inference or source mutation."""

from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
from typing import Annotated, Literal
import warnings

from PIL import Image as PILImage, ImageCms, ImageOps, UnidentifiedImageError, __version__ as pillow_version
from pydantic import Field, field_validator, model_validator

from .contracts import Contract, Dataset, Garment, Identifier, Image, Nonempty, Query, Wardrobe
from .validation import require, unique, validate_dataset, verify_image_files

REPOSITORY = Path(__file__).resolve().parents[1]


class Handling(Contract):
    approved: bool = False
    decision_reference: Nonempty | None = None
    amendment: str = ""

    @model_validator(mode="after")
    def approval_reference(self) -> "Handling":
        if self.approved and (self.decision_reference is None or not self.decision_reference.strip()):
            raise ValueError("handling approval needs an actual owner decision reference")
        return self


class Source(Contract):
    image_id: Identifier
    path: Nonempty
    kind: Literal["garment", "inspiration"]
    provenance: Nonempty
    permission_basis: Literal["owner-created", "explicit-permission", "synthetic-authored"]
    permission_reference: Nonempty
    capture_group: Identifier
    source_group: Identifier

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return Image.relative_path(value)

    @field_validator("provenance", "permission_reference")
    @classmethod
    def not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("provenance and permission must be explicit")
        return value


class Crop(Contract):
    image_id: Identifier
    parent_image_id: Identifier
    box: Annotated[list[Annotated[int, Field(ge=0)]], Field(min_length=4, max_length=4)]


class Exclusion(Contract):
    image_id: Identifier
    component_category: Nonempty | None
    reason: Nonempty


class PilotPlan(Contract):
    schema_version: Literal[1]
    dataset_id: Identifier
    synthetic: bool
    wardrobe: Wardrobe
    reviewer_id: Identifier
    handling: Handling
    sources: list[Source]
    garments: list[Garment]
    crops: list[Crop]
    queries: list[Query]
    exclusions: list[Exclusion]

    @model_validator(mode="after")
    def development_only(self) -> "PilotPlan":
        if self.wardrobe.partition != "development" or any(q.partition != "development" for q in self.queries):
            raise ValueError("all pilot data must remain development data")
        if any(g.ref.wardrobe_id != self.wardrobe.wardrobe_id for g in self.garments):
            raise ValueError("pilot has one actual wardrobe, not owner subsets")
        if any(q.active_wardrobe_id != self.wardrobe.wardrobe_id for q in self.queries):
            raise ValueError("query active wardrobe must be the single pilot wardrobe")
        return self


def private_path(path: Path) -> Path:
    """Require ignored, untracked outputs inside this clone; resolve symlinks."""
    path = path.resolve()
    require(path.is_relative_to(REPOSITORY), "private outputs must be inside an ignored repository directory")
    relative = path.relative_to(REPOSITORY).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", relative], cwd=REPOSITORY,
        capture_output=True, check=False,
    )
    require(ignored.returncode == 0, "private output path is not ignored by Git")
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", relative], cwd=REPOSITORY, capture_output=True, check=True,
    )
    require(not tracked.stdout, "private output path contains tracked files")
    return path


def new_json(path: Path, value: dict) -> None:
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def contained(root: Path, relative: str, *, exists: bool = True) -> Path:
    Image.relative_path(relative)
    path = (root / relative).resolve(strict=exists)
    require(path.is_relative_to(root.resolve()), "path escapes declared root")
    return path


def sanitized_pixels(content: bytes) -> tuple[PILImage.Image, dict]:
    """Decode JPEG/PNG, orient, normalize tagged color to sRGB, strip metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PILImage.DecompressionBombWarning)
            with PILImage.open(BytesIO(content), formats=("JPEG", "PNG")) as original:
                require(getattr(original, "n_frames", 1) == 1, "animated/multiframe images are unsupported")
                original.load()
                details = {"format": original.format, "width_px": original.width, "height_px": original.height,
                           "exif_orientation": original.getexif().get(274)}
                oriented = ImageOps.exif_transpose(original)
                alpha = oriented.convert("RGBA").getchannel("A") if (
                    "A" in oriented.getbands() or "transparency" in oriented.info
                ) else None
                profile = original.info.get("icc_profile")
                if profile:
                    color_input = oriented.convert("RGB") if oriented.mode in ("RGBA", "P") else oriented
                    rgb = ImageCms.profileToProfile(
                        color_input, ImageCms.ImageCmsProfile(BytesIO(profile)),
                        ImageCms.createProfile("sRGB"), outputMode="RGB",
                    )
                else:
                    require(oriented.mode != "CMYK", "untagged CMYK is unsupported; export sRGB JPEG/PNG")
                    rgb = oriented.convert("RGB")
                if alpha is not None:
                    background = PILImage.new("RGB", rgb.size, "white")
                    background.paste(rgb, mask=alpha)
                    rgb = background
                # New pixel storage prevents inherited EXIF/XMP/text/ICC metadata.
                return PILImage.frombytes("RGB", rgb.size, rgb.tobytes()), details
    except (UnidentifiedImageError, PILImage.DecompressionBombError, PILImage.DecompressionBombWarning,
            ImageCms.PyCMSError, OSError, SyntaxError) as exc:
        raise ValueError("corrupt/unsupported image or invalid color profile; use a valid still JPEG/PNG") from exc


def save_pixels(path: Path, pixels: PILImage.Image) -> None:
    # Exclusive creation: never overwrite an earlier prepared image or original.
    with path.open("xb") as stream:
        pixels.save(stream, format="PNG")


def prepare(plan: PilotPlan, originals: Path, output: Path) -> Dataset:
    if not plan.synthetic:
        require(plan.handling.approved, "owner handling approval is pending; do not process real images")
    require(bool(plan.sources and plan.garments and plan.queries), "register sources, garments and tasks before preparation")
    originals = originals.resolve(strict=True)
    require(originals.is_dir(), "originals root must be a directory")
    if not plan.synthetic:
        require(not originals.is_relative_to(REPOSITORY), "real originals must be outside the Git working tree")
    output = private_path(output)
    require(not output.is_relative_to(originals) and not originals.is_relative_to(output), "source/output roots must be separate")
    unique((s.image_id for s in plan.sources), "source image IDs")
    unique((s.path for s in plan.sources), "original paths")
    unique([s.image_id for s in plan.sources] + [c.image_id for c in plan.crops], "source/crop image IDs")
    source_ids = {s.image_id for s in plan.sources}
    require(all(e.image_id in source_ids for e in plan.exclusions), "unknown exclusion source")
    used = {i for g in plan.garments for i in g.image_ids} | {q.image_id for q in plan.queries}
    require(source_ids <= used | {e.image_id for e in plan.exclusions}, "unused source needs an exclusion reason")
    require({c.image_id for c in plan.crops} == {q.crop_image_id for q in plan.queries if q.crop_image_id},
            "crop registrations must match human-selected task crops")
    for source in plan.sources:
        require((source.permission_basis == "synthetic-authored") == plan.synthetic,
                "source permission/synthetic status mismatch")
    # Read only explicitly registered files. No enumeration of personal folders.
    source_paths = {s.image_id: contained(originals, s.path) for s in plan.sources}
    for path in source_paths.values():
        require(path.is_file(), "registered original is not a file")
        if not plan.synthetic:
            require(not path.is_relative_to(REPOSITORY), "real original resolves inside Git working tree")
    output.mkdir(parents=True, exist_ok=False)
    (output / "prepared").mkdir()
    (output / "crops").mkdir()
    images, records = [], []
    for source in plan.sources:
        content = source_paths[source.image_id].read_bytes()
        record = {**source.model_dump(), "sha256": sha256(content).hexdigest()}
        if source.image_id not in used:
            # Explicitly excluded originals are registered/hash-audited without
            # trying to decode or prepare an unsupported/occluded source.
            records.append({**record, "prepared": False})
            continue
        pixels, details = sanitized_pixels(content)
        relative = f"prepared/{source.image_id}.png"
        target = output / relative
        save_pixels(target, pixels)
        images.append(Image(
            image_id=source.image_id, path=relative, sha256=sha256(target.read_bytes()).hexdigest(),
            kind=source.kind, partition="development", provenance=source.provenance,
            permission_reference=source.permission_reference,
            permitted_use="synthetic-engineering" if plan.synthetic else "feasibility-evaluation",
            capture_group=source.capture_group, source_group=source.source_group,
            width_px=pixels.width, height_px=pixels.height,
        ))
        records.append({**record, **details, "prepared": True})
        pixels.close()
    parents = {image.image_id: image for image in images}
    for crop in plan.crops:
        parent = parents.get(crop.parent_image_id)
        require(parent is not None and parent.kind == "inspiration", "crop needs a registered inspiration parent")
        left, top, right, bottom = crop.box
        require(left < right <= parent.width_px and top < bottom <= parent.height_px, "crop bounds invalid")
        with PILImage.open(output / parent.path) as source:
            pixels = source.crop(tuple(crop.box))
        relative = f"crops/{crop.image_id}.png"
        target = output / relative
        save_pixels(target, pixels)
        images.append(Image(
            image_id=crop.image_id, path=relative, sha256=sha256(target.read_bytes()).hexdigest(),
            kind="crop", partition="development", provenance=parent.provenance,
            permission_reference=parent.permission_reference, permitted_use=parent.permitted_use,
            capture_group=parent.capture_group, source_group=parent.source_group,
            parent_image_id=parent.image_id, crop_box=crop.box, width_px=pixels.width, height_px=pixels.height,
        ))
        pixels.close()
    dataset = Dataset(schema_version=1, dataset_id=plan.dataset_id, synthetic=plan.synthetic,
                      wardrobes=[plan.wardrobe], garments=plan.garments, images=images,
                      queries=plan.queries, judgments=[])
    validate_dataset(dataset, require_judgments=False)
    verify_prepared_images(dataset, output)
    for record in records:
        require(sha256(source_paths[record["image_id"]].read_bytes()).hexdigest() == record["sha256"],
                "original changed during preparation; no ready manifest written")
    # Write ready records last. Failed partial directories are preserved, never cleaned automatically.
    payload = dataset.model_dump()
    dataset_bytes = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()
    new_json(output / "preparation.json", {
        "schema_version": 1, "dataset_sha256": sha256(dataset_bytes).hexdigest(),
        "pillow_version": pillow_version, "plan": plan.model_dump(), "originals": records,
        "protocol": "EXIF transpose; tagged ICC to sRGB; untagged assumed sRGB; alpha on white; RGB PNG; no metadata; no resize",
    })
    new_json(output / "dataset.json", payload)
    return dataset


def verify_prepared_images(dataset: Dataset, root: Path) -> None:
    verify_image_files(dataset, root)
    for image in dataset.images:
        require(image.width_px is not None and image.height_px is not None, "pilot image dimensions missing")
        content = contained(root, image.path).read_bytes()
        pixels, _ = sanitized_pixels(content)
        require(pixels.size == (image.width_px, image.height_px), "decoded image dimensions mismatch")
        pixels.close()
        with PILImage.open(BytesIO(content)) as decoded:
            require(decoded.format == "PNG" and decoded.mode == "RGB", "prepared images must be RGB PNG")
            require(not decoded.info and not decoded.getexif(), "prepared image contains metadata")
        if image.kind == "crop":
            require(image.crop_box is not None, "pilot crop coordinates missing")


def load_pilot(root: Path, filename: str = "dataset.json", *, require_labels: bool = False) -> tuple[Dataset, dict]:
    root = private_path(root)
    content = contained(root, filename).read_bytes()
    dataset = Dataset.model_validate_json(content)
    require(len(dataset.wardrobes) == 1 and dataset.wardrobes[0].partition == "development",
            "pilot must have one development wardrobe")
    require(all(i.partition == "development" for i in dataset.images)
            and all(q.partition == "development" for q in dataset.queries), "pilot partition must be development")
    validate_dataset(dataset, require_judgments=require_labels)
    verify_prepared_images(dataset, root)
    audit = json.loads(contained(root, "preparation.json").read_bytes())
    require(isinstance(audit, dict) and audit.get("schema_version") == 1, "invalid preparation audit")
    plan = PilotPlan.model_validate(audit.get("plan"))
    original_content = contained(root, "dataset.json").read_bytes()
    require(sha256(original_content).hexdigest() == audit.get("dataset_sha256"), "preparation manifest binding mismatch")
    baseline = Dataset.model_validate_json(original_content)
    require(dataset.model_dump(exclude={"judgments"}) == baseline.model_dump(exclude={"judgments"}),
            "labeled manifest changed preparation fields")
    require(not dataset.judgments or {j.reviewer_id for j in dataset.judgments} == {plan.reviewer_id},
            "pilot must record the one actual reviewer")
    if filename != "dataset.json":
        label_audit_name = str(Path(filename).with_suffix(".label-audit.json")).replace("\\", "/")
        labeling = json.loads(contained(root, label_audit_name).read_bytes())
        require(isinstance(labeling, dict) and labeling.get("schema_version") == 1, "invalid label audit")
        require(labeling.get("dataset_sha256") == sha256(content).hexdigest(), "labeled manifest binding mismatch")
        audit["labeling"] = labeling
    return dataset, audit


def summary(dataset: Dataset, exclusions: list[dict]) -> dict:
    return {
        "synthetic": dataset.synthetic, "wardrobes": len(dataset.wardrobes),
        "garments": len(dataset.garments), "images_including_crops": len(dataset.images),
        "garments_by_category": dict(Counter(g.category for g in dataset.garments)),
        "inspiration_images": sum(i.kind == "inspiration" for i in dataset.images),
        "crops": sum(i.kind == "crop" for i in dataset.images), "component_tasks": len(dataset.queries),
        "tasks_by_category": dict(Counter(q.component_category for q in dataset.queries)),
        "resolved_judgments": len(dataset.judgments), "reviewers": sorted({j.reviewer_id for j in dataset.judgments}),
        "no_match_tasks": sum(j.no_match for j in dataset.judgments)
        if len(dataset.judgments) == len(dataset.queries) else None,
        "missing_category_tasks": sum(not any(g.category == q.component_category for g in dataset.garments)
                                      for q in dataset.queries),
        "exclusions": exclusions,
        "status": "labels complete" if len(dataset.judgments) == len(dataset.queries) else "human labels pending",
    }
