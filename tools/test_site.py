import posixpath
import re
import subprocess
import sys
from pathlib import Path

import build_site
from build_site import Site, build, inline, markdown

ROOT = Path(__file__).resolve().parent.parent


# --- the markdown subset ------------------------------------------------


def test_headings_get_unique_ids():
    html = markdown("# Title\n\n## Review\n\ntext\n\n## Review\n")
    assert '<h1 id="title">Title</h1>' in html
    assert '<h2 id="review">Review</h2>' in html
    assert '<h2 id="review-2">Review</h2>' in html


def test_paragraph_lines_join_and_blank_lines_split():
    html = markdown("one\ntwo\n\nthree\n")
    assert html == "<p>one two</p>\n<p>three</p>"


def test_text_is_escaped_outside_raw_html():
    assert markdown("a < b & c > d") == "<p>a &lt; b &amp; c &gt; d</p>"


def test_fenced_code_is_escaped_and_kept_verbatim():
    html = markdown("```sh\nls  *.md <x>\n\n**not bold**\n```\nafter\n")
    assert '<pre><code class="language-sh">ls  *.md &lt;x&gt;\n\n**not bold**</code></pre>' in html
    assert "<p>after</p>" in html


def test_inline_code_protects_its_contents():
    assert inline("`a *b* [c](d)` and *e*") == ("<code>a *b* [c](d)</code> and <em>e</em>")


def test_emphasis_and_strong():
    assert inline("**It's done.** and *this* and _that_") == (
        "<strong>It&#x27;s done.</strong> and <em>this</em> and <em>that</em>"
    )


def test_underscores_and_stars_inside_words_are_left_alone():
    assert inline("twin_peaks_txt and 2*n*3") == "twin_peaks_txt and 2*n*3"


def test_one_letter_spans_close_at_their_own_mark():
    assert inline("after *n* steps it is at *k*") == "after <em>n</em> steps it is at <em>k</em>"
    assert inline("if **x** is big, **y** is small") == (
        "if <strong>x</strong> is big, <strong>y</strong> is small"
    )
    assert inline("_a_ and _b c_") == "<em>a</em> and <em>b c</em>"


def test_a_run_of_underscores_is_a_blank_not_emphasis():
    # Clue 39 of the crossword.
    assert inline('"That ___ you like" (3)') == "&quot;That ___ you like&quot; (3)"


def test_emphasis_never_reaches_inside_a_url():
    assert markdown("[init](pkg/__init__.py)") == '<p><a href="pkg/__init__.py">init</a></p>'
    assert inline("[**b** `x_y_`](a/_b_/c)") == (
        '<a href="a/_b_/c"><strong>b</strong> <code>x_y_</code></a>'
    )


def test_autolinks_at_the_start_and_in_the_middle_of_a_paragraph():
    assert markdown("<https://x.y/a_b_> is it, see <https://q.r/>.") == (
        '<p><a href="https://x.y/a_b_">https://x.y/a_b_</a> is it, '
        'see <a href="https://q.r/">https://q.r/</a>.</p>'
    )


def test_links_and_images_go_through_the_link_function():
    html = inline("[`x.txt`](x.txt) ![a picture](out/p.svg)", link=lambda url: "/" + url)
    assert html == '<a href="/x.txt"><code>x.txt</code></a> <img src="/out/p.svg" alt="a picture">'


def test_nested_lists_follow_indentation():
    text = "- one\n  continued\n- two:\n  - two a\n  - two b\n    continued\n- three\n"
    assert markdown(text) == (
        "<ul><li>one continued</li><li>two:<ul><li>two a</li>"
        "<li>two b continued</li></ul></li><li>three</li></ul>"
    )


def test_numbered_list():
    assert markdown("1. first\n2. second\n") == "<ol><li>first</li><li>second</li></ol>"


def test_list_right_after_a_paragraph_line_starts_a_list():
    assert (
        markdown("Two things:\n- a\n- b\n") == "<p>Two things:</p>\n<ul><li>a</li><li>b</li></ul>"
    )


def test_block_quote():
    assert (
        markdown("> Thanks for\n> writing.\n")
        == "<blockquote><p>Thanks for writing.</p></blockquote>"
    )


def test_raw_html_block_passes_through_with_urls_mapped():
    text = '<p align="center">\n  <a href="out/a.svg"><img src="out/a.svg" alt="x & y"></a>\n</p>\n'
    html = markdown(text, link=lambda url: "../" + url)
    assert html == (
        '<p align="center">\n'
        '  <a href="../out/a.svg"><img src="../out/a.svg" alt="x & y"></a>\n'
        "</p>"
    )


def test_summary_skips_title_and_pictures():
    text = "# T\n\n<p>\n<img src='x'>\n</p>\n\nFirst para\ncontinues.\n\nSecond.\n"
    assert build_site.summary_of(text) == "First para continues."


# --- links and the site -------------------------------------------------


def make_repo(root: Path) -> Path:
    (root / "journal").mkdir(parents=True)
    (root / "journal" / "2026-01-01.md").write_text(
        "# Day one\n\nSee [the demo](../projects/demo/).\n"
    )
    (root / "journal" / "2026-01-02.md").write_text(
        "# Day two\n\n[yesterday](2026-01-01.md#day-one), [manual](../CLAUDE.md), "
        "[tools](../tools), [web](https://example.com/a_b), [here](#day-two)\n"
    )
    demo = root / "projects" / "demo"
    (demo / "out").mkdir(parents=True)
    (demo / "out" / "pic.svg").write_text("<svg/>")
    (demo / "demo.py").write_text("")
    (demo / "README.md").write_text(
        "# The demo\n\nIt draws a picture.\n\n![pic](out/pic.svg) [code](demo.py) "
        "[journal](../../journal/2026-01-02.md) [home](../../README.md) [gone](out/gone.svg)\n"
    )
    (root / "tools").mkdir()
    return root


def test_resolve_maps_links_to_pages_assets_and_github(tmp_path):
    site = Site(make_repo(tmp_path))
    gh = build_site.REPO_URL
    page = "projects/demo/index.html"

    def r(target, source="projects/demo/README.md", page=page):
        return site.resolve(target, source, page)

    assert r("out/pic.svg") == "out/pic.svg"
    assert r("demo.py") == f"{gh}/blob/main/projects/demo/demo.py"
    assert r("out/gone.svg") == f"{gh}/blob/main/projects/demo/out/gone.svg"
    assert r("../../journal/2026-01-02.md") == "../../journal/2026-01-02.html"
    assert r("../../README.md") == "../../index.html"
    assert r("../../journal/") == "../../index.html#journal"
    assert r("./") == "index.html"
    j = "journal/2026-01-02.md"
    jp = "journal/2026-01-02.html"
    assert r("2026-01-01.md#day-one", j, jp) == "2026-01-01.html#day-one"
    assert r("../projects/demo/", j, jp) == "../projects/demo/index.html"
    assert r("../CLAUDE.md", j, jp) == f"{gh}/blob/main/CLAUDE.md"
    assert r("../tools", j, jp) == f"{gh}/tree/main/tools"
    for untouched in ("https://example.com/x", "#here", "/abs", "mailto:a@b.c"):
        assert r(untouched) == untouched


def local_targets(out: Path):
    """Every (page, local URL) pair in the built site."""
    for page in out.rglob("*.html"):
        for url in re.findall(r'(?:href|src)="([^"]+)"', page.read_text()):
            if not re.match(r"^[a-z]+:", url):
                yield page, url


def check_links(out: Path) -> int:
    checked = 0
    for page, url in local_targets(out):
        path, _, fragment = url.partition("#")
        target = page if not path else (page.parent / path).resolve()
        assert target.is_file(), f"{page.relative_to(out)} links to missing {url}"
        if fragment:
            assert f'id="{fragment}"' in target.read_text(), f"{page}: no anchor for {url}"
        checked += 1
    return checked


def test_build_writes_pages_assets_and_working_links(tmp_path):
    root = make_repo(tmp_path / "repo")
    out = tmp_path / "site"
    written = build(root, out)
    assert written == [
        "index.html",
        "journal/2026-01-01.html",
        "journal/2026-01-02.html",
        "projects/demo/index.html",
        "projects/demo/out/pic.svg",
    ]
    assert check_links(out) >= 10
    index = (out / "index.html").read_text()
    assert index.index("Day two") < index.index("Day one"), "newest journal day first"
    assert "It draws a picture." in index
    day_one = (out / "journal" / "2026-01-01.html").read_text()
    assert '<a href="2026-01-02.html">2026-01-02 →</a>' in day_one


def test_build_replaces_a_previous_build_but_not_other_directories(tmp_path):
    root = make_repo(tmp_path / "repo")
    out = tmp_path / "site"
    build(root, out)
    (out / "stale.html").write_text("old")
    build(root, out)
    assert not (out / "stale.html").exists()

    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("keep")
    try:
        build(root, precious)
    except FileExistsError:
        assert (precious / "keep.txt").read_text() == "keep"
        return
    raise AssertionError("expected FileExistsError")


def test_the_real_repository_builds_with_no_broken_links(tmp_path):
    out = tmp_path / "site"
    written = build(ROOT, out)
    projects = sorted(p.parent.name for p in (ROOT / "projects").glob("*/README.md"))
    days = sorted(p.stem for p in (ROOT / "journal").glob("*.md"))
    for slug in projects:
        assert f"projects/{slug}/index.html" in written
    for day in days:
        assert f"journal/{day}.html" in written
    assert check_links(out) > 0
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert text.count("<main>") == 1 and "</html>" in text
        # Nothing markdown-shaped should survive outside code.
        prose = re.sub(r"<(code|pre)[^>]*>.*?</\1>", "", text, flags=re.S)
        assert not re.search(r"\]\(|^#+ |\*\*", prose, re.M), page
        # No tag ever lands inside an attribute value.
        assert not re.search(r'="[^"]*<', text), page


def test_relative_urls_never_leave_the_site(tmp_path):
    out = tmp_path / "site"
    build(ROOT, out)
    for page, url in local_targets(out):
        rel = posixpath.normpath(posixpath.join(page.relative_to(out).parent.as_posix(), url))
        assert not rel.startswith(".."), f"{page} links outside the site: {url}"


def test_cli(tmp_path):
    out = tmp_path / "site"
    script = ROOT / "tools" / "build_site.py"
    result = subprocess.run(
        [sys.executable, str(script), "--out", str(out)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "pages and" in result.stdout and (out / "index.html").exists()
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "x").write_text("x")
    result = subprocess.run(
        [sys.executable, str(script), "--out", str(tmp_path / "other")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and "not empty" in result.stderr
