# OpenTouch -> Rerun Integration Plan (A)

## 0) Scope + assumptions
- Goal: visualize OpenTouch tactile datasets (.touch) in Rerun, with HapticaGUIPlugin (Reflex) providing dataset controls and orchestration.
- Repo note: the Reflex UI appears to live at `/Users/paulhan/dev/HapticaGUIPlugin` (contains `src/haptica_reflex_scaffold`). The path `/Users/paulhan/dev/HapticaReflexScaffold` does not exist on disk; adjust paths if needed.
- This plan is based on code inspection under `/Users/paulhan/dev/opentouch-interface`.

---

## 1) Data Format Analysis (OpenTouch)

### 1.1 On-disk layout
- Base dataset directory: `./datasets` (see `OTIConfig`), with recordings stored as `.touch` files.
- Recording destination names are normalized (alnum + `_`), and always end with `.touch`.
- The `.touch` file is HDF5 and contains:
  - `sensor_chunks`: 1D varlen `uint8` dataset; each element is a packed binary chunk.
  - `chunk_start_times`, `chunk_end_times`: `float64` arrays giving chunk time bounds (seconds since recording start).
  - `config`: JSON string of the group configuration (group_name, destination, sensors list, payload list).

### 1.2 Chunk / event binary schema
Each chunk encodes a nested structure: `{sensor_name -> stream_name -> [event_bytes...]}`.

**Chunk encoding** (see `SensorGroupSaver.pack_chunk_data`):
- `uint32 num_sensors`
- For each sensor:
  - `uint32 sensor_name_len`, `sensor_name` (UTF-8)
  - `uint32 num_streams`
  - For each stream:
    - `uint32 stream_name_len`, `stream_name` (UTF-8)
    - `uint32 num_events`
    - For each event: `uint32 event_len` + `event_bytes`

**Event encoding** (see `BaseSerializer`):
- 40-byte header:
  - `stream_name` (32 bytes, UTF-8, null-padded)
  - `time_delta` (`float64`, seconds since recording start)
- Payload: sensor-specific binary (see below).

### 1.3 Sensor modalities & stream payloads
Sensors discovered in `examples/config` and `core/sensors`:

**Digit**
- Streams: `camera` (30 Hz)
- Payload: OpenCV `np.ndarray` image (`H x W x C`, uint8). Serialized as `height,width,channels` (3x uint32) + raw bytes.

**GelSight Mini**
- Streams: `camera` (30 Hz)
- Payload: OpenCV `np.ndarray` image (`H x W x C`, uint8). Same serialization as Digit.

**Digit360**
- Streams: `camera` (30 Hz), `serial` (100 Hz), `audio` (10 Hz)
- `camera`: same as Digit/GelSight.
- `serial`: binary prefix + structured data:
  - `PAP` -> `pressure_ap` (betterproto message)
  - `PRS` -> `pressure` (betterproto message)
  - `GAS` -> `gas` (betterproto message)
  - `IMU` -> custom packed struct with `ts`, `raw` (sensor_, ts_ght, x,y,z), `euler` (ts_ght, heading,pitch,roll), `quat` (ts_ght, x,y,z,w, accuracy)
- `audio`: list of chunks; each chunk is `np.ndarray` shape `(n,2)` with int16 samples. Serialized as:
  - `int32 num_chunks`, `int32[num_chunks] chunk_sizes`, then flattened `int16` sample pairs.

### 1.4 Decoder view of the data
- `Decoder(file_path)` loads all decoded events into:
  ```
  { sensor_name: { stream_name: [ {"delta": float, "data": ...}, ... ] } }
  ```
- `stream_data_of(..., with_delta=False)` strips the `delta` wrapper.

### 1.5 Payload (metadata labels)
- `payload` is stored in the `config` JSON and supports UI widgets like `slider`, `text_input`, `checkbox`, `multiselect`, `radio`, `selectbox`, `number_input` (see `docs/payload.md`).
- These values are metadata labels for a recording, not per-sample sensor data.

---

## 2) Rerun Integration Architecture

### 2.1 Ingestion modes (choose 1 or both)
**A) Offline conversion (.touch -> .rrd)**
- Read `.touch` file and emit a `.rrd` recording via `rr.save()`.
- Benefits: quick load in viewer, shareable single file; consistent with web embedding.

**B) Live streaming (.touch -> Rerun gRPC)**
- Stream decoded chunks into a running Rerun viewer using `rr.connect_grpc()` or `rr.serve_grpc()` + viewer connect.
- Optionally use `rr.serve_web_viewer()` for an embedded web viewer.
- Useful for large datasets or partial reads (stream chunks on demand).

### 2.2 Entity path strategy
- Use a stable hierarchy rooted by sensor name:
  - `sensors/<sensor_name>/camera`
  - `sensors/<sensor_name>/serial/pressure`
  - `sensors/<sensor_name>/serial/imu/raw`
  - `sensors/<sensor_name>/audio`
- Keep paths consistent so UI filters can target subtrees.

### 2.3 Rerun archetype mapping
- **Camera frames**: `Image` (raw) or `EncodedImage` (if re-encoding to PNG/JPEG for bandwidth savings).
- **Tactile arrays (future)**: `Image` for 2D arrays or `Tensor` for higher dimensions.
- **Serial pressure / gas**: `Scalars` time series; use `SeriesLines` or `SeriesPoints` for plot styling.
- **IMU**:
  - Numeric channels (raw x/y/z, euler, quat): `Scalars`.
  - Orientation visualization (optional): `Transform3D` or `Arrows3D` + `Points3D` for axes.
- **Audio**:
  - `Tensor` (shape `[samples, channels]`) for each chunk, or
  - Per-channel `Scalars` with downsampling.

### 2.4 Timeline & synchronization
- Use the event `delta` (seconds since recording start) as the primary time axis.
- In Rerun, set a custom timeline per event:
  - `rr.set_time("ot_time", duration=delta)` (convert seconds to ns if needed).
- Optionally also set a per-stream `sequence` timeline (frame index) for missing/irregular events.
- For multi-stream sync: Rerun aligns entities by timeline; use shared `ot_time` across sensors.

### 2.5 Chunked loading strategy
- Avoid loading entire datasets into RAM for large recordings.
- Stream chunk-by-chunk from HDF5 (`sensor_chunks`) and emit logs as you decode; tie chunk time to `chunk_start_times` / `chunk_end_times` for coarse seeking.
- Use batch logging (`send_columns`) for sequences (images, scalars) when converting to `.rrd` for speed.

### 2.6 Viewer constraints & versioning
- Viewer and SDK versions should match (data format stability note).
- Web viewer runs in 32-bit Wasm and has practical memory limits (~2 GiB), so prefer offline conversion or downsampling for large datasets.

---

## 3) HapticaGUIPlugin (Reflex) Integration

### 3.1 What Rerun doesn’t provide
Use the Reflex UI to cover:
- Dataset selection and indexing (`./datasets/*.touch`).
- Sensor/stream filtering (enable/disable camera, serial, audio).
- Downsampling / resolution options (image stride, audio decimation).
- Export (e.g., `.rrd`, `.csv` for scalar streams).
- Metadata editing (payload values, tags, notes).
- Session control (play/pause, time window, seek to chunk).

### 3.2 Viewer embedding options
**Option A: iframe to app.rerun.io**
- Simple embed with a URL to `.rrd` or `rerun+http://.../proxy` source.
- No programmable control inside the iframe.

**Option B: JS web viewer package**
- Use `@rerun-io/web-viewer` for programmatic control (open/close recordings).
- Embed via Reflex custom JS or a small frontend bridge.

**Option C: Native viewer + external controls**
- Keep viewer as a desktop app; Reflex UI triggers dataset conversion + calls `rerun <file.rrd>` or connects to gRPC.

### 3.3 Control-plane (UI <-> data pipeline)
Define a lightweight control service (Python) that Reflex talks to over HTTP/WebSocket:
- `GET /datasets` -> list of `.touch` recordings + metadata (from `config` dataset).
- `POST /sessions` -> start a Rerun session (mode: `rrd` or `grpc`), return viewer URL / rrd path.
- `POST /sessions/{id}/filters` -> enable/disable streams, downsample settings.
- `POST /sessions/{id}/seek` -> time offset (seconds).
- `POST /sessions/{id}/export` -> create `.rrd` or CSV.

This service runs near the data and uses the OpenTouch decoder + Rerun SDK.

---

## 4) Implementation Steps (ordered with dependencies & complexity)

1) **Inventory & schema doc**
   - Confirm `.touch` structure, sensors, stream payloads, payload metadata.
   - Output: JSON schema doc + example event types.
   - Complexity: Low
   - Depends on: none

2) **Chunked decoder utility**
   - Build a streaming iterator over HDF5 `sensor_chunks` to avoid full in-memory load.
   - Output: generator yielding `(sensor_name, stream_name, delta, data)`.
   - Complexity: Medium
   - Depends on: (1)

3) **Rerun mapping layer**
   - Map each stream to archetypes (`Image`, `Tensor`, `Scalars`, `SeriesLines`, optional `Transform3D`).
   - Implement `set_time` for `ot_time` sync.
   - Complexity: Medium-High
   - Depends on: (2)

4) **Offline converter CLI**
   - `opentouch_to_rrd <dataset.touch> <out.rrd>` using `rr.save`.
   - Supports downsampling flags.
   - Complexity: Medium
   - Depends on: (3)

5) **Streaming service**
   - Expose `serve_grpc` / `serve_web_viewer` + data streaming endpoints.
   - Cache converted `.rrd` and reuse when possible.
   - Complexity: Medium-High
   - Depends on: (3)

6) **Reflex UI integration**
   - New page: dataset picker + stream toggles + playback controls.
   - Embed viewer (iframe or JS package).
   - Complexity: Medium
   - Depends on: (5)

7) **Validation + performance checks**
   - Test with sample `.touch` datasets; verify time alignment and stream toggles.
   - Add profiling around image throughput and chunk sizes.
   - Complexity: Medium
   - Depends on: (3)-(6)

---

## 5) Open questions / decisions to confirm
- Preferred viewer mode: native desktop vs web viewer embed?
- Expected dataset sizes (affects downsampling + web viewer viability).
- Should we persist `.rrd` alongside `.touch`, or generate on demand?
- Any additional sensor types in OpenTouch not captured in current repo?
- Target OS + deployment model for the control service?

