# Combined Plan: OpenTouch Dataset Visualizer

This plan synthesizes the best elements from Plan A (React/TypeScript web-first) and Plan B (Rerun/Python data-first), creating a hybrid architecture that leverages each approach's strengths.

---

## Design Philosophy

**From Plan A:** Web-based UI for accessibility, modern React patterns, strong typing
**From Plan B:** Rerun for heavy 3D/timeline visualization, WebDataset for streaming at scale, cross-dataset thinking

**Combined Approach:** A Python backend using Rerun for core visualization + WebDataset streaming, with an optional lightweight web dashboard for clip selection and session management. This gets the best of both worlds: Rerun's powerful synchronized timeline and 3D rendering, plus web accessibility for browsing/launching.

---

## 1) Architecture

### 1.1 Core Visualization: Rerun SDK (from Plan B)
Rerun provides battle-tested synchronized timeline playback, 3D rendering, and multi-stream visualization out of the box. Building this from scratch in React would duplicate significant effort.

- Use Rerun as the primary visualization engine
- Each clip represented as a sequence entity with synchronized streams:
  - `rgb/frames` (image stream)
  - `tactile/pressure` (13x13 grid heatmap or point cloud)
  - `hand/pose` (skeleton + keypoints)
  - `events` (contact peaks, slip, grasp transitions)

### 1.2 Data Layer: WebDataset + Manifest (hybrid)
**From Plan B:** WebDataset for streaming large datasets without preloading
**From Plan A:** JSON manifest concept for clip metadata

- Store clips in `.tar` shards with RGB frames, tactile arrays, pose, metadata
- Generate `manifest.json` per shard listing clip IDs, durations, fps, modalities
- Stream from local disk or HTTP without full extraction
- Build time index tables per clip for fast seeking

### 1.3 Optional Web Dashboard (from Plan A concepts)
A lightweight React app for:
- Browsing/filtering clips from the manifest
- Launching Rerun sessions for selected clips
- Managing clip comparisons

**Stack:** React + TypeScript + Vite + Tailwind (minimal, just for navigation)

### 1.4 State Management (hybrid)
- **Rerun side:** Rerun handles timeline state, playback position, synchronized streams
- **Web side (if used):** Zustand for lightweight clip selection state

---

## 2) Unified Data Schema (from Plan B, enhanced)

### 2.1 Unified Interaction Schema (UIS)
Critical for cross-dataset compatibility and clean data contracts:

```yaml
frames:
  rgb: HxWx3 (JPEG/PNG per frame)
tactile:
  taxels: (T, 169) float32
  taxel_layout: 13x13 2D mapping specification
  units: "pressure_normalized" | "raw_adc"
hand:
  pose: per-timestamp joint positions
  reference_frame: "wrist" | "world"
  units: "meters"
timestamps:
  t: float64 seconds (canonical reference)
metadata:
  clip_id: string
  duration_s: float
  fps: int
  modalities: ["rgb", "tactile", "pose"]
```

### 2.2 Dataset Adapters
- `uis_map.yaml` configuration for dataset-specific transforms
- Minimal adapters that convert to UIS in memory at load time
- OpenTouch adapter first, extensible for future datasets

---

## 3) Data Processing Pipeline

### 3.1 Pre-processing (offline, one-time)
**From Plan B:** WebDataset shard creation

```
convert_to_webdataset.py
  - RGB frames -> JPEG/PNG in .tar shards
  - Tactile arrays -> compressed .npy/.npz
  - Hand poses -> .json or .npz
  - Generate manifest.json per shard
  - Precompute derived signals (contact peaks, slip, center of pressure)
```

### 3.2 Time Synchronization (hybrid)
**From Plan A:** `timeMs -> frameIdx` lookup maps
**From Plan B:** Time index tables per clip

- Normalize all modalities to one timestamp reference
- Create bidirectional index: `timestamp <-> frame_index` for each modality
- Support variable frame rates across modalities

### 3.3 Runtime Loading
**From Plan A:** Web Worker concept for non-blocking parsing
**From Plan B:** Streaming decode

- Python async clip loader yields batched frames aligned by timestamp
- Lazy decode: only decode frames as they enter the visible time window
- LRU cache for recently accessed clips

---

## 4) Visualization Components

### 4.1 Main Panels (Rerun-based, from Plan B)
- **RGB Scene:** Video stream with optional hand pose overlay
- **Tactile Heatmap:** 13x13 grid rendered as heatmap or deforming surface
- **3D Hand + Tactile:** Optional view projecting taxels onto glove surface mesh
- **Timeline:** Rerun's built-in multi-track timeline with scrubbing

### 4.2 Tactile-Centric Features (from Plan B - novel ideas)
- **Tactile Heat Timeline Strip:** Dedicated tactile summary over time
- **Contact Lens Mode:** Show only taxels above threshold as "contact points"
- **Force Fingerprints:** Radial plot per finger for cross-clip comparison
- **Clip Similarity Jump:** Navigate using tactile event embeddings

### 4.3 Heatmap Configuration (from Plan A)
- Configurable color scale (linear/log, custom palettes)
- Hover to show individual taxel values
- Toggle normalization modes

---

## 5) Interactive Features

### 5.1 Core Playback (hybrid)
**From Plan A:** Frame-step, speed control
**From Plan B:** Rerun's synchronized playback

- Play/pause with keyboard shortcuts
- Frame step: single frame forward/back
- Playback speed: 0.25x to 4x
- Scrubbing via timeline drag

### 5.2 Comparison Mode (from Plan A, enhanced by Plan B)
**From Plan A:** Side-by-side synchronized view
**From Plan B:** Align by tactile peaks instead of just time

- **Time-sync mode:** Two clips aligned by timestamp
- **Event-sync mode:** Align clips by tactile peaks/events (novel from Plan B)
- **Offset mode:** Manual time offset adjustment

### 5.3 Zoom & Navigation (from Plan A)
- Timeline zoom (mouse wheel / pinch)
- Time window selection
- Markers for events/clip boundaries

### 5.4 Export (from Plan A)
- Capture current frame + tactile snapshot as image
- Export tactile data slice as CSV
- Export Rerun session for sharing

---

## 6) File Structure

```
opentouch-visualizer/
  # Python core
  src/
    data/
      webdataset_loader.py      # Streaming loader
      uis_schema.py             # Unified schema definitions
      adapters/
        opentouch_adapter.py    # OpenTouch -> UIS conversion
    visualization/
      rerun_viewer.py           # Main Rerun visualization
      tactile_renderer.py       # Heatmap + sparkline rendering
      comparison_mode.py        # Dual-clip comparison
    preprocessing/
      convert_to_webdataset.py  # Shard creation
      compute_events.py         # Contact peaks, slip detection
    config/
      uis_map.yaml              # Dataset-specific mappings

  # Optional web dashboard
  web/
    src/
      App.tsx
      components/
        ClipBrowser/
        SessionLauncher/
      state/
        useClipStore.ts

  # Data & outputs
  data/
    shards/                     # WebDataset .tar files
    manifests/                  # Per-shard manifest.json

  # Documentation
  docs/
    uis_schema.md
    README.md
```

---

## 7) Implementation Phases

### Phase 0: Foundation (Week 1)
**From Plan B:** Schema-first approach

- [ ] Define UIS schema (`uis_schema.py`, `uis_schema.md`)
- [ ] Define taxel layout specification (13x13 mapping)
- [ ] Prototype single clip in Rerun with aligned RGB + tactile

### Phase 1: Data Pipeline (Week 2)
**From Plan B:** WebDataset streaming

- [ ] Implement `convert_to_webdataset.py`
- [ ] Build clip loader with streaming decode
- [ ] Generate manifests for test dataset subset
- [ ] Validate time synchronization

### Phase 2: Core Visualization (Week 3)
**Hybrid:** Rerun + heatmap features from Plan A

- [ ] Build Rerun logging pipeline for all streams
- [ ] Implement tactile heatmap with configurable color scales
- [ ] Add hand pose overlay
- [ ] Verify sync within +/- 1 frame

### Phase 3: Interactive Features (Week 4)
**From Plan A:** Playback controls and comparison

- [ ] Frame step, speed control
- [ ] Timeline zoom and scrubbing
- [ ] Comparison mode (time-sync)

### Phase 4: Tactile-Centric UX (Week 5)
**From Plan B:** Novel visualization ideas

- [ ] Tactile heat timeline strip
- [ ] Contact Lens Mode
- [ ] Force Fingerprints view
- [ ] Event-sync comparison mode

### Phase 5: Polish & Cross-Dataset (Week 6)
**Hybrid:** Export from Plan A, adapters from Plan B

- [ ] Export functionality (images, CSV, Rerun sessions)
- [ ] Dataset adapter layer
- [ ] Optional web dashboard for clip browsing
- [ ] Documentation and examples

---

## 8) Technical Stack Summary

| Component | Choice | Source |
|-----------|--------|--------|
| Core visualization | Rerun SDK | Plan B |
| Data streaming | WebDataset | Plan B |
| Schema validation | Pydantic + zod | Hybrid |
| Heatmap rendering | Rerun + custom | Hybrid |
| Timeline | Rerun built-in | Plan B |
| Web dashboard (optional) | React + Vite + Zustand | Plan A |
| Preprocessing | Python scripts | Plan B |

---

## 9) Risks & Mitigations

| Risk | Mitigation | Source |
|------|------------|--------|
| Large data throughput | WebDataset streaming + decode caching | Plan B |
| Tactile layout accuracy | Validate mapping against glove specs | Plan B |
| Time alignment drift | Per-clip time index tables | Plan B |
| UX complexity | Keep tactile modes optional/toggleable | Plan B |
| Main thread blocking | Async loading, lazy decode | Plan A |
| Cross-dataset inconsistency | Strict UIS schema + adapters | Plan B |

---

## 10) Validation Criteria

- [ ] Play 5 random clips, confirm RGB/tactile/pose sync within +/- 1 frame
- [ ] Tactile peak detection matches qualitative contact events
- [ ] Compare two clips side-by-side with consistent tactile mapping
- [ ] Stream 100+ clips without memory issues
- [ ] Export captures accurate snapshot of current state

---

## Attribution: What Came From Each Plan

### From Plan A (React/Web-first)
- Zustand for lightweight state management
- JSON manifest concept (`clips.json`)
- Detailed file structure organization
- Configurable color scales for heatmap
- Export functionality (image/CSV snapshots)
- Frame step and playback speed controls
- LRU cache for clip memory management
- Web Worker concept for non-blocking parsing

### From Plan B (Rerun/Python-first)
- Rerun SDK as core visualization engine
- WebDataset for large-scale streaming
- Unified Interaction Schema (UIS) for cross-dataset compatibility
- Time index tables for fast seeking
- Novel tactile UX ideas (Sparkline Bar, Contact Lens Mode, Force Fingerprints)
- Event-sync comparison mode (align by tactile peaks)
- Pre-computed derived signals (contact peaks, slip detection)
- Dataset adapter architecture

### Combined/Enhanced
- Hybrid architecture: Rerun core + optional web dashboard
- Bidirectional time index maps
- Dual comparison modes (time-sync and event-sync)
- Phased implementation that validates early and adds features incrementally
