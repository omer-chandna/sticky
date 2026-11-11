# Sticky implementation plan

The repository root is the monorepo. Processing was implemented and tested before the studio was wired to it.

## Decisions

- Classical computer vision is the default path: OpenCV geometry, a surface-color mask, GrabCut when contrast is low, Pillow/OpenCV restoration, and VTracer 0.6.11 for real vectors.
- No generative model and no hosted AI API. `rembg` is an optional backend, disabled, and not installed.
- Coordinates that cross the API are normalized to the current image.
- Restore always starts from the original upload or from the prepared crop of that upload. Sliders do not restack filters.
- Interactive calls use a preview resolution. Downloads reprocess from the restored artwork at the requested physical size and DPI.
- Photos live in temporary server storage with a TTL. The browser stores settings and artifact ids.
- Physical size is what the user types.
- Hybrid SVGs are labeled as embedded raster. Vector mode contains paths only.
- Sheet packing is bounding-box shelf packing. Placement is in millimetres. PDFs use real page sizes.
- Illumination leveling uses a clamped division by blurred luminance. CLAHE increased variance on smooth ramps, so it is not the control behind “level lighting.”

## Status

- Pipeline, API, studio, collection flow, sheet builder, Docker, and tests are in the tree.
- Example photographs are generated, not scraped.
- Browser checks of upload, restore, vector export, and PDF are part of the latest pass. See the README for anything that is still a limit rather than a missing control.
