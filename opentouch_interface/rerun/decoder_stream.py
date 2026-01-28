import json
from typing import Dict, Iterator, Tuple

import h5py

from opentouch_interface.core.serialization import (  # noqa: F401
    digit360_serializer,
    digit_sensor_serializer,
    gelsight_mini_serializer,
)
from opentouch_interface.core.registries.class_registries import SerializerClassRegistry
from opentouch_interface.core.sensor_group_saver import SensorGroupSaver


EventTuple = Tuple[str, str, float, object]


def _read_config(file_path: str) -> dict:
    """Read the config dataset directly from a .touch file."""
    with h5py.File(file_path, "r") as hdf5_file:
        if "config" not in hdf5_file:
            return {}
        raw_data = hdf5_file["config"][()]
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        return json.loads(raw_data)


def _build_serializers(config: dict) -> Dict[str, object]:
    """Return sensor_name -> serializer instance mapping."""
    serializers: Dict[str, object] = {}
    sensors_config = config.get("sensors", [])
    for sensor in sensors_config:
        sensor_name = sensor.get("sensor_name")
        sensor_type = sensor.get("sensor_type")
        if not sensor_name or not sensor_type:
            continue
        serializer_cls = SerializerClassRegistry.get_serializer(sensor_type)
        if serializer_cls is None:
            continue
        serializers[sensor_name] = serializer_cls()
    return serializers


def iter_events(file_path: str) -> Iterator[EventTuple]:
    """Stream decoded events from a .touch file.

    Yields:
        (sensor_name, stream_name, delta, data)
    """
    config = _read_config(file_path)
    serializers = _build_serializers(config)

    with h5py.File(file_path, "r") as hdf5_file:
        if "sensor_chunks" not in hdf5_file:
            return
        dataset = hdf5_file["sensor_chunks"]

        for i in range(dataset.shape[0]):
            chunk_blob = bytes(dataset[i])
            chunk_data = SensorGroupSaver.unpack_chunk_data(chunk_blob)

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
                        delta = decoded.get("delta")
                        data = decoded.get("data")
                        yield sensor_name, stream_name, delta, data
