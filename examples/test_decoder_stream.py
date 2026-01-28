#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import h5py

from opentouch_interface.core.sensor_group_saver import SensorGroupSaver
from opentouch_interface.rerun import decoder_stream


SensorKey = Tuple[str, str]


def _find_touch_files() -> List[Path]:
    candidates: List[Path] = []
    for root in (Path("tests"), Path("examples"), Path("datasets"), Path("tmp")):
        if root.exists():
            candidates.extend(sorted(root.rglob("*.touch")))
    if not candidates:
        candidates.extend(sorted(Path(".").rglob("*.touch")))
    return candidates


def _summarize_sensor_types(config: dict) -> List[Tuple[str, str]]:
    sensors = config.get("sensors", [])
    summary: List[Tuple[str, str]] = []
    for sensor in sensors:
        name = sensor.get("sensor_name") or "<unnamed>"
        sensor_type = sensor.get("sensor_type") or "<unknown>"
        summary.append((name, sensor_type))
    return summary


def _decode_first_chunk_counts(
    file_path: Path,
    serializers: Dict[str, object],
) -> Tuple[Optional[Dict[SensorKey, int]], int]:
    with h5py.File(file_path, "r") as hdf5_file:
        if "sensor_chunks" not in hdf5_file:
            return None, 0
        dataset = hdf5_file["sensor_chunks"]
        if dataset.shape[0] == 0:
            return None, 0
        chunk_blob = bytes(dataset[0])

    chunk_data = SensorGroupSaver.unpack_chunk_data(chunk_blob)
    counts: Dict[SensorKey, int] = {}
    total = 0
    for sensor_name, streams in chunk_data.items():
        serializer = serializers.get(sensor_name)
        if serializer is None:
            continue
        for stream_name, events in streams.items():
            for event_blob in events:
                try:
                    decoded = serializer.deserialize(event_blob)
                except Exception:
                    continue
                if not isinstance(decoded, dict):
                    continue
                total += 1
                key = (sensor_name, stream_name)
                counts[key] = counts.get(key, 0) + 1
    return counts, total


def _iter_events_with_limit(
    file_path: Path,
    max_events: Optional[int],
    first_chunk_total: Optional[int],
) -> Tuple[int, Dict[SensorKey, int], Dict[SensorKey, int], int, int, List[str]]:
    total = 0
    all_counts: Dict[SensorKey, int] = {}
    first_chunk_counts: Dict[SensorKey, int] = {}
    missing_delta = 0
    missing_data = 0
    sensors_seen: List[str] = []

    for sensor_name, stream_name, delta, data in decoder_stream.iter_events(str(file_path)):
        total += 1
        key = (sensor_name, stream_name)
        all_counts[key] = all_counts.get(key, 0) + 1

        if first_chunk_total is not None and total <= first_chunk_total:
            first_chunk_counts[key] = first_chunk_counts.get(key, 0) + 1

        if delta is None:
            missing_delta += 1
        if data is None:
            missing_data += 1
        if sensor_name not in sensors_seen:
            sensors_seen.append(sensor_name)

        if max_events is not None and total >= max_events:
            break

    return total, all_counts, first_chunk_counts, missing_delta, missing_data, sensors_seen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate streaming decode for a .touch file using decoder_stream.iter_events().",
    )
    parser.add_argument(
        "--touch",
        dest="touch_path",
        help="Path to a .touch file. If omitted, searches tests/, examples/, datasets/.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Optional cap on number of streamed events to read.",
    )
    args = parser.parse_args()

    touch_path: Optional[Path]
    if args.touch_path:
        touch_path = Path(args.touch_path)
    else:
        candidates = _find_touch_files()
        touch_path = candidates[0] if candidates else None

    if touch_path is None:
        print(
            "No .touch files found in tests/, examples/, or datasets/. Provide --touch to proceed.",
            file=sys.stderr,
        )
        return 2

    if not touch_path.exists():
        print(f".touch file not found: {touch_path}", file=sys.stderr)
        return 2

    print(f"Using .touch file: {touch_path}")

    config = decoder_stream._read_config(str(touch_path))
    sensor_summary = _summarize_sensor_types(config)
    if not sensor_summary:
        print("Config has no sensors; streaming decode will skip all events.", file=sys.stderr)
    else:
        print("Sensors declared in config:")
        for name, sensor_type in sensor_summary:
            print(f"- {name}: {sensor_type}")

    serializers = decoder_stream._build_serializers(config)
    if not serializers:
        print("No serializers could be built from config.", file=sys.stderr)

    with h5py.File(touch_path, "r") as hdf5_file:
        if "sensor_chunks" not in hdf5_file:
            print("Missing sensor_chunks dataset in .touch file.", file=sys.stderr)
            return 3
        dataset = hdf5_file["sensor_chunks"]
        print(f"sensor_chunks shape: {dataset.shape}")
        if dataset.shape[0] == 0:
            print("sensor_chunks dataset is empty.", file=sys.stderr)
            return 3

    expected_counts, expected_total = _decode_first_chunk_counts(touch_path, serializers)
    if expected_counts is None:
        print("Unable to decode first chunk (missing sensor_chunks or empty dataset).", file=sys.stderr)

    if expected_total and args.max_events is not None and args.max_events < expected_total:
        print(
            "max-events is smaller than the first chunk event count; "
            "first-chunk verification will be skipped.",
            file=sys.stderr,
        )
        expected_total = None
        expected_counts = None

    total, all_counts, first_chunk_counts, missing_delta, missing_data, sensors_seen = _iter_events_with_limit(
        touch_path,
        args.max_events,
        expected_total if expected_total else None,
    )

    if total == 0:
        print("No events streamed from decoder_stream.iter_events().", file=sys.stderr)
        return 4

    print(f"Streamed events: {total}")
    print(f"Events missing delta: {missing_delta}")
    print(f"Events missing data: {missing_data}")
    print(f"Sensors observed in stream: {', '.join(sensors_seen)}")

    if expected_counts is not None:
        if first_chunk_counts != expected_counts:
            print("First chunk event counts do not match stream output.", file=sys.stderr)
            print(f"Expected: {expected_counts}", file=sys.stderr)
            print(f"Observed: {first_chunk_counts}", file=sys.stderr)
            return 5
        print("First chunk verification passed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
