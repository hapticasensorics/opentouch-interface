from __future__ import annotations

from typing import Any

import numpy as np
import rerun as rr


def _entity_path(sensor_name: str, stream_name: str, *parts: str) -> str:
    base = f"sensors/{sensor_name}/{stream_name}"
    if not parts:
        return base
    return "/".join([base, *parts])


def _get_field(obj: Any, field: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def _log_scalar(path: str, value: Any) -> None:
    if value is None:
        return
    rr.log(path, rr.Scalars([value]))


def _log_camera(path: str, frame: Any, downsample: int) -> None:
    if frame is None:
        return
    if not isinstance(frame, np.ndarray):
        frame = np.asarray(frame)
    if frame.size == 0:
        return
    if downsample > 1:
        frame = frame[::downsample, ::downsample, ...]
    rr.log(path, rr.Image(frame))


def _log_pressure(base_path: str, pressure_data: Any) -> None:
    pressure = _get_field(pressure_data, "pressure")
    temperature = _get_field(pressure_data, "temperature")
    _log_scalar(f"{base_path}/pressure/pressure", pressure)
    _log_scalar(f"{base_path}/pressure/temperature", temperature)


def _log_gas(base_path: str, gas_data: Any) -> None:
    for key in ("temperature", "pressure", "humidity", "gas", "gas_index"):
        value = _get_field(gas_data, key)
        _log_scalar(f"{base_path}/gas/{key}", value)


def _log_imu(base_path: str, imu_data: Any) -> None:
    if not isinstance(imu_data, dict):
        return
    raw = imu_data.get("raw") or {}
    sensor_id = raw.get("sensor_")
    raw_prefix = f"{base_path}/imu/raw"
    if sensor_id is not None:
        raw_prefix = f"{raw_prefix}/sensor_{sensor_id}"
    for axis in ("x", "y", "z"):
        _log_scalar(f"{raw_prefix}/{axis}", raw.get(axis))

    euler = imu_data.get("euler") or {}
    for key in ("heading", "pitch", "roll"):
        _log_scalar(f"{base_path}/imu/euler/{key}", euler.get(key))

    quat = imu_data.get("quat") or {}
    for key in ("x", "y", "z", "w", "accuracy"):
        _log_scalar(f"{base_path}/imu/quat/{key}", quat.get(key))


def _log_audio(path: str, audio_data: Any) -> None:
    if audio_data is None:
        return
    if isinstance(audio_data, list):
        chunks = []
        for chunk in audio_data:
            if chunk is None:
                continue
            arr = np.asarray(chunk)
            if arr.size == 0:
                continue
            if arr.ndim == 1:
                arr = arr.reshape((-1, 1))
            chunks.append(arr)
        if not chunks:
            return
        audio = np.vstack(chunks)
    else:
        audio = np.asarray(audio_data)
        if audio.size == 0:
            return
    rr.log(path, rr.Tensor(audio))


def log_event(
    sensor_name: str,
    stream_name: str,
    delta: float | None,
    data: Any,
    image_downsample: int = 1,
) -> None:
    if delta is not None:
        try:
            rr.set_time_seconds("ot_time", float(delta))
        except (TypeError, ValueError):
            pass

    if stream_name == "camera":
        _log_camera(_entity_path(sensor_name, stream_name), data, image_downsample)
        return

    if stream_name == "serial":
        if isinstance(data, dict):
            if "pressure" in data:
                _log_pressure(_entity_path(sensor_name, stream_name), data["pressure"])
            if "pressure_ap" in data:
                # pressure_ap contains raw bytes; skip until a decoder is defined.
                pass
            if "gas" in data:
                _log_gas(_entity_path(sensor_name, stream_name), data["gas"])
            if "imu" in data:
                _log_imu(_entity_path(sensor_name, stream_name), data["imu"])
        return

    if stream_name == "audio":
        _log_audio(_entity_path(sensor_name, stream_name), data)
        return
