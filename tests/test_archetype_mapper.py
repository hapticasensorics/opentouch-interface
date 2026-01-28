import numpy as np

from opentouch_interface.rerun import archetype_mapper as mapper


class RerunStub:
    def __init__(self):
        self.logged = []
        self.time_calls = []

    def log(self, path, obj):
        self.logged.append((path, obj))

    def set_time_seconds(self, timeline, value):
        self.time_calls.append((timeline, value))


class StubScalars:
    def __init__(self, values):
        self.values = list(values)


class StubImage:
    def __init__(self, data):
        self.data = data


class StubTensor:
    def __init__(self, data):
        self.data = data


def _install_stub(monkeypatch):
    stub = RerunStub()
    stub.Scalars = StubScalars
    stub.Image = StubImage
    stub.Tensor = StubTensor
    monkeypatch.setattr(mapper, "rr", stub)
    return stub


def test_camera_maps_to_image_with_downsample(monkeypatch):
    stub = _install_stub(monkeypatch)
    frame = np.arange(4 * 4 * 3).reshape((4, 4, 3))

    mapper.log_event("alpha", "camera", 0.5, frame, image_downsample=2)

    assert stub.time_calls == [("ot_time", 0.5)]
    assert len(stub.logged) == 1
    path, obj = stub.logged[0]
    assert path == "sensors/alpha/camera"
    assert isinstance(obj, StubImage)
    assert np.array_equal(obj.data, frame[::2, ::2, ...])


def test_audio_maps_to_tensor(monkeypatch):
    stub = _install_stub(monkeypatch)
    chunks = [np.array([1, 2, 3]), np.array([4, 5])]

    mapper.log_event("alpha", "audio", None, chunks)

    assert stub.time_calls == []
    assert len(stub.logged) == 1
    path, obj = stub.logged[0]
    assert path == "sensors/alpha/audio"
    assert isinstance(obj, StubTensor)
    assert obj.data.shape == (5, 1)
    assert np.array_equal(obj.data[:, 0], np.array([1, 2, 3, 4, 5]))


def test_serial_maps_to_scalars(monkeypatch):
    stub = _install_stub(monkeypatch)
    data = {
        "pressure": {"pressure": 101.3, "temperature": 22.5},
        "gas": {
            "temperature": 1.0,
            "pressure": 2.0,
            "humidity": 3.0,
            "gas": 4.0,
            "gas_index": 5.0,
        },
        "imu": {
            "raw": {"sensor_": 1, "x": 0.1, "y": 0.2, "z": 0.3},
            "euler": {"heading": 10.0, "pitch": 20.0, "roll": 30.0},
            "quat": {"x": 1.0, "y": 2.0, "z": 3.0, "w": 4.0, "accuracy": 0.99},
        },
    }

    mapper.log_event("alpha", "serial", None, data)

    expected = [
        ("sensors/alpha/serial/pressure/pressure", [101.3]),
        ("sensors/alpha/serial/pressure/temperature", [22.5]),
        ("sensors/alpha/serial/gas/temperature", [1.0]),
        ("sensors/alpha/serial/gas/pressure", [2.0]),
        ("sensors/alpha/serial/gas/humidity", [3.0]),
        ("sensors/alpha/serial/gas/gas", [4.0]),
        ("sensors/alpha/serial/gas/gas_index", [5.0]),
        ("sensors/alpha/serial/imu/raw/sensor_1/x", [0.1]),
        ("sensors/alpha/serial/imu/raw/sensor_1/y", [0.2]),
        ("sensors/alpha/serial/imu/raw/sensor_1/z", [0.3]),
        ("sensors/alpha/serial/imu/euler/heading", [10.0]),
        ("sensors/alpha/serial/imu/euler/pitch", [20.0]),
        ("sensors/alpha/serial/imu/euler/roll", [30.0]),
        ("sensors/alpha/serial/imu/quat/x", [1.0]),
        ("sensors/alpha/serial/imu/quat/y", [2.0]),
        ("sensors/alpha/serial/imu/quat/z", [3.0]),
        ("sensors/alpha/serial/imu/quat/w", [4.0]),
        ("sensors/alpha/serial/imu/quat/accuracy", [0.99]),
    ]

    assert len(stub.logged) == len(expected)
    for (path, obj), (expected_path, expected_values) in zip(stub.logged, expected):
        assert path == expected_path
        assert isinstance(obj, StubScalars)
        assert obj.values == expected_values
