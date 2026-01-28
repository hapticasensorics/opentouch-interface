# OpenTouch Visualizer Implementation Summary

This document summarizes the outputs from two parallel Codex CLI implementations for the OpenTouch dataset visualizer.

## Overview

Both implementations operated in a read-only sandbox environment and could not directly modify files. Instead, they produced comprehensive patches and instructions for manual application.

---

## Implementer A: Rerun Visualization Pipeline

**Thread ID:** `019c0275-0203-7722-aa0a-477e101b5f8d`

### Focus
Core visualization using Rerun SDK with tactile heatmap rendering and demo capabilities.

### Proposed Files to Create

| File Path | Description |
|-----------|-------------|
| `src/opentouch_visualizer/__init__.py` | Package exports: ClipData, RerunVisualizer, generate_mock_clip |
| `src/opentouch_visualizer/data.py` | ClipData dataclass with validation for frames and tactile arrays |
| `src/opentouch_visualizer/tactile.py` | Tactile heatmap utilities: to_grid, normalize, colormap_blue_red, TactileHeatmapRenderer |
| `src/opentouch_visualizer/mock_data.py` | generate_mock_clip() function for synthetic test data |
| `src/opentouch_visualizer/rerun_visualizer.py` | RerunVisualizer class with timeline logging |
| `src/opentouch_visualizer/demo.py` | CLI demo script with argparse |
| `src/opentouch_interface/version.py` | Dynamic version computation from GITHUB_REF |
| `pyproject.toml` | Modern Python packaging with uv support |
| `tests/test_mock_data.py` | Test for mock data shape validation |
| `tests/test_tactile_renderer.py` | Test for heatmap rendering |

### Setup Changes Required
1. Create `src/` directory layout
2. Move existing packages: `git mv opentouch src/opentouch` and `git mv opentouch_interface src/opentouch_interface`
3. Update `setup.py` to use `find_packages("src")` with `package_dir={"": "src"}`
4. Add `rerun-sdk` to dependencies

### How to Run
```bash
# Install with dev dependencies
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest -q

# Run the visualizer demo
uv run python -m opentouch_visualizer.demo
uv run python -m opentouch_visualizer.demo --no-spawn  # headless
```

---

## Implementer B: Data Loading + WebDataset

**Thread ID:** `019c0275-158c-7610-9098-b59eda6e9e07`

### Focus
Unified Interaction Schema (UIS), WebDataset streaming loader, adapters, and CLI.

### Proposed Files to Create

| File Path | Description |
|-----------|-------------|
| `opentouch_interface/visualizer/__init__.py` | Package exports for UIS schema classes |
| `opentouch_interface/visualizer/data/__init__.py` | Data module exports |
| `opentouch_interface/visualizer/data/uis_schema.py` | Full UIS dataclasses: TaxelLayout, TactileData, HandPose, EventSeries, RGBStream, ClipMetadata, TimeIndex, UISClip |
| `opentouch_interface/visualizer/data/manifest.py` | Manifest loading (JSON/JSONL support) |
| `opentouch_interface/visualizer/data/webdataset_loader.py` | WebDatasetClipLoader with LRU caching |
| `opentouch_interface/visualizer/data/adapters/base.py` | UISAdapter protocol |
| `opentouch_interface/visualizer/data/adapters/__init__.py` | Adapter exports |
| `opentouch_interface/visualizer/data/adapters/opentouch_adapter.py` | OpenTouchAdapter with frame readers (video, encoded sequences) |
| `opentouch_interface/visualizer/data/opentouch_loader.py` | OpenTouchDirectoryLoader for local datasets |
| `opentouch_interface/visualizer/data/mock.py` | make_mock_clip() for synthetic UISClip data |
| `opentouch_interface/visualizer/runner.py` | Viewer launcher stub (calls rerun_viewer) |
| `opentouch_interface/visualizer/cli.py` | Full CLI with --manifest, --shards, --mock, --dry-run options |

### Setup Changes Required
1. Add `webdataset` to dependencies in `setup.py`
2. Add CLI entrypoint: `opentouch-visualizer = opentouch_interface.visualizer.cli:main`

### How to Run
```bash
# Install
uv pip install -e .

# Quick smoke test with mock data
opentouch-visualizer --mock --dry-run
opentouch-visualizer --mock

# Load from WebDataset shards
opentouch-visualizer --shards /path/to/shards/*.tar --manifest manifest.json

# Load from directory
opentouch-visualizer --dir /path/to/clips --clip-id my_clip
```

---

## Conflicts and Coordination Required

### Overlapping Functionality
1. **Mock Data Generation**: Both implementations provide mock clip generation
   - Implementer A: `opentouch_visualizer.mock_data.generate_mock_clip()` returns `ClipData`
   - Implementer B: `opentouch_interface.visualizer.data.mock.make_mock_clip()` returns `UISClip`

2. **Data Schemas**: Different but compatible approaches
   - Implementer A: Simple `ClipData` dataclass with frames + tactile arrays
   - Implementer B: Full UIS with `UISClip`, `RGBStream`, `TactileData`, etc.

### Integration Points
- Implementer B's CLI calls `opentouch_interface.visualizer.rerun_viewer.launch_clip(clip)`
- Implementer A's `RerunVisualizer` should be adapted to accept UISClip or provide this interface
- **Recommendation**: Create a thin adapter in `rerun_viewer.py` that converts UISClip to ClipData

### Package Structure Options
1. **Option A**: Use Implementer A's `src/` layout with a new top-level `opentouch_visualizer` package
2. **Option B**: Place visualizer under `opentouch_interface/visualizer/` as Implementer B proposed
3. **Option C (Recommended)**: Combine both - use `src/` layout but place code under `opentouch_interface/visualizer/`

---

## Test Results

Neither implementation could run tests in the read-only sandbox. Tests should be run after applying the patches:

```bash
# After applying patches
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
```

Expected tests:
- `test_mock_data.py`: Validates mock clip shapes
- `test_tactile_renderer.py`: Validates heatmap rendering produces (13, 13, 3) uint8 output

---

## Next Steps

1. **Apply Patches**: Choose which package structure to use and apply the relevant patches
2. **Resolve Schema Differences**: Decide whether to use ClipData, UISClip, or both
3. **Integration**: Connect Implementer B's CLI to Implementer A's RerunVisualizer
4. **Dependencies**: Add to setup.py:
   - `rerun-sdk` (for visualization)
   - `webdataset` (for streaming)
5. **Testing**: Run the test suite after installation
6. **Documentation**: Update README.md with visualizer usage instructions

---

## Usage Token Summary

| Implementer | Input Tokens | Output Tokens | Cached |
|-------------|-------------|---------------|--------|
| A (Rerun)   | 321,107     | 35,095        | 272,256 |
| B (Data)    | 209,634     | 38,684        | 188,928 |

---

## Files Modified vs Created

### Modified Files (patches needed)
- `setup.py` - Add dependencies and entrypoints

### New Files (both implementations combined)
- ~15 Python modules for visualization
- `pyproject.toml` for modern packaging
- 2 test files

---

*Generated by Claude Code monitoring two parallel Codex CLI sessions*
