import random
import re
from pathlib import Path

import pytest
from darksvg import DARK_BG, DARK_FG, dark, darken, lightness, oklab, palette, rgb_of

ROOT = Path(__file__).resolve().parent.parent

# Real pictures that keep the light card, and why.
KEPT_LIGHT = {
    "projects/eca/out/damage.svg": "the cells are embedded PNGs",
    "projects/eca/out/poster.svg": "the cells are embedded PNGs",
    "projects/forth/out/sierpinski.svg": "no background of its own",
}

CHART = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">\n'
    '<rect width="100" height="50" fill="#fff"/>\n'
    '<text x="4" y="12">title</text>\n'
    '<line x1="0" x2="100" y1="40" y2="40" stroke="#e5e5e5"/>\n'
    "<rect x='10' y='20' width='8' height='20' fill='#2a78d6' stroke='none'/>\n"
    "</svg>\n"
)


def test_white_and_black_land_on_the_sites_dark_background_and_text():
    assert lightness(dark("#fff")) == pytest.approx(lightness(DARK_BG), abs=0.005)
    assert lightness(dark("#ffffff")) == pytest.approx(lightness(DARK_BG), abs=0.005)
    assert lightness(dark("#000")) == pytest.approx(lightness(DARK_FG), abs=0.005)


def test_greys_flip_in_order_and_stay_grey():
    greys = [f"#{v:02x}{v:02x}{v:02x}" for v in range(0, 256, 15)]
    flipped = [lightness(dark(g)) for g in greys]
    assert flipped == sorted(flipped, reverse=True)
    for g in greys:
        r, gg, b = rgb_of(dark(g))
        assert max(r, gg, b) - min(r, gg, b) < 0.01, g


def test_an_accent_keeps_its_hue_and_about_its_lightness():
    for color in ("#2a78d6", "#eb6834", "#c2410c", "#2563eb"):
        _, a, b = oklab(rgb_of(color))
        lit, a2, b2 = oklab(rgb_of(dark(color)))
        hue, hue2 = complex(a, b), complex(a2, b2)
        assert abs((hue2 / hue).imag / abs(hue2 / hue)) < 0.03, color
        # A straight flip took these down by 0.15 to 0.25; now they barely darken, if at all.
        assert lit > lightness(color) - 0.1, color


def test_every_counterpart_is_a_real_srgb_colour():
    rng = random.Random(7)
    for _ in range(500):
        color = "#" + "".join(f"{rng.randrange(256):02x}" for _ in range(3))
        assert re.fullmatch(r"#[0-9a-f]{6}", dark(color)), color


def test_a_chart_gets_a_rule_for_each_colour_it_uses():
    colors = palette(CHART)
    assert colors == {c: dark(c) for c in ("#fff", "#e5e5e5", "#2a78d6")}
    out = darken(CHART)
    head, block, rest = out.partition("<style>")
    assert head == '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">\n'
    assert rest.endswith(CHART.partition("\n")[2])
    assert block + rest.partition("</style>")[0] == (
        "<style>@media (prefers-color-scheme: dark){"
        f"svg:not([fill]){{fill:{dark('#000')}}}"
        f'[fill="#2a78d6"]{{fill:{dark("#2a78d6")}}}'
        f'[stroke="#e5e5e5"]{{stroke:{dark("#e5e5e5")}}}'
        f'[fill="#fff"]{{fill:{dark("#fff")}}}'
        "}"
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.replace("<text", "<style>text{fill:#444}</style><text"),
        lambda s: s.replace("<text", '<image href="data:image/png;base64,AA"/><text'),
        lambda s: s.replace('<text x="4"', '<text style="fill:red" x="4"'),
        lambda s: s.replace('stroke="#e5e5e5"', 'stroke="grey"'),
        lambda s: s.replace('stroke="#e5e5e5"', 'stroke="url(#g)"'),
        lambda s: s.replace('fill="#fff"', 'fill="#14151a"'),  # already dark
        lambda s: s.replace('<rect width="100"', '<rect x="5" width="100"'),
        lambda s: s.replace('<rect width="100"', '<rect width="40"'),
        lambda s: s.replace('<rect width="100" height="50" fill="#fff"/>\n', ""),
        lambda s: s.replace("<svg", "<g"),
    ],
    ids=[
        "style",
        "image",
        "style-attr",
        "named",
        "gradient",
        "dark",
        "offset",
        "narrow",
        "no-bg",
        "not-svg",
    ],
)
def test_a_picture_it_cannot_recolour_completely_is_left_alone(change):
    svg = change(CHART)
    assert svg != CHART
    assert palette(svg) is None
    assert darken(svg) is None


def test_a_full_size_background_may_be_written_as_a_percentage_or_by_width():
    assert palette(CHART.replace('<rect width="100"', '<rect width="100%"'))
    by_width = CHART.replace('viewBox="0 0 100 50"', 'width="100" height="50"')
    assert palette(by_width)
    assert palette(CHART.replace('stroke="none"', 'stroke="transparent"'))


def test_every_real_picture_is_dark_already_recoloured_or_kept_light_for_a_reason():
    for path in sorted(ROOT.glob("projects/*/out/*.svg")):
        name = path.relative_to(ROOT).as_posix()
        svg = path.read_text(encoding="utf-8")
        background = re.search(r"""<rect[^>]*fill=["'](#[0-9a-fA-F]+)""", svg)
        already_dark = background and lightness(background.group(1)) < 0.5
        if name in KEPT_LIGHT:
            assert darken(svg) is None, f"{name} can be recoloured now; drop it from KEPT_LIGHT"
        elif not already_dark:
            assert darken(svg) is not None, f"{name} has no dark palette"


def test_real_text_stays_readable_in_dark_mode():
    for path in sorted(ROOT.glob("projects/*/out/*.svg")):
        colors = palette(path.read_text(encoding="utf-8"))
        if colors is None:
            continue
        text = r"""<text[^>]*?fill=["'](#[0-9a-fA-F]+)"""
        fills = re.findall(text, path.read_text(encoding="utf-8"))
        for color in fills:
            if lightness(color) > 0.5:
                continue  # light text on a dark mark, such as a count on a heatmap cell
            gap = lightness(colors[color]) - lightness(DARK_BG)
            assert gap > 0.4, f"{path.name}: text in {color} is too close to the background"
