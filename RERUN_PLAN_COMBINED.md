# Combined Plan: OpenTouch + Rerun + HapticaGUIPlugin Integration

*Synthesized from Plan A (data formats, Rerun mapping) and Plan B (architecture, MVP phasing)*

---

## Executive Summary

This integration creates a visualization pipeline for OpenTouch tactile datasets using Rerun for high-performance data visualization and HapticaGUIPlugin (Reflex) for web-based dataset browsing and control.

**Key decisions:**
- MVP uses native Rerun viewer (best performance) + Reflex web UI for controls
- Modular monolith architecture for fast iteration
- Offline `.touch` → `.rrd` conversion as primary ingestion mode
- WebSocket for playback state sync in Phase 2

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenTouch Data Layer                         │
│  .touch files (HDF5): sensor_chunks, config, timestamps         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Service                            │
│  - Decoder (stream chunk iterator)                               │
│  - Rerun Mapper (archetype conversion)                           │
│  - CLI: opentouch_to_rrd <input.touch> <output.rrd>             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌─────────────────────┐
│   Rerun Viewer   │ │  .rrd Files  │ │  HapticaGUIPlugin   │
│   (native app)   │ │   (cache)    │ │   (Reflex web UI)   │
│                  │ └──────────────┘ │                     │
│ • 3D viz         │                  │ • Dataset browser   │
│ • Timeline       │◄────────────────►│ • Stream toggles    │
│ • Time scrub     │   Session API    │ • Metadata/export   │
│ • Multi-stream   │                  │ • Playback controls │
└──────────────────┘                  └─────────────────────┘
```

---

## Three Implementation Workstreams

### Workstream 1: Rerun Data Pipeline
**Owner: Agent 1**
**Goal:** Load .touch files and convert to Rerun format

**Tasks:**
1. Create streaming decoder iterator over HDF5 chunks
2. Implement entity path hierarchy: `sensors/<name>/<stream>`
3. Handle binary unpacking for each stream type:
   - Camera: `(H,W,C) uint8` → `rr.Image`
   - Serial/pressure: protobuf → `rr.Scalars`
   - IMU: packed struct → `rr.Scalars` (raw, euler, quat)
   - Audio: int16 chunks → `rr.Tensor`
4. Set timeline: `rr.set_time_seconds("ot_time", delta)`
5. Create CLI: `opentouch_to_rrd <input> <output>`

**Output files:**
- `opentouch_interface/rerun/decoder_stream.py`
- `opentouch_interface/rerun/cli.py`

---

### Workstream 2: Rerun Visualization & Session Control
**Owner: Agent 2**
**Goal:** Configure Rerun viewer layouts and create session API

**Tasks:**
1. Define default viewer layout (camera views, scalar plots)
2. Implement session service with endpoints:
   - `POST /sessions` → start viewer, return session ID
   - `POST /sessions/{id}/load` → load .rrd file
   - `GET /sessions/{id}/state` → playback time, status
3. Add spawn/connect modes for native viewer
4. Create downsampling options (image stride, audio decimation)
5. Add `.rrd` caching to avoid re-conversion

**Output files:**
- `opentouch_interface/rerun/session_service.py`
- `opentouch_interface/rerun/viewer_config.py`

---

### Workstream 3: HapticaGUIPlugin Integration
**Owner: Agent 3**
**Goal:** Build Reflex UI for dataset browsing and Rerun control

**Tasks:**
1. Create dataset browser page:
   - List `.touch` files from `./datasets/`
   - Show metadata (sensors, streams, duration)
   - Thumbnail previews (first frame)
2. Add stream toggle controls (enable/disable sensors)
3. Add "Open in Rerun" button → calls session API
4. Add export options (CSV for scalars, .rrd download)
5. Wire up playback controls (play/pause, seek)

**Output files:**
- `HapticaGUIPlugin/src/haptica_reflex_scaffold/pages/dataset_browser.py`
- `HapticaGUIPlugin/src/haptica_reflex_scaffold/components/rerun_controls.py`

---

## Dependencies Between Workstreams

```
Workstream 1 (Data Pipeline)
     │
     ├──► Workstream 2 (Session Service) ◄── can start in parallel
     │           │
     │           ▼
     └─────► Workstream 3 (GUI) ◄── needs session API endpoints
```

- Agent 1 and 2 can work in parallel initially
- Agent 3 needs session API stub from Agent 2 to wire up controls
- All agents converge for integration testing

---

## MVP Scope (Phase 1)

**Included:**
- Convert single .touch → .rrd on demand
- Launch native Rerun viewer with camera + tactile streams
- Dataset list in Reflex UI
- "Open in Rerun" action
- One-way control (GUI → Rerun)

**Excluded (Phase 2+):**
- Embedded web viewer
- Bidirectional sync (Rerun → GUI)
- Annotations and tagging
- Multi-dataset comparison

---

## Data Format Quick Reference

### .touch File Structure (HDF5)
- `sensor_chunks`: varlen uint8 array (packed binary)
- `chunk_start_times`, `chunk_end_times`: float64 arrays
- `config`: JSON string with sensor list and metadata

### Supported Sensors
| Sensor | Streams | Rate |
|--------|---------|------|
| Digit | camera | 30 Hz |
| GelSight Mini | camera | 30 Hz |
| Digit360 | camera, serial, audio | 30/100/10 Hz |

### Rerun Archetype Mapping
| Stream | Archetype |
|--------|-----------|
| camera | `rr.Image` |
| serial/pressure | `rr.Scalars` |
| serial/imu | `rr.Scalars` (multiple channels) |
| audio | `rr.Tensor` |

---

## Open Questions
1. Preferred viewer mode: native vs web embed? → **MVP: native**
2. Persist .rrd alongside .touch? → **Yes, cache for fast reload**
3. Target OS? → **macOS primary, Linux for server**
