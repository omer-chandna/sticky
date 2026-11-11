# Architecture

Sticky is a monorepo. The repository root is the project.

```
apps/web                 Next.js studio and landing page
services/api/app         FastAPI plus the processing library
  processing/            detect, rectify, segment, restore, cutline, pipeline
  segmentation/          OpenCV backend and optional rembg backend
  vectorization/         VTracer, fidelity score, SVG sanitizer
  exports/               PNG/SVG appearance, sheet packing, PDF, ZIP
packages/shared          TypeScript types and millimetre helpers
examples/                Original sample generator
```

## Coordinates

The browser and the API exchange points as fractions of the current image, origin at the top left. After a crop or a perspective warp, later steps use the new image. The pipeline returns a `prepared` image (the cropped or rectified RGB, before color adjustments) so slider changes do not re-warp and do not stack filters on a previous filtered result.

## Stages

`StickerPipeline` is the reuse point for a future CLI or desktop app.

| Stage | What it does | Deterministic |
| --- | --- | --- |
| Detect | Border color model plus local contrast, then contours | Yes |
| Rectify | Homography from four corners, output size from the edge lengths | Yes |
| Segment | Surface-color mask, hole test, GrabCut if contrast is low | Yes, for the same pixels |
| Restore | Gray-world blend, exposure, bilateral denoise, limited unsharp, optional illumination leveling | Yes |
| Vectorize | VTracer 0.6 `convert_raw_image_to_svg` | Yes, for the same image and parameters |
| Cutline | External contour of the alpha mask, optional holes and offset | Yes |
| Export | Physical size, border, PDF page size in points | Yes |

Detection downscales to 1000 px. Interactive restore downscales to `STICKY_PREVIEW_MAX_DIMENSION`. Exports can request the final limit. Results are cached per upload by a hash of the parameters.

Jobs record the stage they actually enter (`correcting perspective`, `removing background`, `cleaning image`, `vectorizing artwork`, `preparing export`). There is no synthetic percent complete. Cancel takes effect between stages.

## Segmentation

The OpenCV backend samples the color outside the selection (or the photo border when there is no selection). Pixels unlike that surface stay opaque, including white ink. Enclosed pixels that match the surface stay transparent, which keeps a die-cut hole. A loose rectangle around a sticker therefore does not have to be perfect: the padding that still looks like the laptop is dropped, and the white interior is kept.

GrabCut is the fallback when the sticker and the surface are hard to tell apart. If that also fails, the geometric selection is kept and the response says to use the brush.

`RembgSegmenter` implements the same `segment()` shape and is not used unless `STICKY_ENABLE_REMBG=true` and the `rembg` package is installed. Sticky does not download those weights. See the license note below.

## Restoration limits

Cleanup maps to a mild bilateral filter, not a full repaint. Sharpness is an unsharp mask with a gain cap. White balance is gray-world, blended and clamped so a genuinely warm sticker is not forced to gray. Illumination leveling divides by a blurred luminance field and keeps the result only when it actually flattens the lighting. CLAHE was tried on smooth ramps and increased local variance, so it is not the method behind the “level lighting” switch.

Blur (low Laplacian variance on the foreground) and glare (a high share of near-white pixels) produce warnings. Nothing is inpainted.

## Vectors

VTracer 0.6.11 is called as `convert_raw_image_to_svg(..., img_format="png")`. Presets map onto its real parameters (`color_precision`, `layer_difference`, `filter_speckle`, `corner_threshold`, `length_threshold`, `path_precision`, `colormode`, `hierarchical=cutout`). Cutout paths do not depend on stacking order, so shapes stay editable. Transparent pixels are not traced. The SVG is parsed with defusedxml and stripped of scripts and external links.

Fidelity is `1 - mean absolute RGB error`, weighted by how well the opaque regions overlap, after CairoSVG rasterizes the SVG. Below 0.86, the API sets `recommend_faithful`. Hybrid SVGs set `data-sticky-mode="hybrid"` and a description that says the artwork is an embedded PNG.

## Sheets

Page sizes are Letter (215.9 × 279.4 mm) and A4 (210 × 297 mm), portrait or landscape. Packing is a shelf algorithm on each sticker’s occupied bounding box, which already includes border and rotation. Manual positions are rejected when they cross the margin or overlap, unless overlap is explicitly allowed. The PDF page box is that size in points. A footer says to print at actual size when the margin has room. An optional 10 mm square requires a margin of at least 14 mm so it sits in the margin.

## Persistence

The API stores one folder per upload under `STICKY_DATA_DIR`: the orientation-corrected original, artifacts, and a parameter cache. Ids are random 128-bit hex strings. Responses never include filesystem paths. A cleanup thread deletes folders older than the TTL.

The browser stores the project (ids, outlines, slider values, sheet positions) in `localStorage` under `sticky-project-v1`. Image bytes stay on the API. If the TTL has passed, the studio asks for the photo again.

## Models and licenses

| Component | Used by default | License notes |
| --- | --- | --- |
| OpenCV, NumPy, Pillow, FastAPI, ReportLab, VTracer | Yes | Library licenses. No downloaded weights. |
| CairoSVG | Yes, to score vectors | Cairo is a system library (LGPL / MPL for Cairo). |
| rembg + a segmentation checkpoint | No | The rembg package is MIT. The commonly used `u2net`, `u2netp`, and `isnet-general-use` weights are distributed by their authors under Apache-2.0. Confirm the checkpoint you select before enabling it. `u2net` is about 170 MB. `u2netp` is the smaller default if you turn the backend on (`REMBG_MODEL`). CPU is enough. GPU is not required and not assumed. |
| Generative restoration | Not implemented | `Segmenter` is the extension point for another local segmenter. A generative inpainter would be a separate, explicit opt-in and would have to show the original next to any synthesized pixels. There is no provider SDK in this repository. |

## Security

Uploads are limited by byte size and pixel count. Pillow’s decompression-bomb guard is set from `STICKY_MAX_MEGAPIXELS`. The decoder, not the filename, decides whether the file is an image. SVG responses are sanitized and, when served for preview, get `Content-Security-Policy: sandbox`. The web app previews SVG and PNG responses as images, which do not run scripts.
