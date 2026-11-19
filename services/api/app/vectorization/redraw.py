"""Flatten a sticker photo into a few solid inks before tracing.

Printed stickers use a handful of flat inks. A photo of one adds grain,
uneven lighting and soft edges, which VTracer would otherwise trace as lumps
and blotches. This step rebuilds the flat-ink artwork it was printed from:

1. Edge-preserving denoise removes camera grain without rounding ink edges.
2. Work at 2x so thin strokes and small letters keep sub-pixel boundaries.
3. K-means in Lab finds the inks; near-identical inks are merged.
4. A small majority filter removes stray specks.
5. Neighbouring regions are merged when the edge between them is soft and the
   inks are close. A lighting gradient changes slowly; a printed edge is sharp,
   and black next to grey is never merged.

It is deterministic: the same input always gives the same inks and shapes.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


SPECK_AREA = 64  # pixels at the traced (2x) size


@dataclass
class RedrawConfig:
    inks: int = 6
    scale: int = 2
    mode_window: int = 5
    merge_inks_below: float = 10.0  # Lab distance under which two inks are the same ink
    soft_edge: float = 1.0  # boundary softness cutoff, relative to the typical ink edge
    max_ink_step: float = 24.0  # never merge regions whose inks differ more than this


@dataclass
class RedrawResult:
    image: np.ndarray  # RGBA at `scale` times the input size
    palette: np.ndarray  # (n, 3) uint8 RGB
    merges: int


def flatten_artwork(image_rgba: np.ndarray, config: RedrawConfig | None = None) -> RedrawResult:
    config = config or RedrawConfig()
    rgb = np.ascontiguousarray(image_rgba[:, :, :3])
    alpha = image_rgba[:, :, 3]
    smooth = cv2.fastNlMeansDenoisingColored(rgb, None, 10, 10, 7, 21)
    lab = cv2.cvtColor(smooth, cv2.COLOR_RGB2LAB).astype(np.float32)
    scale = max(1, int(config.scale))
    if scale > 1:
        lab = cv2.resize(lab, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        alpha = cv2.resize(alpha, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    fg = alpha > 128
    if int(fg.sum()) < 64:
        empty = np.zeros((*fg.shape, 4), np.uint8)
        return RedrawResult(image=empty, palette=np.zeros((0, 3), np.uint8), merges=0)

    centers = _find_inks(lab[fg], config)
    labels = _assign(lab, centers)
    if config.mode_window > 1:
        votes = np.stack(
            [cv2.blur((labels == i).astype(np.float32), (config.mode_window, config.mode_window)) for i in range(len(centers))]
        )
        labels = votes.argmax(0).astype(np.int32)
    labels[~fg] = -1
    labels, merges = _merge_soft_regions(labels, lab[:, :, 0], centers, fg, config)

    palette = cv2.cvtColor(np.clip(centers, 0, 255).astype(np.uint8)[None], cv2.COLOR_LAB2RGB)[0]
    rgb_out = palette[np.maximum(labels, 0)]
    image = np.dstack([rgb_out, np.where(fg, 255, 0).astype(np.uint8)]).astype(np.uint8)
    return RedrawResult(image=image, palette=palette, merges=merges)


def _find_inks(pixels: np.ndarray, config: RedrawConfig) -> np.ndarray:
    k = int(np.clip(config.inks, 2, 16))
    rng = np.random.default_rng(0)
    sample = pixels if len(pixels) <= 80000 else pixels[rng.choice(len(pixels), 80000, replace=False)]
    k = min(k, len(np.unique(sample.round(), axis=0)))
    if k < 2:
        return sample[:1].astype(np.float32)
    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.2)
    _, _, centers = cv2.kmeans(sample.astype(np.float32), k, None, criteria, 4, cv2.KMEANS_PP_CENTERS)
    inks = [c for c in centers]
    merged = True
    while merged and len(inks) > 2:
        merged = False
        for i in range(len(inks)):
            for j in range(i + 1, len(inks)):
                if float(np.linalg.norm(inks[i] - inks[j])) < config.merge_inks_below:
                    inks[i] = (inks[i] + inks[j]) / 2
                    inks.pop(j)
                    merged = True
                    break
            if merged:
                break
    # Order dark to light so output is stable and readable.
    inks.sort(key=lambda c: float(c[0]))
    return np.array(inks, np.float32)


def _assign(lab: np.ndarray, centers: np.ndarray) -> np.ndarray:
    distance = np.stack([((lab - c) ** 2).sum(-1) for c in centers])
    return distance.argmin(0).astype(np.int32)


def _merge_soft_regions(
    labels: np.ndarray,
    lightness: np.ndarray,
    centers: np.ndarray,
    fg: np.ndarray,
    config: RedrawConfig,
) -> tuple[np.ndarray, int]:
    """Union regions across soft, low-contrast boundaries (lighting), smallest first."""
    component = np.full(labels.shape, -1, np.int64)
    ink_of: list[int] = []
    count = 0
    for ink in range(len(centers)):
        n, comp = cv2.connectedComponents((labels == ink).astype(np.uint8), connectivity=4)
        inside = comp > 0
        component[inside] = comp[inside] - 1 + count
        ink_of.extend([ink] * (n - 1))
        count += n - 1
    if count < 2:
        return labels, 0
    ink_arr = np.array(ink_of)
    area = np.bincount(component[component >= 0], minlength=count).astype(np.int64)

    # Edge strength: lightness difference across a few pixels, so a soft ramp scores low.
    blurred = cv2.GaussianBlur(lightness, (0, 0), 1.0)
    across_y = np.abs(np.roll(blurred, -2, 0) - np.roll(blurred, 1, 0))[:-1].ravel()
    across_x = np.abs(np.roll(blurred, -2, 1) - np.roll(blurred, 1, 1))[:, :-1].ravel()
    a = np.concatenate([component[:-1].ravel(), component[:, :-1].ravel()])
    b = np.concatenate([component[1:].ravel(), component[:, 1:].ravel()])
    strength = np.concatenate([across_y, across_x])
    keep = (a != b) & (a >= 0) & (b >= 0)
    if not keep.any():
        return labels, 0
    lo, hi, strength = np.minimum(a[keep], b[keep]), np.maximum(a[keep], b[keep]), strength[keep]
    pair, inverse = np.unique(lo * count + hi, return_inverse=True)
    length = np.bincount(inverse)
    mean_strength = np.bincount(inverse, strength) / length
    cutoff = float(np.median(strength)) * config.soft_edge
    first, second = pair // count, pair % count

    parent = np.arange(count)

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    merges = 0
    for index in np.argsort(mean_strength, kind="stable"):
        if mean_strength[index] >= cutoff:
            break
        if length[index] < 20:
            continue
        ra, rb = find(int(first[index])), find(int(second[index]))
        if ra == rb:
            continue
        big, small = (ra, rb) if area[ra] >= area[rb] else (rb, ra)
        if float(np.linalg.norm(centers[ink_arr[big]] - centers[ink_arr[small]])) > config.max_ink_step:
            continue
        parent[small] = big
        area[big] += area[small]
        merges += 1
    # Specks left over: fold each into the neighbour it shares the longest border with.
    for index in np.argsort(-length, kind="stable"):
        ra, rb = find(int(first[index])), find(int(second[index]))
        if ra == rb:
            continue
        big, small = (ra, rb) if area[ra] >= area[rb] else (rb, ra)
        if area[small] >= SPECK_AREA:
            continue
        parent[small] = big
        area[big] += area[small]
        merges += 1
    if not merges:
        return labels, 0
    roots = np.array([find(i) for i in range(count)])
    merged = labels.copy()
    inside = component >= 0
    merged[inside] = ink_arr[roots[component[inside]]]
    return merged, merges
