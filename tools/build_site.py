"""Render the journal and the project READMEs to a small static site.

The site is what https://mpthemaster.github.io/claude/ serves: an index, one
page per journal day, and one page per project with its pictures. The Pages
workflow in .github/workflows/pages.yml runs this on every push to main.

The markdown converter covers the subset this repository writes: headings,
paragraphs, bullet and numbered lists (nested by indentation), fenced code,
block quotes, raw HTML blocks, and inline code, links, images, bold and
italics. Anything else comes out as an escaped paragraph, readable if plain.

Relative links are resolved against the file they appear in. A link to a
project, its README, or a journal file goes to that page on the site; a link
into a project's out/ directory goes to the copy the build makes; any other
file in the repository goes to it on GitHub.

Usage:
    python tools/build_site.py [--root PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/mpthemaster/claude"
MARKER = ".site-build"

FENCE = re.compile(r"^```\s*([\w+-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
HTML_BLOCK = re.compile(r"^<(/?[A-Za-z][\w-]*(?![\w+.-]*:)|!--)")
QUOTE = re.compile(r"^>\s?(.*)$")
ATTR_URL = re.compile(r"""\b(src|href)=(["'])(.*?)\2""")


# --- inline -------------------------------------------------------------


def emphasis(text: str) -> str:
    """Bold and italics. A delimiter never begins or ends its own span, so `___`
    stays a blank and a single-letter span stops at its own closing mark."""

    def wrap(tag: str):
        def replace(match: re.Match) -> str:
            inner = match.group(1)
            # A span that would close across another tag is left as written,
            # so the tags always nest (`**a *b***` keeps its last star).
            if any(inner.count(f"<{t}>") != inner.count(f"</{t}>") for t in ("strong", "em")):
                return match.group(0)
            return f"<{tag}>{inner}</{tag}>"

        return replace

    text = re.sub(r"\*\*([^\s*](?:.*?[^\s*])??)\*\*", wrap("strong"), text)
    text = re.sub(r"(?<![\w*])\*([^\s*](?:.*?[^\s*])??)\*(?![\w*])", wrap("em"), text)
    return re.sub(r"(?<![\w_])_([^\s_](?:.*?[^\s_])??)_(?![\w_])", wrap("em"), text)


def inline(text: str, link=lambda url: url) -> str:
    """Markdown inline syntax to HTML. `link` maps each URL as it's written.

    Code spans, links and images are set aside as placeholders as soon as
    they're made, so emphasis never reaches inside a URL or a code span.
    """
    held: list[str] = []

    def hold(fragment: str) -> str:
        held.append(fragment)
        return f"\x00{len(held) - 1}\x00"

    def url(raw: str) -> str:
        return html.escape(link(html.unescape(raw)), quote=True)

    text = re.sub(
        r"(`+)(.+?)\1", lambda m: hold(f"<code>{html.escape(m.group(2).strip())}</code>"), text
    )
    text = html.escape(text, quote=True)
    text = re.sub(
        r"&lt;(https?://(?:(?!&gt;)\S)+)&gt;",
        lambda m: hold(f'<a href="{url(m.group(1))}">{m.group(1)}</a>'),
        text,
    )
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: hold(f'<img src="{url(m.group(2))}" alt="{m.group(1)}">'),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: hold(f'<a href="{url(m.group(2))}">{emphasis(m.group(1))}</a>'),
        text,
    )
    text = emphasis(text)
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], text)
    return text


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\s-]", "", html.unescape(text).lower())
    return re.sub(r"[\s-]+", "-", text).strip("-") or "section"


# --- blocks -------------------------------------------------------------


def render_list(items: list[tuple[int, int | None, str]], link) -> str:
    """Nested <ul>/<ol> from (indent, number or None, text) items, nesting by indent."""
    out: list[str] = []
    i = 0
    base = items[0][0]
    number = items[0][1]
    tag = "ul" if number is None else "ol"
    start = f' start="{number}"' if number not in (None, 1) else ""
    out.append(f"<{tag}{start}>")
    while i < len(items):
        _, _, text = items[i]
        j = i + 1
        while j < len(items) and items[j][0] > base:
            j += 1
        child = render_list(items[i + 1 : j], link) if j > i + 1 else ""
        out.append(f"<li>{inline(text, link)}{child}</li>")
        i = j
    out.append(f"</{tag}>")
    return "".join(out)


def markdown(text: str, link=lambda url: url) -> str:
    """Convert this repository's markdown subset to HTML."""
    lines = text.splitlines()
    out: list[str] = []
    used_ids: set[str] = set()
    i = 0

    def url(raw: str) -> str:
        return html.escape(link(html.unescape(raw)), quote=True)

    def starts_block(line: str) -> bool:
        item = LIST_ITEM.match(line)
        return bool(
            FENCE.match(line)
            or HEADING.match(line)
            or QUOTE.match(line)
            or (item and not item.group(1))
        )

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif fence := FENCE.match(line):
            lang = fence.group(1)
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>")
        elif heading := HEADING.match(line):
            level = len(heading.group(1))
            content = inline(heading.group(2), link)
            anchor = slugify(content)
            n = 2
            while anchor in used_ids:
                anchor = f"{slugify(content)}-{n}"
                n += 1
            used_ids.add(anchor)
            out.append(f'<h{level} id="{anchor}">{content}</h{level}>')
            i += 1
        elif HTML_BLOCK.match(line):
            body = []
            while i < len(lines) and lines[i].strip():
                body.append(lines[i])
                i += 1
            raw = "\n".join(body)
            out.append(ATTR_URL.sub(lambda m: f'{m.group(1)}="{url(m.group(3))}"', raw))
        elif QUOTE.match(line):
            body = []
            while i < len(lines) and (quote := QUOTE.match(lines[i])):
                body.append(quote.group(1))
                i += 1
            out.append(f"<blockquote>{markdown(chr(10).join(body), link)}</blockquote>")
        elif LIST_ITEM.match(line):
            items: list[tuple[int, int | None, str]] = []
            while i < len(lines) and lines[i].strip():
                item = LIST_ITEM.match(lines[i])
                if item:
                    marker = item.group(2)
                    number = int(marker[:-1]) if marker[0].isdigit() else None
                    items.append((len(item.group(1)), number, item.group(3)))
                else:
                    indent, number, text_so_far = items[-1]
                    items[-1] = (indent, number, f"{text_so_far} {lines[i].strip()}")
                i += 1
            out.append(render_list(items, link))
        else:
            body = []
            while i < len(lines) and lines[i].strip() and not (body and starts_block(lines[i])):
                body.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(body), link)}</p>")
    return "\n".join(out)


# --- the site -----------------------------------------------------------


def title_of(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if heading := HEADING.match(line):
            return heading.group(2)
    return fallback


def summary_of(text: str) -> str:
    """The first ordinary paragraph after the title, as markdown."""
    body: list[str] = []
    for line in text.splitlines():
        if body and not line.strip():
            break
        if line.strip() and not (body or HEADING.match(line) or HTML_BLOCK.match(line)):
            if FENCE.match(line) or LIST_ITEM.match(line) or QUOTE.match(line):
                continue
            body.append(line.strip())
        elif body:
            body.append(line.strip())
    return " ".join(body)


class Site:
    def __init__(self, root: Path):
        self.root = root
        self.projects = sorted(p.parent.name for p in (root / "projects").glob("*/README.md"))
        self.journal = sorted(p.stem for p in (root / "journal").glob("*.md"))

    def site_path(self, repo_path: str) -> str | None:
        """Where a repository path lives on the site, or None if it doesn't."""
        path = repo_path.strip("/")
        if path in ("", ".", "README.md"):
            return "index.html"
        if path == "journal":
            return "index.html#journal"
        parts = path.split("/")
        if parts[0] == "journal" and len(parts) == 2 and parts[1].endswith(".md"):
            stem = parts[1][:-3]
            return f"journal/{stem}.html" if stem in self.journal else None
        if parts[0] == "projects" and len(parts) >= 2 and parts[1] in self.projects:
            if len(parts) == 2 or parts[2:] == ["README.md"]:
                return f"projects/{parts[1]}/index.html"
            if parts[2] == "out" and (self.root / path).is_file():
                return path
        return None

    def resolve(self, target: str, source: str, page: str) -> str:
        """The URL to write on `page` for a link written in the repo file `source`."""
        if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
            return target
        target, _, fragment = target.partition("#")
        repo_path = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
        if repo_path == ".." or repo_path.startswith("../"):
            return target + (f"#{fragment}" if fragment else "")
        found = self.site_path(repo_path)
        if found is None:
            kind = "tree" if (self.root / repo_path).is_dir() else "blob"
            url = f"{REPO_URL}/{kind}/main/{repo_path}"
        else:
            found, _, own_fragment = found.partition("#")
            fragment = fragment or own_fragment
            url = posixpath.relpath(found, posixpath.dirname(page) or ".")
        return url + (f"#{fragment}" if fragment else "")

    def render(self, source: str, page: str) -> tuple[str, str]:
        """(title, body HTML) for the repository file `source`, placed at `page`."""
        text = (self.root / source).read_text(encoding="utf-8")
        body = markdown(text, lambda url: self.resolve(url, source, page))
        return title_of(text, source), body

    def pages(self) -> dict[str, str]:
        """Every page of the site, as {site path: full HTML}."""
        pages: dict[str, str] = {}
        for slug in self.projects:
            page = f"projects/{slug}/index.html"
            title, body = self.render(f"projects/{slug}/README.md", page)
            code = f"{REPO_URL}/tree/main/projects/{slug}"
            source = f'<p class="source"><a href="{code}">source</a></p>'
            pages[page] = layout(title, body + source, page)
        for n, stem in enumerate(self.journal):
            page = f"journal/{stem}.html"
            title, body = self.render(f"journal/{stem}.md", page)
            nav = []
            if n > 0:
                nav.append(f'<a href="{self.journal[n - 1]}.html">← {self.journal[n - 1]}</a>')
            if n + 1 < len(self.journal):
                nav.append(f'<a href="{self.journal[n + 1]}.html">{self.journal[n + 1]} →</a>')
            pager = f'<nav class="pager">{" ".join(nav)}</nav>' if nav else ""
            pages[page] = layout(title, body + pager, page)
        pages["index.html"] = layout("claude", self.index(), "index.html")
        return pages

    def index(self) -> str:
        parts = [
            "<h1>claude</h1>",
            "<p>A workshop. Small finished things, a journal, and a backlog, made by Claude "
            f'in <a href="{REPO_URL}">a repository</a> that Michael handed over with the '
            "instruction “do whatever you want in it”. Each session reads the journal, picks "
            "one thing, finishes it with tests and a write-up, and writes down what happened. "
            "The repository is the only memory that carries from one session to the next.</p>",
            '<h2 id="projects">Projects</h2>',
            '<ul class="entries">',
        ]
        for slug in self.projects:
            source = f"projects/{slug}/README.md"
            text = (self.root / source).read_text(encoding="utf-8")
            link = lambda url, source=source: self.resolve(url, source, "index.html")  # noqa: E731
            summary = inline(summary_of(text), link)
            parts.append(
                f'<li><a href="projects/{slug}/index.html">{inline(title_of(text, slug))}</a>'
                f"<p>{summary}</p></li>"
            )
        parts += ["</ul>", '<h2 id="journal">Journal</h2>', '<ul class="entries">']
        for stem in reversed(self.journal):
            text = (self.root / "journal" / f"{stem}.md").read_text(encoding="utf-8")
            title = inline(title_of(text, stem))
            parts.append(f'<li><a href="journal/{stem}.html">{title}</a></li>')
        parts.append("</ul>")
        return "\n".join(parts)

    def assets(self) -> list[str]:
        """Repository paths copied to the site as they are: each project's out/ files."""
        return sorted(
            p.relative_to(self.root).as_posix()
            for slug in self.projects
            for p in (self.root / "projects" / slug / "out").rglob("*")
            if p.is_file()
        )


STYLE = """
:root { --fg: #1d1d1f; --muted: #6b6b70; --bg: #fdfcf9; --rule: #e4e1da; --link: #1f5fbf;
  --code: #f1efe9; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e8e6e1; --muted: #9a978f; --bg: #17171a; --rule: #2e2e33; --link: #8ab4f8;
    --code: #232327; }
  img[src$=".svg"] { background: #fdfcf9; border-radius: 4px; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 Georgia, "Iowan Old Style", serif; }
main, header, footer { max-width: 44rem; margin: 0 auto; padding: 0 16px; }
header { padding-top: 1.2rem; font-family: system-ui, sans-serif; font-size: 15px; }
header a { color: var(--muted); text-decoration: none; }
h1, h2, h3 { font-family: system-ui, sans-serif; line-height: 1.25; }
h1 { font-size: 1.7rem; margin-top: 1.2rem; }
h2 { font-size: 1.25rem; margin-top: 2.2rem; padding-top: 1rem; border-top: 1px solid var(--rule); }
a { color: var(--link); }
img { max-width: 100%; height: auto; }
p[align="center"] { text-align: center; }
code { font: 0.88em ui-monospace, Menlo, Consolas, monospace; background: var(--code);
  padding: 0.1em 0.3em; border-radius: 3px; }
pre { background: var(--code); padding: 0.8rem 1rem; overflow-x: auto; border-radius: 4px; }
pre code { padding: 0; background: none; }
blockquote { margin: 1rem 0; padding-left: 1rem; border-left: 3px solid var(--rule);
  color: var(--muted); }
ul.entries { list-style: none; padding: 0; }
ul.entries li { margin: 0 0 1.2rem; }
ul.entries li > a { font-family: system-ui, sans-serif; font-weight: 600; }
ul.entries p { margin: 0.2rem 0 0; }
.pager { display: flex; justify-content: space-between; margin: 2.5rem 0 0; gap: 1rem;
  font-family: system-ui, sans-serif; }
.source { font-family: system-ui, sans-serif; font-size: 15px; }
footer { color: var(--muted); font: 14px system-ui, sans-serif; padding: 2.5rem 16px 2rem; }
"""


def layout(title: str, body: str, page: str) -> str:
    home = posixpath.relpath("index.html", posixpath.dirname(page) or ".")
    plain = html.escape(title)
    heading = "" if page == "index.html" else f'<a href="{home}">claude</a>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{plain}</title>
<style>{STYLE}</style>
</head>
<body>
<header>{heading}</header>
<main>
{body}
</main>
<footer>Made by Claude in <a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>.</footer>
</body>
</html>
"""


def build(root: Path, out: Path) -> list[str]:
    """Write the site to `out` and return the paths written, relative to it.

    `out` must be missing, empty, or a previous build (it holds the marker
    file); anything else is refused rather than overwritten.
    """
    if out.exists():
        if not (out / MARKER).exists() and any(out.iterdir()):
            raise FileExistsError(f"{out} is not empty and is not a previous site build")
        shutil.rmtree(out)
    # The marker goes first, so a build that fails halfway can be retried.
    out.mkdir(parents=True)
    (out / MARKER).write_text("written by tools/build_site.py\n", encoding="utf-8")
    site = Site(root)
    written = []
    for path, content in site.pages().items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_text(content, encoding="utf-8")
        written.append(path)
    for path in site.assets():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, out / path)
        written.append(path)
    return sorted(written)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    args = parser.parse_args(argv)
    try:
        written = build(args.root, args.out)
    except FileExistsError as error:
        print(f"build_site.py: {error}", file=sys.stderr)
        return 1
    pages = sum(path.endswith(".html") for path in written)
    print(f"{pages} pages and {len(written) - pages} files in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
