"""Give a light SVG picture a dark palette of its own, inside the file.

The site's dark mode used to put a light card behind every SVG, because the
charts here are drawn dark on white. This module lets the site do better for
most of them: it reads a picture's colours, works out a dark counterpart for
each, and writes them into the file as a `prefers-color-scheme: dark` block,
so the browser swaps the palette itself when the reader's system is dark.

A colour's counterpart keeps its hue and chroma and flips its lightness in
OKLab: white takes the lightness of the site's dark background, black that
of its dark-mode text (as greys: the page's slight warmth isn't copied, a
difference of 3 in one channel), and in between the flip goes by the square of the lightness, so the
ends swap while the midtones barely move. Text stays bright, gridlines stay
faint, an accent colour stays about as light as it was (a straight flip
turned orange into brown), and a light-to-dark ramp becomes a dark-to-light
one. Where the result falls outside sRGB, its chroma is reduced until it
fits.

Only a picture this can recolour completely gets a palette: one whose first
element is a full-size rectangle in a light colour, whose every fill and
stroke is a hex colour, `none` or `transparent`, and which has no `<style>`, no `style=`
attribute and no embedded `<image>` (a raster can't be recoloured by CSS).
Anything else is left as it is, and the site keeps the light card behind it.
A picture that is already dark doesn't need either.
"""

import math
import re

# The site's dark-mode background and text (STYLE in build_site.py).
DARK_BG = "#17171a"
DARK_FG = "#e8e6e1"

HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
PAINT = re.compile(r"""\b(fill|stroke|stop-color|flood-color)\s*=\s*(["'])(.*?)\2""")
OPENING = re.compile(r"<svg\b[^>]*>")
FIRST_ELEMENT = re.compile(r"\s*(<(\w+)\b[^>]*>)")
ATTR = re.compile(r"""\b([\w-]+)\s*=\s*(["'])(.*?)\2""")


def rgb_of(color: str) -> tuple[float, float, float]:
    """A hex colour as sRGB channels from 0 to 1."""
    digits = color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    r, g, b = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return r, g, b


def hex_of(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def gamma(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """sRGB to OKLab (Björn Ottosson's matrices)."""
    r, g, b = (linear(c) for c in rgb)
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in lms)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def srgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    """OKLab to sRGB, unclamped: a channel outside 0 to 1 means out of gamut."""
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3  # noqa: E741 (Ottosson's names for the cone responses)
    return tuple(
        gamma(c) if c >= 0 else -gamma(-c)
        for c in (
            4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
        )
    )


def lightness(color: str) -> float:
    return oklab(rgb_of(color))[0]


def dark(color: str) -> str:
    """The dark-mode counterpart of a hex colour."""
    L, a, b = oklab(rgb_of(color))
    lo, hi = lightness(DARK_BG), lightness(DARK_FG)
    L = lo + (1 - L * L) * (hi - lo)
    # Reduce chroma, keeping hue, until the colour is inside sRGB.
    scale, step = 1.0, 0.5
    if not in_gamut(srgb((L, a, b))):
        scale = 0.0
        for _ in range(20):
            if in_gamut(srgb((L, a * (scale + step), b * (scale + step)))):
                scale += step
            step /= 2
    return hex_of(srgb((L, a * scale, b * scale)))


def in_gamut(rgb: tuple[float, float, float], slack: float = 1e-6) -> bool:
    return all(-slack <= c <= 1 + slack for c in rgb)


def palette(svg: str) -> dict[str, str] | None:
    """{colour as written: its dark counterpart} for a picture this can recolour, else None."""
    opening = OPENING.search(svg)
    if opening is None or re.search(r"<style\b|<image\b|\sstyle\s*=", svg):
        return None
    first = FIRST_ELEMENT.match(svg, opening.end())
    if first is None or first.group(2) != "rect":
        return None
    rect = {m.group(1): m.group(3) for m in ATTR.finditer(first.group(1))}
    svg_attrs = {m.group(1): m.group(3) for m in ATTR.finditer(opening.group(0))}
    view = svg_attrs.get("viewBox", "").replace(",", " ").split()
    wide = {"100%", svg_attrs.get("width"), view[2] if len(view) == 4 else None} - {None}
    tall = {"100%", svg_attrs.get("height"), view[3] if len(view) == 4 else None} - {None}
    if (
        rect.get("x", "0") != "0"
        or rect.get("y", "0") != "0"
        or rect.get("width") not in wide
        or rect.get("height") not in tall
        or not HEX.fullmatch(rect.get("fill", ""))
        or lightness(rect["fill"]) < 0.6
    ):
        return None
    colors = {}
    for m in PAINT.finditer(svg):
        value = m.group(3)
        if value in ("none", "transparent"):
            continue
        if not HEX.fullmatch(value):
            return None
        colors[value] = dark(value)
    return colors


def darken(svg: str) -> str | None:
    """`svg` with its dark palette written in, or None if it can't have one."""
    colors = palette(svg)
    if colors is None:
        return None
    rules = [f"svg:not([fill]){{fill:{dark('#000')}}}"]
    for value, counterpart in sorted(colors.items()):
        for name in ("fill", "stroke", "stop-color", "flood-color"):
            if re.search(rf"""\b{name}\s*=\s*["']{re.escape(value)}["']""", svg):
                rules.append(f'[{name}="{value}"]{{{name}:{counterpart}}}')
    block = "<style>@media (prefers-color-scheme: dark){" + "".join(rules) + "}</style>"
    end = OPENING.search(svg).end()
    return svg[:end] + "\n" + block + svg[end:]
