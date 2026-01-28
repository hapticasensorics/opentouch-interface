# Plan B: OpenTouch Dataset Visualizer

## Goals (different but practical)
- Exploration-first: prioritize fast, tactile event browsing over heavy annotation tools.
- Streaming-native: handle 5.1h / 2,900 clips without preloading (WebDataset + lazy decode).
- Cross-dataset ready: adopt a unified intermediate format so OpenTouch can compare with future datasets.
- Tactile-centric UX: make 169-taxel signals feel spatial and temporal, not just arrays.

---

## 1) Core Architecture (Rerun-first, hybrid pipeline)
1.1 Rerun as the visualization spine
- Use Rerun SDK as the main scene graph and timeline UI.
- Represent each clip as a sequence entity with synchronized streams:
  - rgb/frames (image stream)
  - tactile/pressure (grid or point cloud)
  - hand/pose (skeleton + keypoints)
  - events (contact peaks, slip, grasp transitions)
- Use Rerun time-based logging for synchronized playback.

1.2 WebDataset for large-scale streaming
- Store clips in .tar shards with RGB frames, tactile arrays, pose, metadata.
- Stream from local disk or HTTP without full extraction.
- Build a thin clip loader that yields batched frames aligned by timestamp.

1.3 Unified cross-dataset format
- Define a Unified Interaction Schema (UIS) with:
  - frames.rgb: HxWx3
  - tactile.taxels: (T,169) + taxel_layout (2D mapping)
  - hand.pose: per-timestamp joints with units + reference frames
  - timestamps: canonical t in seconds
- Create adapters for future datasets (OpenTouch now, others later).

---

## 2) Data Processing Pipeline
2.1 Pre-processing (offline, one-time)
- Convert raw data to WebDataset shards:
  - RGB frames as JPEG/PNG
  - tactile arrays as compressed .npy or .npz
  - hand poses as .json or .npz
- Generate manifest.json per shard (clip IDs, durations, stats).
- Precompute derived signals for UI (contact peaks, slip, center of pressure).

2.2 Alignment and time sync
- Normalize all modalities to one timestamp reference.
- Create a time index table per clip so the loader can seek quickly.

2.3 Cross-dataset compatibility layer
- Provide a mapping config file (uis_map.yaml) for dataset-specific transforms.
- Keep dataset adapters minimal; convert into UIS in memory at load.

---

## 3) Visualization Features (Rerun + custom UI)
3.1 Scene panels
- Main Scene: RGB stream + hand pose overlay.
- Tactile Scene: taxel grid rendered as deforming surface or heatmap.
- 3D Hand + Tactile: optional 3D view where taxels project onto glove surface.

3.2 Tactile-centric timeline
- Dedicated tactile heat timeline strip.
- Auto-annotate high-pressure events and show timeline markers.

3.3 Novel UI/UX ideas
- Tactile Sparkline Bar: 169-taxel summary vector as a single bar, draggable over time.
- Contact Lens Mode: show only taxels above a threshold as "contact points" on the hand.
- Force Fingerprints: radial plot per finger for fast cross-clip comparison.
- Clip Similarity Jump: navigate using tactile event embeddings.

---

## 4) Cross-dataset Exploration Modes
- Dual-dataset mode: split view; align two clips by tactile peaks instead of time.
- Normalized metrics panel: compare peak force, duration, contact area across datasets.
- Dataset adapter registry so new datasets can drop in with minimal work.

---

## 5) Implementation Phases
Phase 0: Feasibility and schema
- Define UIS schema + taxel layout.
- Prototype a single clip in Rerun with aligned RGB + tactile.

Phase 1: WebDataset streaming
- Implement shard creation script.
- Build clip loader that streams from local disk.
- Add manifest indexing.

Phase 2: Rerun integration
- Build logging pipeline to push all streams into Rerun.
- Add playback controls + synchronized timeline.

Phase 3: Tactile-centric UX
- Implement tactile heat timeline.
- Add Contact Lens Mode + Force Fingerprints view.

Phase 4: Cross-dataset support
- Add adapter layer + UIS mapping config.
- Build dual-dataset comparison mode.

---

## 6) Technical Stack
- Python: data conversion + WebDataset streaming
- Rerun SDK: core visualization
- Optional Web UI: dashboard to pick clips and launch Rerun session
- Storage: WebDataset shards on local disk or object store

---

## 7) Deliverables
- uis_schema.md
- convert_to_webdataset.py
- opentouch_rerun_viewer.py
- manifest.json per shard
- README with instructions + example clip

---

## 8) Risks and Mitigations
- Large data throughput -> streaming + decode caching
- Tactile layout accuracy -> validate mapping with glove specs
- Time alignment -> per-clip time index tables
- UX overload -> keep tactile modes optional and lightweight

---

## 9) Validation
- Play 5 random clips, confirm RGB/tactile/pose sync within +/- 1 frame.
- Confirm tactile peak detection matches qualitative events.
- Compare two clips side-by-side for consistent tactile mapping.
