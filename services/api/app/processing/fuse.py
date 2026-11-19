"""Combine several photos of the same flat surface into one cleaner image.

A laptop lid is flat, so every photo of it relates to every other by a
homography. Several close photos therefore give more pixels per sticker than
one photo of the whole lid, and stacking overlapping views removes what a
single photo cannot:

- Random camera grain averages out, so detail survives without heavy denoising.
- Glare moves when the camera angle changes, so a per-pixel median drops it.

Steps:
1. SIFT features on a reduced copy of each photo; pairs are matched with a
   ratio test and RANSAC homographies.
2. The best-connected photo is the reference. Every other photo is placed
   through the strongest chain of matches to it.
3. Exposure differences are evened out with a per-photo colour gain.
4. The canvas uses the finest pixel density among the photos (capped by the
   upload pixel limit) so close-up detail is not thrown away.
5. Canvas tiles are fused independently: each photo is warped in, aligned to
   the tile's sharpest photo with dense optical flow to fix residual drift,
   and the median of the aligned photos is kept. Near-white pixels that other
   photos see as darker are treated as glare and left out of the median.

Nothing is generated: every output pixel is a median of real photo pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

Progress = Callable[[str], None]


@dataclass
class FuseConfig:
    match_dimension: int = 1600
    max_pixels: int = 40_000_000
    tile: int = 768
    margin: int = 48
    overlap: int = 32  # feathered strip shared with the left and top neighbour tiles
    min_inliers: int = 30
    min_coverage: float = 0.2  # share of a tile a photo must cover to vote there
    detail_ratio: float = 0.6  # photos coarser than this share of the tile's best do not vote
    max_flow: float = 10.0  # residual misalignment (canvas px) beyond which a photo is skipped in a tile
    glare_level: float = 245.0


@dataclass
class FuseResult:
    image: np.ndarray
    used: list[int]
    dropped: list[int]
    reference: int
    scale: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Photo:
    index: int
    rgb: np.ndarray
    small_scale: float  # small px per full px
    points: np.ndarray  # keypoints in small coordinates
    descriptors: np.ndarray | None


def fuse_photos(images: list[np.ndarray], config: FuseConfig | None = None, progress: Progress | None = None) -> FuseResult:
    config = config or FuseConfig()
    report = progress or (lambda _stage: None)
    if len(images) < 2:
        raise ValueError("Combining needs at least two photos.")

    report("matching photos")
    photos = [_describe(i, _rgb(image), config) for i, image in enumerate(images)]
    edges, matches = _match_all(photos, config)
    reference, to_ref = _place(len(photos), edges)
    to_ref = _refine(to_ref, reference, matches)
    used = sorted(to_ref)
    dropped = [p.index for p in photos if p.index not in to_ref]
    warnings: list[str] = []
    if dropped:
        names = ", ".join(str(i + 1) for i in dropped)
        warnings.append(
            f"Photo {names} did not overlap the others enough to line up, so it was left out. "
            "Take photos that each share about a third of their view with another photo."
        )
    if len(used) < 2:
        raise ValueError(
            "These photos could not be lined up with each other. Take overlapping photos of the same stickers, "
            "keeping the phone at a similar distance."
        )

    gains = _exposure_gains(photos, to_ref, reference)
    density = {i: _density(to_ref[i], photos[i].rgb.shape) for i in used}
    canvas, scale, capped = _canvas(photos, to_ref, density, config)
    if capped:
        warnings.append(
            "The combined photo was reduced to stay within the upload pixel limit. "
            "Combine fewer or closer-together photos to keep every pixel."
        )
    width, height, origin = canvas
    to_canvas = {
        i: np.array([[scale, 0, -origin[0] * scale], [0, scale, -origin[1] * scale], [0, 0, 1]]) @ to_ref[i] for i in used
    }
    detail = {i: min(1.0, density[i] / scale) for i in used}
    footprints = {i: _footprint(to_canvas[i], photos[i].rgb.shape) for i in used}
    masks = {i: np.full(photos[i].rgb.shape[:2], 255, np.uint8) for i in used}
    priority = sorted(used, key=lambda i: (-detail[i], i))

    report("combining photos")
    output = np.zeros((height, width, 3), np.uint8)
    covered = np.zeros((height, width), bool)
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    m, overlap = config.margin, min(config.overlap, config.margin)
    for ty in range(0, height, config.tile):
        for tx in range(0, width, config.tile):
            fused, valid = _fuse_tile(
                tx, ty, width, height, photos, to_canvas, masks, footprints, gains, detail, priority, flow, config
            )
            tw, th = min(config.tile, width - tx), min(config.tile, height - ty)
            # Each tile also covers a strip of its left and top neighbours and fades in across it,
            # so small differences between neighbouring tiles do not show as a seam.
            left, top = (overlap if tx > 0 else 0), (overlap if ty > 0 else 0)
            region = fused[m - top : m + th, m - left : m + tw].astype(np.float32)
            region_valid = valid[m - top : m + th, m - left : m + tw]
            ramp_x = np.ones(left + tw, np.float32)
            ramp_y = np.ones(top + th, np.float32)
            ramp_x[:left] = np.linspace(0, 1, left + 2, dtype=np.float32)[1:-1]
            ramp_y[:top] = np.linspace(0, 1, top + 2, dtype=np.float32)[1:-1]
            weight = np.minimum(ramp_y[:, None], ramp_x[None, :])
            window = (slice(ty - top, ty + th), slice(tx - left, tx + tw))
            weight = np.where(covered[window], weight, 1.0)
            weight = np.where(region_valid, weight, 0.0)[..., None]
            output[window] = np.round(output[window] * (1 - weight) + region * weight).astype(np.uint8)
            covered[window] |= region_valid
    _fill_uncovered(output, covered)
    return FuseResult(image=output, used=used, dropped=dropped, reference=reference, scale=float(scale), warnings=warnings)


def _rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    return np.ascontiguousarray(image[:, :, :3])


def _describe(index: int, rgb: np.ndarray, config: FuseConfig) -> _Photo:
    height, width = rgb.shape[:2]
    scale = min(1.0, config.match_dimension / float(max(height, width)))
    small = cv2.resize(rgb, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    keypoints, descriptors = cv2.SIFT_create(nfeatures=5000).detectAndCompute(gray, None)
    points = np.float32([k.pt for k in keypoints]).reshape(-1, 2)
    return _Photo(index=index, rgb=rgb, small_scale=scale, points=points, descriptors=descriptors)


def _match_all(photos: list[_Photo], config: FuseConfig):
    """Homographies between full-resolution photos: edges[(a, b)] maps a's pixels into b.

    Also returns the inlier correspondences (full-resolution pixels) for refinement.
    """
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    edges: dict[tuple[int, int], tuple[np.ndarray, int]] = {}
    matches: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    for a in range(len(photos)):
        for b in range(a + 1, len(photos)):
            pa, pb = photos[a], photos[b]
            if pa.descriptors is None or pb.descriptors is None or len(pa.points) < 8 or len(pb.points) < 8:
                continue
            pairs = matcher.knnMatch(pa.descriptors, pb.descriptors, k=2)
            good = [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < 0.75 * n.distance]
            if len(good) < config.min_inliers:
                continue
            src = pa.points[[m.queryIdx for m in good]]
            dst = pb.points[[m.trainIdx for m in good]]
            small_h, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
            if small_h is None or inliers is None:
                continue
            count = int(inliers.sum())
            if count < config.min_inliers:
                continue
            full_h = np.diag([1 / pb.small_scale, 1 / pb.small_scale, 1]) @ small_h @ np.diag([pa.small_scale, pa.small_scale, 1])
            full_h = full_h / full_h[2, 2]
            if not _plausible(full_h):
                continue
            keep = inliers.ravel().astype(bool)
            full_a = src[keep] / pa.small_scale
            full_b = dst[keep] / pb.small_scale
            edges[(a, b)] = (full_h, count)
            edges[(b, a)] = (np.linalg.inv(full_h), count)
            matches[(a, b)] = (full_a, full_b)
            matches[(b, a)] = (full_b, full_a)
    return edges, matches


def _refine(to_ref: dict[int, np.ndarray], reference: int, matches, rounds: int = 3) -> dict[int, np.ndarray]:
    """Re-fit each photo against every placed photo it overlaps, so chained errors do not pile up."""
    placed = dict(to_ref)
    for _ in range(rounds):
        for i in sorted(placed):
            if i == reference:
                continue
            src, dst = [], []
            for (a, b), (pts_a, pts_b) in matches.items():
                if a == i and b in placed:
                    src.append(pts_a)
                    dst.append(_apply(placed[b], pts_b))
            if not src:
                continue
            source, target = np.concatenate(src), np.concatenate(dst)
            if len(source) < 8:
                continue
            fitted, mask = cv2.findHomography(source, target, cv2.RANSAC, 2.0)
            if fitted is None or mask is None or int(mask.sum()) < 8 or not _plausible(fitted / fitted[2, 2]):
                continue
            fitted = fitted / fitted[2, 2]
            # Keep the re-fit only if it agrees better with all the overlapping photos.
            if _reprojection(fitted, source, target) < _reprojection(placed[i], source, target):
                placed[i] = fitted
    return placed


def _reprojection(h: np.ndarray, source: np.ndarray, target: np.ndarray) -> float:
    return float(np.median(np.linalg.norm(_apply(h, source) - target, axis=1)))


def _plausible(h: np.ndarray) -> bool:
    linear = h[:2, :2]
    det = float(np.linalg.det(linear))
    if det <= 0:
        return False
    scale = np.sqrt(det)
    return 0.2 < scale < 5.0 and abs(h[2, 0]) < 0.01 and abs(h[2, 1]) < 0.01


def _place(count: int, edges: dict[tuple[int, int], tuple[np.ndarray, int]]) -> tuple[int, dict[int, np.ndarray]]:
    """Pick the best-connected photo and chain every reachable photo to it along the strongest matches."""
    strength = [sum(n for (a, _b), (_h, n) in edges.items() if a == i) for i in range(count)]
    reference = int(np.argmax(strength))
    to_ref: dict[int, np.ndarray] = {reference: np.eye(3)}
    while True:
        best = None
        for (a, b), (h, n) in edges.items():
            if a not in to_ref and b in to_ref and (best is None or n > best[2]):
                best = (a, b, n, h)
        if best is None:
            break
        a, b, _n, h = best
        placed = to_ref[b] @ h
        to_ref[a] = placed / placed[2, 2]
    return reference, to_ref


def _exposure_gains(photos: list[_Photo], to_ref: dict[int, np.ndarray], reference: int) -> dict[int, np.ndarray]:
    """Per-photo colour gain so overlapping photos agree with the reference's exposure."""
    ref = photos[reference]
    ref_small = cv2.resize(ref.rgb, None, fx=ref.small_scale, fy=ref.small_scale, interpolation=cv2.INTER_AREA)
    shrink = np.diag([ref.small_scale, ref.small_scale, 1])
    gains = {reference: np.ones(3, np.float32)}
    for i, h in to_ref.items():
        if i == reference:
            continue
        photo = photos[i]
        small = cv2.resize(photo.rgb, None, fx=photo.small_scale, fy=photo.small_scale, interpolation=cv2.INTER_AREA)
        h_small = shrink @ h @ np.diag([1 / photo.small_scale, 1 / photo.small_scale, 1])
        size = (ref_small.shape[1], ref_small.shape[0])
        warped = cv2.warpPerspective(small, h_small, size, flags=cv2.INTER_LINEAR)
        mask = cv2.warpPerspective(np.full(small.shape[:2], 255, np.uint8), h_small, size, flags=cv2.INTER_NEAREST) > 0
        mask &= (warped.max(axis=2) < 240) & (ref_small.max(axis=2) < 240)
        if int(mask.sum()) < 500:
            gains[i] = np.ones(3, np.float32)
            continue
        ratio = np.median(ref_small[mask].astype(np.float32), axis=0) / np.maximum(np.median(warped[mask].astype(np.float32), axis=0), 1)
        gains[i] = np.clip(ratio, 0.7, 1.4).astype(np.float32)
    return gains


def _density(to_ref: np.ndarray, shape: tuple[int, ...]) -> float:
    """Photo pixels per reference pixel, measured at the photo's centre."""
    height, width = shape[:2]
    inverse = np.linalg.inv(to_ref)
    centre = _apply(to_ref, np.array([[width / 2, height / 2]]))[0]
    probe = np.array([centre, centre + [1, 0], centre + [0, 1]])
    mapped = _apply(inverse, probe)
    jacobian = np.stack([mapped[1] - mapped[0], mapped[2] - mapped[0]], axis=1)
    return float(np.sqrt(abs(np.linalg.det(jacobian))))


def _canvas(photos, to_ref, density, config) -> tuple[tuple[int, int, tuple[float, float]], float, bool]:
    corners = []
    for i, h in to_ref.items():
        height, width = photos[i].rgb.shape[:2]
        corners.append(_apply(h, np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float64)))
    points = np.concatenate(corners)
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    scale = max(1.0, max(density.values()))
    area = (x1 - x0) * (y1 - y0) * scale * scale
    capped = area > config.max_pixels
    if capped:
        scale *= float(np.sqrt(config.max_pixels / area))
    width = max(1, int(np.ceil((x1 - x0) * scale)))
    height = max(1, int(np.ceil((y1 - y0) * scale)))
    return (width, height, (float(x0), float(y0))), float(scale), capped


def _footprint(to_canvas: np.ndarray, shape: tuple[int, ...]) -> tuple[float, float, float, float]:
    height, width = shape[:2]
    pts = _apply(to_canvas, np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float64))
    return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())


def _fuse_tile(tx, ty, width, height, photos, to_canvas, masks, footprints, gains, detail, priority, flow, config):
    m = config.margin
    x0, y0 = tx - m, ty - m
    tw, th = min(config.tile, width - tx), min(config.tile, height - ty)
    w, h = tw + 2 * m, th + 2 * m
    shift = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64)

    layers: list[tuple[int, np.ndarray, np.ndarray]] = []
    for i in priority:
        fx0, fy0, fx1, fy1 = footprints[i]
        if fx1 < x0 or fy1 < y0 or fx0 > x0 + w or fy0 > y0 + h:
            continue
        matrix = shift @ to_canvas[i]
        warped = cv2.warpPerspective(photos[i].rgb, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        valid = cv2.warpPerspective(masks[i], matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        valid = cv2.erode(valid, np.ones((5, 5), np.uint8)) > 0
        if valid[m : m + th, m : m + tw].mean() < config.min_coverage and layers:
            continue
        if not valid.any():
            continue
        layers.append((i, np.clip(warped.astype(np.float32) * gains[i], 0, 255), valid))

    if not layers:
        return np.zeros((h, w, 3), np.uint8), np.zeros((h, w), bool)

    # Reference: the highest-detail photo covering most of the tile.
    full = [layer for layer in layers if layer[2][m : m + th, m : m + tw].mean() > 0.5]
    ref_index, ref_rgb, ref_valid = (full or layers)[0]
    best = detail[ref_index]
    voters = [(ref_rgb, ref_valid)]
    ref_gray = cv2.cvtColor(ref_rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    for i, rgb, valid in layers:
        if i == ref_index or detail[i] < config.detail_ratio * best:
            continue
        both = valid & ref_valid
        if both.mean() < 0.05:
            # No shared area to align on: it only fills where the reference is missing.
            voters.append((rgb, valid & ~ref_valid))
            continue
        gray = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        gray = np.where(valid, gray, ref_gray).astype(np.uint8)
        motion = flow.calc(ref_gray, gray, None)
        magnitude = np.linalg.norm(motion[both], axis=1)
        if magnitude.size == 0 or float(np.median(magnitude)) > config.max_flow:
            continue
        # Residual drift is smooth; a local jump means the flow latched onto glare or a
        # reflection. Use the tile's typical shift there instead, so the pixel still votes.
        typical = np.median(motion[both], axis=0)
        jumps = np.linalg.norm(motion - typical, axis=2) > 2.5
        motion[jumps] = typical
        map_x, map_y = grid_x + motion[..., 0], grid_y + motion[..., 1]
        aligned_gray = cv2.remap(gray, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # Keep the flow only when it makes this photo agree better with the reference.
        # Homographies are usually within a pixel; flow on grain or glare can make it worse.
        before = _detail_difference(ref_gray, gray, both)
        after = _detail_difference(ref_gray, aligned_gray, both)
        if after > 0.9 * before:
            voters.append((rgb, valid))
            continue
        aligned = cv2.remap(rgb, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        aligned_valid = cv2.remap(valid.astype(np.uint8), map_x, map_y, interpolation=cv2.INTER_NEAREST, borderValue=0) > 0
        voters.append((aligned, aligned_valid))

    return _robust_median(voters, config.glare_level)


def _detail_difference(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """Mean difference of edges between two grey images, ignoring smooth brightness (glare, exposure)."""
    high_a = a.astype(np.float32) - cv2.GaussianBlur(a.astype(np.float32), (0, 0), 4)
    high_b = b.astype(np.float32) - cv2.GaussianBlur(b.astype(np.float32), (0, 0), 4)
    return float(np.abs(high_a - high_b)[mask].mean())


def _robust_median(voters: list[tuple[np.ndarray, np.ndarray]], glare_level: float) -> tuple[np.ndarray, np.ndarray]:
    stack = np.stack([rgb for rgb, _valid in voters])
    valid = np.stack([v for _rgb, v in voters])
    if len(voters) > 1:
        # Glare is a broad brightening that moves between photos. Compare each photo's
        # blurred brightness with the darkest photo at that spot: blurring ignores small
        # misalignments at letter edges, so only the smooth glare (and its halo) is dropped.
        brightness = stack.max(axis=3)
        smooth = np.stack(
            [cv2.GaussianBlur(np.where(v, b, np.nan).astype(np.float32), (0, 0), 6) for b, v in zip(brightness, valid)]
        )
        smooth = np.where(np.isnan(smooth), np.stack([cv2.GaussianBlur(b, (0, 0), 6) for b in brightness]), smooth)
        darkest = np.where(valid, smooth, np.inf).min(axis=0)
        glare = (smooth > darkest[None] + 18) & ((brightness >= glare_level) | (smooth > darkest[None] + 30))
        valid = valid & ~glare
        # Never leave a pixel with no vote because of this test.
        valid |= (valid.sum(axis=0) == 0)[None] & np.stack([v for _rgb, v in voters])
    count = valid.sum(axis=0)
    data = np.where(valid[..., None], stack, np.nan)
    data.sort(axis=0)  # NaN sorts last
    low = np.clip((count - 1) // 2, 0, None)[None, ..., None]
    high = np.clip(count // 2, 0, len(voters) - 1)[None, ..., None]
    low = np.broadcast_to(low, (1, *data.shape[1:]))
    high = np.broadcast_to(high, (1, *data.shape[1:]))
    median = (np.take_along_axis(data, low, 0)[0] + np.take_along_axis(data, high, 0)[0]) / 2
    median = np.nan_to_num(median, nan=0.0)
    return np.clip(np.round(median), 0, 255).astype(np.uint8), count > 0


def _fill_uncovered(image: np.ndarray, covered: np.ndarray) -> None:
    """Paint areas no photo saw with the surrounding surface colour, so detection treats them as background."""
    if covered.all() or not covered.any():
        return
    edge = covered & ~cv2.erode(covered.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    colour = np.median(image[edge], axis=0) if edge.any() else np.median(image[covered], axis=0)
    image[~covered] = colour.astype(np.uint8)


def _apply(h: np.ndarray, points: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(points.reshape(-1, 1, 2).astype(np.float64), h).reshape(-1, 2)
