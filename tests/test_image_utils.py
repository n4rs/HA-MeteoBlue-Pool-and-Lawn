# Copyright 2026 Dan Keder
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
"""Tests for meteoblue.image_utils."""

from __future__ import annotations

import warnings
from io import BytesIO
from pathlib import Path

from meteoblue.image_utils import invert_png, remove_background
from PIL import Image, ImageDraw

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FIXTURE = Path(__file__).parent / "fixtures" / "meteogram_extended.png"


def _encode_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_invert_returns_valid_png() -> None:
    """Output starts with the PNG signature and is decodable."""
    out = invert_png(FIXTURE.read_bytes())
    assert out.startswith(PNG_SIGNATURE)
    with Image.open(BytesIO(out)) as img:
        img.load()


def test_invert_preserves_dimensions() -> None:
    """Inverted output keeps the original width and height."""
    src = FIXTURE.read_bytes()
    with Image.open(BytesIO(src)) as img:
        src_size = img.size
    with Image.open(BytesIO(invert_png(src))) as inv:
        assert inv.size == src_size


def test_invert_synthetic_colors() -> None:
    """HSL-lightness invert: white<->black, red stays red, gray unchanged."""
    img = Image.new("RGB", (5, 1))
    img.putpixel((0, 0), (255, 255, 255))  # white
    img.putpixel((1, 0), (0, 0, 0))  # black
    img.putpixel((2, 0), (255, 0, 0))  # red
    img.putpixel((3, 0), (128, 0, 0))  # dark red
    img.putpixel((4, 0), (128, 128, 128))  # gray

    with Image.open(BytesIO(invert_png(_encode_png(img)))) as raw:
        out = raw.convert("RGB")
    assert out.getpixel((0, 0)) == (0, 0, 0)
    assert out.getpixel((1, 0)) == (255, 255, 255)
    assert out.getpixel((2, 0)) == (255, 0, 0)
    assert out.getpixel((3, 0)) == (255, 127, 127)
    assert out.getpixel((4, 0)) == (127, 127, 127)


def test_invert_preserves_alpha() -> None:
    """Alpha channel passes through untouched; only RGB is inverted."""
    img = Image.new("RGBA", (2, 1))
    img.putpixel((0, 0), (255, 255, 255, 64))
    img.putpixel((1, 0), (255, 0, 0, 200))

    with Image.open(BytesIO(invert_png(_encode_png(img)))) as raw:
        out = raw.convert("RGBA")
    assert out.getpixel((0, 0)) == (0, 0, 0, 64)
    assert out.getpixel((1, 0)) == (255, 0, 0, 200)


def _assert_close(
    actual: tuple[int, ...], expected: tuple[int, ...], tol: int = 1
) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected, strict=True):
        assert abs(a - e) <= tol, f"{actual} vs {expected}"


def test_remove_background_returns_valid_png_preserving_dimensions() -> None:
    """Output is a decodable PNG with the same dimensions as the input."""
    src = FIXTURE.read_bytes()
    out = remove_background(src)
    assert out.startswith(PNG_SIGNATURE)
    with Image.open(BytesIO(src)) as src_img, Image.open(BytesIO(out)) as out_img:
        assert out_img.size == src_img.size


def test_remove_background_no_warning_on_palette_transparency() -> None:
    """Palette PNG with tRNS bytes must not trigger PIL warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        remove_background(FIXTURE.read_bytes())


def test_remove_white_background_synthetic_colors() -> None:
    """White bg: alpha derived from distance from white; RGB unmultiplied."""
    img = Image.new("RGB", (5, 1))
    img.putpixel((0, 0), (255, 255, 255))  # pure white -> transparent
    img.putpixel((1, 0), (0, 0, 0))  # pure black -> opaque black
    img.putpixel((2, 0), (128, 128, 128))  # mid gray -> semi-transparent black
    img.putpixel((3, 0), (255, 0, 0))  # saturated red -> opaque red
    img.putpixel((4, 0), (255, 128, 128))  # antialiased red -> semi red, no halo

    with Image.open(
        BytesIO(remove_background(_encode_png(img), background="white"))
    ) as raw:
        out = raw.convert("RGBA")

    assert out.getpixel((0, 0))[3] == 0
    _assert_close(out.getpixel((1, 0)), (0, 0, 0, 255))
    _assert_close(out.getpixel((2, 0)), (0, 0, 0, 127))
    _assert_close(out.getpixel((3, 0)), (255, 0, 0, 255))
    _assert_close(out.getpixel((4, 0)), (255, 0, 0, 127))


def test_remove_black_background_synthetic_colors() -> None:
    """Black bg: alpha derived from distance from black; RGB unmultiplied."""
    img = Image.new("RGB", (5, 1))
    img.putpixel((0, 0), (0, 0, 0))  # pure black -> transparent
    img.putpixel((1, 0), (255, 255, 255))  # pure white -> opaque white
    img.putpixel((2, 0), (128, 128, 128))  # mid gray -> semi-transparent white
    img.putpixel((3, 0), (0, 255, 255))  # saturated cyan -> opaque cyan
    img.putpixel((4, 0), (0, 128, 128))  # antialiased cyan -> semi cyan, no halo

    with Image.open(
        BytesIO(remove_background(_encode_png(img), background="black"))
    ) as raw:
        out = raw.convert("RGBA")

    assert out.getpixel((0, 0))[3] == 0
    _assert_close(out.getpixel((1, 0)), (255, 255, 255, 255))
    _assert_close(out.getpixel((2, 0)), (255, 255, 255, 128))
    _assert_close(out.getpixel((3, 0)), (0, 255, 255, 255))
    _assert_close(out.getpixel((4, 0)), (0, 255, 255, 128))


def test_remove_background_autodetects_white_corners() -> None:
    """With no arg, white corners imply white bg removal."""
    img = Image.new("RGB", (8, 8), (255, 255, 255))
    img.paste((0, 0, 0), (3, 3, 5, 5))

    with Image.open(BytesIO(remove_background(_encode_png(img)))) as raw:
        out = raw.convert("RGBA")
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((4, 4)) == (0, 0, 0, 255)


def test_remove_background_autodetects_black_corners() -> None:
    """With no arg, black corners imply black bg removal."""
    img = Image.new("RGB", (8, 8), (0, 0, 0))
    img.paste((255, 255, 255), (3, 3, 5, 5))

    with Image.open(BytesIO(remove_background(_encode_png(img)))) as raw:
        out = raw.convert("RGBA")
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((4, 4)) == (255, 255, 255, 255)


def test_remove_background_explicit_arg_overrides_corners() -> None:
    """The explicit background arg takes precedence over corner detection."""
    img = Image.new("RGB", (8, 8), (255, 255, 255))
    img.paste((0, 0, 0), (3, 3, 5, 5))

    with Image.open(
        BytesIO(remove_background(_encode_png(img), background="black"))
    ) as raw:
        out = raw.convert("RGBA")
    assert out.getpixel((4, 4))[3] == 0
    _assert_close(out.getpixel((0, 0)), (255, 255, 255, 255))


def test_remove_background_no_halo_around_antialiased_text() -> None:
    """Antialiased edge pixels unmultiply to near-black; no grey halo survives."""
    img = Image.new("RGB", (64, 24), (255, 255, 255))
    ImageDraw.Draw(img).text((4, 4), "Hg", fill=(0, 0, 0))

    with Image.open(BytesIO(remove_background(_encode_png(img)))) as raw:
        out = raw.convert("RGBA")

    edge_samples = [
        (x, y)
        for x in range(out.width)
        for y in range(out.height)
        if 0 < out.getpixel((x, y))[3] < 255
    ]
    assert edge_samples, "expected at least one antialiased edge pixel"
    for x, y in edge_samples:
        r, g, b, _ = out.getpixel((x, y))
        assert max(r, g, b) <= 16, f"halo at {(x, y)}: rgb={(r, g, b)}"
