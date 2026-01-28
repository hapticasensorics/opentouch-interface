from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_TIMELINE = "ot_time"
DEFAULT_APP_ID = "opentouch_to_rrd"


@dataclass(frozen=True)
class DownsampleOptions:
    """Controls downsampling for high-frequency streams."""

    image_stride: int = 1
    audio_decimation: int = 1
    scalar_stride: int = 1


@dataclass(frozen=True)
class EntityPathConfig:
    """Defines how sensor streams map to Rerun entity paths."""

    root: str = "sensors"
    streams: Dict[str, str] = field(
        default_factory=lambda: {
            "camera": "camera",
            "serial": "serial",
            "pressure": "pressure",
            "imu": "imu",
            "imu_euler": "imu/euler",
            "imu_quat": "imu/quaternion",
            "audio": "audio",
        }
    )

    def path_for(self, sensor_name: str, stream: str) -> str:
        """Return the canonical entity path for a sensor stream."""
        stream_path = self.streams.get(stream, stream)
        return f"{self.root}/{sensor_name}/{stream_path}"


DEFAULT_ENTITY_PATHS = EntityPathConfig()


DEFAULT_VIEWER_LAYOUT = {
    "timeline": DEFAULT_TIMELINE,
    "views": [
        {
            "name": "Cameras",
            "type": "image",
            "entities": ["sensors/*/camera"],
        },
        {
            "name": "Scalars",
            "type": "time_series",
            "entities": [
                "sensors/*/serial",
                "sensors/*/pressure",
                "sensors/*/imu",
                "sensors/*/imu/*",
            ],
        },
        {
            "name": "Audio",
            "type": "tensor",
            "entities": ["sensors/*/audio"],
        },
    ],
}


def default_downsample_options() -> DownsampleOptions:
    """Return the default downsampling configuration."""
    return DownsampleOptions()


def _layout_fingerprint(layout: dict) -> str:
    payload = json.dumps(layout, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _normalize_entity(expr: str) -> str:
    if expr.startswith(("/", "$")):
        return expr
    return f"/{expr}"


def _layout_time_ranges(timeline: Optional[str]):
    if not timeline:
        return None
    import rerun.blueprint as rrb

    start = rrb.TimeRangeBoundary.infinite()
    end = rrb.TimeRangeBoundary.infinite()
    return [rrb.VisibleTimeRange(timeline, start=start, end=end)]


def build_blueprint(layout: dict = DEFAULT_VIEWER_LAYOUT):
    """Build a Rerun blueprint from a viewer layout."""
    import rerun.blueprint as rrb

    views = []
    time_ranges = _layout_time_ranges(layout.get("timeline"))
    for view in layout.get("views", []):
        view_type = view.get("type", "time_series")
        name = view.get("name")
        entities = view.get("entities") or []
        contents = [f"+ {_normalize_entity(entity)}" for entity in entities] if entities else None

        kwargs = {}
        if name:
            kwargs["name"] = name
        if contents is not None:
            kwargs["contents"] = contents
        if time_ranges is not None and view_type in ("image", "time_series"):
            kwargs["time_ranges"] = time_ranges

        if view_type == "image":
            views.append(rrb.Spatial2DView(origin="/", **kwargs))
        elif view_type == "tensor":
            views.append(rrb.TensorView(origin="/", **kwargs))
        else:
            views.append(rrb.TimeSeriesView(origin="/", **kwargs))

    if not views:
        return rrb.Blueprint()
    return rrb.Blueprint(rrb.Grid(*views))


def save_blueprint(
    cache_dir: Path,
    application_id: str = DEFAULT_APP_ID,
    layout: dict = DEFAULT_VIEWER_LAYOUT,
) -> Path:
    """Save the viewer layout blueprint and return its path."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _layout_fingerprint(layout)
    blueprint_path = cache_dir / f"rerun-viewer-{fingerprint}.rbl"
    if blueprint_path.exists() and blueprint_path.stat().st_size > 0:
        return blueprint_path

    blueprint = build_blueprint(layout)
    blueprint.save(application_id, blueprint_path)
    return blueprint_path
