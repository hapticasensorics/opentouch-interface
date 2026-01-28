# RERUN_PLAN_B: OpenTouch + Rerun + HapticaGUIPlugin Integration Plan

## Scope and intent
This plan focuses on integrating OpenTouch data with Rerun visualization while keeping HapticaGUIPlugin (Reflex) as the branded web UI. It draws on the existing OpenTouch recording format (.touch HDF5) and the planned Rerun-first architecture from the OpenTouch visualizer plans.

---

## 1) System Architecture

### 1.1 Data flow (end to end)
```
[OpenTouch sensors]                [OpenTouch .touch files]
        |                                   |
        | live streams                      | playback
        v                                   v
OpenTouch Core (TouchSensor + SensorGroupSaver)
        |  (events + timestamps)
        v
Processing / Adapter Layer
  - decode .touch (Decoder)
  - normalize streams
  - map to UIS (Unified Interaction Schema)
        |
        +--------------------+---------------------+
        |                    |                     |
        v                    v                     v
Rerun Logger (SDK)       Metadata/Index        HapticaGUIPlugin
  - time-series logging  (manifest.json)       (Reflex UI)
  - high-freq streams    - clip registry       - dataset browser
  - 3D / timeline         - thumbnails         - metadata, export
        |
        v
Rerun Viewer (native or web)
```

### 1.2 Monolith vs microservices

**Option A: Modular monolith (recommended for MVP)**
- Single Python process for OpenTouch ingestion + Rerun logging + lightweight API.
- Reflex (HapticaGUIPlugin) runs as a separate web process, calls the API.
- Advantages: faster integration, fewer moving parts, easy local dev.
- Tradeoffs: tighter coupling, harder to scale live streaming.

**Option B: Microservices (recommended for scale / multi-user)**
- **Ingest Service**: OpenTouch live capture and .touch ingestion.
- **Processing Service**: Converts data to UIS, derives events, prepares thumbnails.
- **Rerun Service**: Owns Rerun logging, session lifecycle, and viewer launch.
- **GUI Service**: HapticaGUIPlugin (Reflex) for UI and workflows.
- Advantages: isolation, scaling, clearer ownership of data vs UI.
- Tradeoffs: more infra, needs RPC + coordination.

### 1.3 API boundaries (proposed)

**Ingestion API (OpenTouch service)**
- `POST /record/start` -> start live capture
- `POST /record/stop` -> stop and return .touch path
- `GET /datasets` -> list .touch files
- `GET /datasets/{id}/metadata` -> config, sensors, streams

**Processing API (adapter service)**
- `POST /process/{dataset_id}` -> convert to UIS + derived events
- `GET /process/{dataset_id}/manifest` -> manifest.json
- `GET /process/{dataset_id}/preview` -> thumbnails / summary

**Rerun Session API (visualization control plane)**
- `POST /session` -> create session from dataset / clip
- `POST /session/{id}/load` -> load clip (UIS or .rrd)
- `POST /session/{id}/playback` -> play/pause/seek
- `GET /session/{id}/state` -> playback time, selection

**GUI API (HapticaGUIPlugin)**
- consumes the above services
- exposes user actions (export, tagging, saved views)

---

## 2) Rerun Viewer Strategy

### 2.1 Embedded vs standalone

**Standalone viewer (native app)**
- Launch Rerun viewer locally (via SDK spawn or CLI).
- Best performance for 3D and high-frequency streams.
- HapticaGUIPlugin controls the session and shows metadata.
- Interaction model: side-by-side windows.

**Embedded viewer (web)**
- Embed Rerun web viewer inside Reflex UI (iframe or custom component).
- Enables a single branded interface.
- Tradeoff: depends on web viewer performance and feature parity.

### 2.2 Rerun web vs native

**Rerun web (rerun-web)**
- Pros: browser delivery, embed-friendly, shareable URLs.
- Cons: may have limits for high-frequency streams or 3D complexity.

**Rerun native**
- Pros: best performance, full feature set.
- Cons: separate window, harder to brand.

**Recommendation**
- **MVP**: native viewer for stability + Reflex UI for control/metadata.
- **Phase 2**: evaluate rerun-web embedding for a unified branded UI.

### 2.3 User interaction model

**MVP interaction**
- User selects dataset/clip in HapticaGUIPlugin.
- GUI calls Rerun Session API to load the clip.
- Rerun viewer handles playback and timeline; GUI shows metadata and export.

**Enhanced interaction**
- Bidirectional sync: timeline scrubs in Rerun update GUI panels.
- GUI controls (play/pause, annotations) send events to Rerun service.

---

## 3) Feature Division

### 3.1 Rerun responsibilities
- 3D visualization (hand pose, sensor geometry).
- High-frequency streams and time-series logging.
- Timeline UI and scrubbing.
- Multi-stream synchronization.

### 3.2 HapticaGUIPlugin responsibilities
- Dataset browser, search, filters.
- Clip metadata, annotations, and tags.
- Export workflows (CSV, image, RRD).
- Branding, layout, navigation, user workflows.

### 3.3 Shared state synchronization
**Shared state keys**
- `active_dataset_id`
- `active_clip_id`
- `playback_time_s`
- `playback_state` (play/pause)
- `selection` (markers, events, annotations)

**Sync mechanism (recommended)**
- WebSocket for live playback state and selection events.
- REST for dataset and session lifecycle.
- For MVP, a simple polling endpoint is acceptable.

---

## 4) Tech Stack Decisions

### 4.1 Real-time updates
- **Recommended**: WebSocket between GUI and Rerun service for playback state + markers.
- **Fallback**: polling every 250-500ms for MVP.

### 4.2 Data storage and access
- **Source of truth**: OpenTouch `.touch` (HDF5) recordings.
- **Derived**: UIS format + manifest.json for quick browsing.
- **Rerun artifacts**: `.rrd` files for fast reload and sharing.
- **Shared filesystem**: simplest local setup; use an agreed folder layout.

### 4.3 Process communication
- **MVP**: Python subprocess + HTTP (FastAPI/Starlette) for session control.
- **Scale**: separate services with HTTP + WS, optional gRPC for internal calls.

### 4.4 Integration points in code
- Use `opentouch_interface.decoder.Decoder` to read .touch.
- Adapter to UIS (per existing Plan B / Combined Plan).
- Rerun logging service converts UIS to Rerun entities.
- Reflex UI calls session API endpoints.

---

## 5) MVP vs Full Feature Set

### 5.1 MVP (minimum viable integration)
**Goal:** Get a branded UI that can launch a Rerun session for a dataset clip.

- Convert a single .touch file to UIS on demand.
- Spawn native Rerun viewer and log RGB + tactile streams.
- HapticaGUIPlugin UI:
  - dataset list
  - clip details
  - “Open in Rerun” action
- One-way control (GUI -> Rerun). No sync back required.

### 5.2 Phase 2 (incremental upgrades)
- Build a persistent manifest index for datasets and clips.
- Add event markers (contact peaks, slip) from preprocessing.
- Add playback sync (Rerun -> GUI) via WebSocket.
- Allow annotations and export from GUI.

### 5.3 Phase 3 (full feature set)
- Embedded rerun-web viewer inside Reflex UI.
- Multi-clip comparison and alignment modes.
- Session sharing with `.rrd` export or hosted sessions.
- Multi-user access with permissions and project workspaces.

---

## Execution Notes and Open Questions

1. Confirm Rerun viewer embedding options and expected performance for high-frequency tactile streams.
2. Decide whether to keep Streamlit dashboard or fully migrate UI workflows to HapticaGUIPlugin.
3. Define UIS mapping for each sensor type (Digit, Digit360, GelSight Mini).
4. Choose the MVP path (native Rerun viewer vs web embed) based on performance testing.

---

## Proposed File/Service Layout (logical, not implementation)
```
OpenTouch Core (existing)
  - .touch capture
  - Decoder

Visualization Service
  - UIS adapter
  - Rerun logger
  - Session API

HapticaGUIPlugin (Reflex)
  - Dataset browser
  - Metadata panels
  - Export + annotations
  - Rerun session controls
```

