# Plan A — OpenTouch Dataset Visualizer

## 1) Architecture (frameworks/libs)
- **Frontend**: React + TypeScript + Vite (fast dev, strong typing).
- **State & data flow**: Zustand (lightweight global state) or Redux Toolkit if you want time‑travel/debugging; pick one and stick to it.
- **Visualization**:
  - **Video**: native HTML5 video + `hls.js` (if streaming) or direct MP4.
  - **Tactile heatmap**: Canvas 2D for high‑frequency updates (169 taxels) or WebGL via `pixi.js` for smoother scaling.
  - **Charts/timeline**: `d3-scale`/`d3-axis` for precise time mapping; lightweight custom timeline UI.
- **Data parsing**: `papaparse` for CSV, `zod` for schema validation, `dayjs` for time formatting.
- **UI components**: Radix UI + Tailwind (or CSS modules) for clean primitives.
- **Worker**: Web Worker for parsing/decoding large arrays to avoid main‑thread blocking.

## 2) Data loading pipeline
- **Data formats** (assumed):
  - RGB frames/video: MP4 or image sequence.
  - Tactile: per‑frame arrays (169 taxels) in CSV/NPY/JSON.
  - Hand pose: per‑frame joint positions in CSV/JSON.
  - Timestamps: per‑frame (ms) or per‑sample time arrays.
- **Pipeline steps**:
  1. **Dataset manifest**: `clips.json` listing clip id, file paths, fps, duration, modalities present.
  2. **Clip selection** triggers loading of metadata (duration, fps, timestamps).
  3. **Lazy load** video via `<video src>`; load tactile/pose in background.
  4. **Parse tactile/pose** in Web Worker → normalize to `{timeMs, values[], pose[]}` arrays.
  5. **Index map**: build `timeMs -> frameIdx` lookup for sync.
  6. **Cache**: keep last N clips in memory (LRU) for quick compare.

## 3) Visualization components
- **Video Player**
  - Standard play/pause, speed, frame‑step.
  - Exposes current playback time (ms) for sync.
- **Tactile Heatmap**
  - 13x13 grid mapped from 169 taxels.
  - Canvas render loop: update when `timeMs` changes.
  - Color scale: configurable (linear/log).
- **Hand Pose Overlay**
  - Render on top of video (optional) or separate panel.
- **Timeline / Sync Panel**
  - Multi‑track timeline: video, tactile, pose.
  - Scrubber that sets global `timeMs`.
  - Markers for events/clip boundaries.

## 4) Interactive features
- **Scrubbing**: drag scrubber; video seeks and tactile/pose update.
- **Zoom**: timeline zoom (mouse wheel / pinch) + time window selection.
- **Compare clips**: side‑by‑side mode with synchronized time or offset mode.
- **Frame step**: single frame forward/back.
- **Playback speed**: 0.25x–4x.
- **Heatmap tools**: hover to show taxel value; toggle normalization.
- **Export**: capture current frame + tactile snapshot as image/CSV.

## 5) File structure & module breakdown
```
src/
  app/
    App.tsx
    routes.tsx
  components/
    VideoPlayer/
    TactileHeatmap/
    Timeline/
    ClipSelector/
    CompareView/
  data/
    loaders/
      loadManifest.ts
      loadClip.ts
      parseTactileWorker.ts
    models/
      Clip.ts
      TactileFrame.ts
      HandPose.ts
  state/
    usePlayerStore.ts
    useClipStore.ts
  utils/
    time.ts
    math.ts
    color.ts
  workers/
    tactileParser.worker.ts
  styles/
    globals.css
```
- `Clip.ts`: metadata schema, typed ids, fps, duration.
- `loadClip.ts`: fetch + parse tactile/pose.
- `tactileParser.worker.ts`: heavy parsing + normalization.

## 6) Implementation order & dependencies
1. **Project scaffolding**
   - Vite + React + TS, Tailwind/Radix, Zustand.
2. **Data model & manifest**
   - Define `Clip`, `TactileFrame`, `HandPose` types.
   - Implement manifest loader + validation.
3. **Basic player & sync**
   - Build `VideoPlayer` with time callbacks.
   - Create global `timeMs` store.
4. **Tactile heatmap**
   - Canvas grid rendering with dummy data.
   - Hook into `timeMs`.
5. **Data loading pipeline**
   - Implement worker parsing tactile/pose.
   - Map `timeMs` to nearest tactile frame.
6. **Timeline**
   - Render time axis, scrubber, zoom.
7. **Clip selector**
   - List/filter clips, load on selection.
8. **Compare mode**
   - Side‑by‑side video + heatmap, sync options.
9. **Polish & export**
   - Hover tooltips, color scale toggle, export snapshot.

## Dependencies Map
- Timeline depends on global `timeMs` store.
- Heatmap depends on parsed tactile data + `timeMs`.
- Compare view depends on clip loading and sync logic.
- Export depends on heatmap + video canvas composition.
