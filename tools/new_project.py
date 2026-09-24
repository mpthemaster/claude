"""Scaffold a new project directory under projects/.

Usage:
    python tools/new_project.py <slug> "One-line description"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

README = """# {title}

{description}

## Run

```sh
python projects/{slug}/{module}.py
pytest projects/{slug}
```

## Notes

(What it does, how it works, what you found.)
"""

MODULE = '''"""{description}"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    print("hello from {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

TEST = """import {module}


def test_main_runs():
    assert {module}.main([]) == 0
"""


def create(root: Path, slug: str, description: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("slug must be lowercase letters, digits and hyphens")
    target = root / "projects" / slug
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    module = slug.replace("-", "_")
    title = slug.replace("-", " ").title()
    target.mkdir(parents=True)
    fill = {"slug": slug, "module": module, "title": title, "description": description}
    (target / "README.md").write_text(README.format(**fill))
    (target / f"{module}.py").write_text(MODULE.format(**fill))
    (target / f"test_{module}.py").write_text(TEST.format(**fill))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a project.")
    parser.add_argument("slug")
    parser.add_argument("description")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    target = create(args.root, args.slug, args.description)
    print(f"created {target.relative_to(args.root)}")
    print("next: add a row to the projects table in README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
