import os
import posixpath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import build_site
import pytest
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


def test_nested_emphasis_always_closes_in_order():
    assert inline("**a *b* c**") == "<strong>a <em>b</em> c</strong>"
    html = inline("**bold *italic***")
    assert html == "<strong>bold *italic</strong>*"


def test_autolink_with_a_query_string():
    assert inline("<https://e.test/?a=1&b=2>") == (
        '<a href="https://e.test/?a=1&amp;b=2">https://e.test/?a=1&amp;b=2</a>'
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


def test_numbered_list_keeps_its_starting_number():
    assert markdown("3. third\n4. fourth\n") == '<ol start="3"><li>third</li><li>fourth</li></ol>'


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


def test_raw_html_urls_in_single_quotes_are_mapped_too():
    html = markdown("<p><a href='x.md'>x</a> <img src=\"a&amp;b.svg\"></p>", link=lambda u: "/" + u)
    assert html == '<p><a href="/x.md">x</a> <img src="/a&amp;b.svg"></p>'


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
    (demo / "out" / "charts").mkdir()
    (demo / "out" / "charts" / "c.svg").write_text("<svg/>")
    (demo / "demo.py").write_text("")
    (demo / "README.md").write_text(
        "# The demo\n\nIt draws a picture.\n\n![pic](out/pic.svg) [code](demo.py) "
        "[journal](../../journal/2026-01-02.md) [home](../../README.md) [gone](out/gone.svg)\n"
        "\n<p><img src='out/charts/c.svg'></p>\n"
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
        for url in re.findall(r"""(?:href|src)=["']([^"']+)""", page.read_text()):
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
        "feed.xml",
        "index.html",
        "journal/2026-01-01.html",
        "journal/2026-01-02.html",
        "projects/demo/index.html",
        "projects/demo/out/charts/c.svg",
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


def test_a_build_that_fails_halfway_can_be_retried(tmp_path, monkeypatch):
    root = make_repo(tmp_path / "repo")
    out = tmp_path / "site"

    def broken(self):
        raise OSError("disk full")

    monkeypatch.setattr(Site, "assets", broken)
    with pytest.raises(OSError):
        build(root, out)
    monkeypatch.undo()
    assert "index.html" in build(root, out)


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


# --- the feed -----------------------------------------------------------

NS = {"a": build_site.ATOM}


def parse_feed(out: Path):
    """(feed element, its entries) from a built site's feed.xml."""
    feed = ET.parse(out / "feed.xml").getroot()
    assert feed.tag == f"{{{build_site.ATOM}}}feed"
    return feed, feed.findall("a:entry", NS)


def field(element, tag: str) -> str:
    return element.findtext(f"a:{tag}", namespaces=NS)


def link_of(entry) -> str:
    return entry.find("a:link", NS).get("href")


def git(*args: str, cwd: Path, date: str | None = None):
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )


def test_feed_lists_the_days_newest_first_with_absolute_links(tmp_path):
    root = make_repo(tmp_path / "repo")
    out = tmp_path / "site"
    build(root, out)
    feed, entries = parse_feed(out)
    site = build_site.SITE_URL
    assert field(feed, "id") == site
    assert feed.find("a:link[@rel='self']", NS).get("href") == f"{site}feed.xml"
    assert field(feed, "title") == "claude"
    assert field(feed.find("a:author", NS), "name") == "Claude"
    assert [field(e, "title") for e in entries] == ["Day two", "Day one"]
    pages = [f"{site}journal/2026-01-02.html", f"{site}journal/2026-01-01.html"]
    assert [field(e, "id") for e in entries] == pages
    assert [link_of(e) for e in entries] == pages
    days = ["2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"]
    assert [field(e, "published") for e in entries] == days
    # Outside git, an entry is updated on its day and the feed on its newest day.
    assert [field(e, "updated") for e in entries] == days
    assert field(feed, "updated") == days[0]
    day_two = field(entries[0], "content")
    assert "<h1" not in day_two, "the title is the entry's <title>"
    assert f'<a href="{site}journal/2026-01-01.html#day-one">yesterday</a>' in day_two
    assert f'<a href="{build_site.REPO_URL}/blob/main/CLAUDE.md">manual</a>' in day_two
    assert '<a href="https://example.com/a_b">web</a>' in day_two
    assert f'<a href="{site}journal/2026-01-02.html#day-two">here</a>' in day_two
    day_one = field(entries[1], "content")
    assert f'<a href="{site}projects/demo/index.html">the demo</a>' in day_one


def test_feed_dates_an_entry_by_its_last_commit_only_in_a_full_checkout(tmp_path):
    root = make_repo(tmp_path / "repo")
    git("init", "-q", cwd=root)
    git("config", "user.email", "t@example.com", cwd=root)
    git("config", "user.name", "t", cwd=root)
    git("add", ".", cwd=root)
    git("commit", "-q", "-m", "both days", cwd=root, date="2026-01-01T23:59:00+00:00")
    build(root, tmp_path / "first")
    feed, entries = parse_feed(tmp_path / "first")
    # Day two was committed before its day began; an entry is never updated before it.
    assert [field(e, "updated") for e in entries] == [
        "2026-01-02T00:00:00Z",
        "2026-01-01T23:59:00Z",
    ]
    assert field(feed, "updated") == "2026-01-02T00:00:00Z"

    with (root / "journal" / "2026-01-02.md").open("a") as day_two:
        day_two.write("\nMore, later.\n")
    git("commit", "-q", "-a", "-m", "day two again", cwd=root, date="2026-01-05T06:07:08-04:00")
    build(root, tmp_path / "second")
    feed, entries = parse_feed(tmp_path / "second")
    assert [field(e, "updated") for e in entries] == [
        "2026-01-05T10:07:08Z",
        "2026-01-01T23:59:00Z",
    ]
    assert [field(e, "published") for e in entries] == [
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]
    assert field(feed, "updated") == "2026-01-05T10:07:08Z"

    # A shallow clone knows only its last commit, which would date every older
    # entry wrongly, so there the entries are dated by their file names.
    shallow = tmp_path / "shallow"
    git("clone", "-q", "--depth", "1", root.as_uri(), str(shallow), cwd=tmp_path)
    build(shallow, tmp_path / "shallow-site")
    _, entries = parse_feed(tmp_path / "shallow-site")
    assert [field(e, "updated") for e in entries] == [
        "2026-01-02T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]


def test_feed_keeps_only_the_newest_days(tmp_path):
    root = make_repo(tmp_path / "repo")
    for n in range(3, 26):
        (root / "journal" / f"2026-01-{n:02d}.md").write_text(f"# Day {n}\n\nText.\n")
    out = tmp_path / "site"
    build(root, out)
    _, entries = parse_feed(out)
    assert len(entries) == build_site.FEED_ENTRIES == 20
    assert field(entries[0], "title") == "Day 25"
    assert field(entries[-1], "title") == "Day 6"


def test_feed_titles_are_plain_text_and_content_has_no_control_characters(tmp_path):
    root = make_repo(tmp_path / "repo")
    (root / "journal" / "2026-01-01.md").write_text("# Day *one*,\x01 `again`\n\nA\x01B & C\n")
    out = tmp_path / "site"
    build(root, out)
    _, entries = parse_feed(out)
    assert field(entries[-1], "title") == "Day one, again"
    assert field(entries[-1], "content") == "<p>AB &amp; C</p>"


def test_a_journal_file_not_named_for_a_day_is_refused(tmp_path):
    root = make_repo(tmp_path / "repo")
    (root / "journal" / "2026-13-01.md").write_text("# Not a day\n")
    with pytest.raises(ValueError, match="2026-13-01.md"):
        build(root, tmp_path / "site")
    # Also one too old for the feed to keep, which would otherwise be left out quietly.
    (root / "journal" / "2026-13-01.md").unlink()
    for n in range(3, 24):
        (root / "journal" / f"2026-01-{n:02d}.md").write_text(f"# Day {n}\n")
    (root / "journal" / "2025-notes.md").write_text("# Notes\n")
    with pytest.raises(ValueError, match="2025-notes.md"):
        build(root, tmp_path / "site-2")


def test_every_page_advertises_the_feed(tmp_path):
    root = make_repo(tmp_path / "repo")
    out = tmp_path / "site"
    build(root, out)
    pages = list(out.rglob("*.html"))
    assert len(pages) == 4
    for page in pages:
        href = posixpath.relpath("feed.xml", page.parent.relative_to(out).as_posix())
        tag = f'<link rel="alternate" type="application/atom+xml" title="claude" href="{href}">'
        assert tag in page.read_text(), page


def test_the_real_feed_parses_and_points_at_built_pages(tmp_path):
    out = tmp_path / "site"
    build(ROOT, out)
    feed, entries = parse_feed(out)
    site = build_site.SITE_URL
    days = sorted(p.stem for p in (ROOT / "journal").glob("*.md"))
    expected = [f"{site}journal/{day}.html" for day in reversed(days)]
    assert [field(e, "id") for e in entries] == expected[: build_site.FEED_ENTRIES]
    stamp = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
    for entry in entries:
        assert stamp.fullmatch(field(entry, "published")) and stamp.fullmatch(
            field(entry, "updated")
        )
        assert field(entry, "updated") >= field(entry, "published")
        assert (out / link_of(entry).removeprefix(site)).is_file()
        content = field(entry, "content")
        assert "<h1" not in content, "a journal file starts with its # title, the entry's <title>"
        for url in re.findall(r"""(?:href|src)=["']([^"']+)""", content):
            assert re.match(r"^[a-z][a-z0-9+.-]*:", url), f"relative URL in the feed: {url}"
            if url.startswith(site):
                path, _, fragment = url.removeprefix(site).partition("#")
                assert (out / path).is_file(), url
                if fragment:
                    assert f'id="{fragment}"' in (out / path).read_text(), url
    assert field(feed, "updated") == max(field(e, "updated") for e in entries)
