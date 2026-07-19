# Copyright 2026 Dan Keder
#
# Modifications Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file includes code modified from
# https://github.com/ludeeus/integration_blueprint/, which is licensed under
# the MIT License.
#
"""Pure image-processing helpers for the MeteoBlue integration."""

from __future__ import annotations

from io import BytesIO
from typing import Literal

import numpy as np
from PIL import Image

Background = Literal["white", "black"]

_MID_LUMINANCE = 128


def invert_png(content: bytes) -> bytes:
    """
    Return a tone-inverted copy of the given PNG bytes.

    Inverts HSL lightness while preserving hue and saturation, so white
    backgrounds become black and colored elements keep their identity
    (e.g. red stays red, blue stays blue). Text drawn in dark ink on a
    white background becomes light ink on a dark background and remains
    legible.

    The function is synchronous and CPU-bound; call it from a worker
    thread (e.g. ``asyncio.to_thread``) when running under an event loop.
    """
    with Image.open(BytesIO(content)) as img:
        has_alpha = (
            img.mode in ("RGBA", "LA") or img.info.get("transparency") is not None
        )
        mode = "RGBA" if has_alpha else "RGB"
        arr = np.asarray(img.convert(mode), dtype=np.int16).copy()
        rgb = arr[..., :3]
        mx = rgb.max(axis=-1, keepdims=True)
        mn = rgb.min(axis=-1, keepdims=True)
        arr[..., :3] = np.clip(255 - mx - mn + rgb, 0, 255)
        out = Image.fromarray(arr.astype(np.uint8), mode)
        buf = BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()


def remove_background(
    content: bytes,
    background: Background | None = None,
) -> bytes:
    """
    Return a copy of the PNG with its white or black background made transparent.

    The background color is auto-detected from the image corners when
    ``background`` is ``None``; pass ``"white"`` or ``"black"`` to override.

    Alpha is derived from each pixel's distance from the background color,
    and the RGB is unmultiplied so antialiased edges (e.g. around text)
    blend cleanly over any new background without halos.

    The function is synchronous and CPU-bound; call it from a worker
    thread (e.g. ``asyncio.to_thread``) when running under an event loop.
    """
    with Image.open(BytesIO(content)) as img:
        source = (
            img.convert("RGBA")
            if img.mode == "P" and "transparency" in img.info
            else img
        )
        rgb = np.asarray(source.convert("RGB"), dtype=np.float32)

    if background is None:
        background = _detect_background(rgb)

    alpha = 255.0 - rgb.min(axis=-1) if background == "white" else rgb.max(axis=-1)

    safe_alpha = np.where(alpha > 0, alpha, 1.0)[..., np.newaxis]
    fg = (
        (rgb - 255.0) * (255.0 / safe_alpha) + 255.0
        if background == "white"
        else rgb * (255.0 / safe_alpha)
    )

    out = np.empty((*rgb.shape[:2], 4), dtype=np.uint8)
    out[..., :3] = np.clip(fg, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)

    buf = BytesIO()
    Image.fromarray(out, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _detect_background(rgb: np.ndarray) -> Background:
    """Classify the background as white or black by sampling the four corners."""
    h, w = rgb.shape[:2]
    patch = min(4, h, w)
    corners = np.concatenate(
        [
            rgb[:patch, :patch].reshape(-1, 3),
            rgb[:patch, -patch:].reshape(-1, 3),
            rgb[-patch:, :patch].reshape(-1, 3),
            rgb[-patch:, -patch:].reshape(-1, 3),
        ]
    )
    return "white" if corners.mean() > _MID_LUMINANCE else "black"
