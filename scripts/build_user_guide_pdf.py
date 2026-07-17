#!/usr/bin/env python3
"""Regenerate a docs/*.md guide's PDF (markdown -> styled HTML -> headless
Chrome/Edge --print-to-pdf).

Requires: `pip install markdown` and Chrome or Edge installed.
Run from anywhere:  python scripts/build_user_guide_pdf.py [--src PATH] [--out PATH]
With no args, builds docs/user-guide.md -> docs/wxcc-skills-user-guide.pdf (the
original pair). Any other --src defaults --out to the same path with a .pdf
extension. Called automatically by hooks/pre-commit for each doc it lists.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO / "docs" / "user-guide.md"
DEFAULT_OUT = REPO / "docs" / "wxcc-skills-user-guide.pdf"

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { margin: 0.7in 0.75in; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; color: #16232e;
       margin: 0; line-height: 1.5; }
/* Cover band: styles the guide's H1 + first paragraph as a title block */
h1 { background: linear-gradient(135deg, #005073 0%, #049fd9 100%); color: #fff;
     font-size: 27pt; font-weight: 600; letter-spacing: -0.5px;
     padding: 42px 34px 14px 34px; margin: 0 0 0 0; border-radius: 0 0 0 18px; }
h1 + p { background: #005073; color: #cfeefb; font-size: 12.5pt; font-style: italic;
         padding: 0 34px 26px 34px; margin: 0 0 1.6em 0; border-radius: 0 0 18px 0; }
h2 { font-size: 14.5pt; color: #005073; font-weight: 600; margin: 1.7em 0 0.5em;
     padding-bottom: 3px; border-bottom: 2px solid #049fd9;
     page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #005073; margin: 1.3em 0 0.4em; page-break-after: avoid; }
p { margin: 0.5em 0; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 9pt;
       background: #f0f4f7; color: #0b3a52; padding: 1px 5px; border-radius: 3px; }
pre { background: #f5f8fa; border-left: 3px solid #049fd9; border-radius: 4px;
      padding: 10px 12px; overflow-x: auto; page-break-inside: avoid;
      white-space: pre-wrap; word-break: break-all; }
pre code { background: none; padding: 0; display: block; }
table { border-collapse: collapse; width: 100%; margin: 0.9em 0;
        page-break-inside: avoid; }
th { background: #005073; color: #fff; font-weight: 600; font-size: 9.5pt;
     padding: 7px 10px; text-align: left; }
td { border-bottom: 1px solid #dde5ea; padding: 6px 10px; font-size: 9.5pt;
     vertical-align: top; }
tr:nth-child(even) td { background: #f4f8fb; }
blockquote { background: #eef7fb; border-left: 4px solid #049fd9; border-radius: 4px;
             margin: 0.9em 0; padding: 8px 14px; color: #17455c;
             page-break-inside: avoid; }
blockquote p { margin: 0.2em 0; }
ul, ol { padding-left: 1.4em; }
li { margin: 0.25em 0; }
a { color: #0387b8; text-decoration: none; }
hr { border: none; border-top: 1px solid #c6d3db; margin: 1.6em 0; }
hr + p em { color: #5b7386; font-size: 9.5pt; }
"""


def find_browser() -> str:
    for b in BROWSERS:
        if Path(b).exists():
            return b
    sys.exit("error: no Chrome/Edge found for PDF printing.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    # Resolve to absolute before deriving --out or handing a path to the browser
    # subprocess: headless Chrome's --print-to-pdf does not honor this process's
    # cwd for a relative path, so a relative --out silently fails to write.
    args.src = args.src.resolve()
    args.out = (args.out.resolve() if args.out else None) or \
        (DEFAULT_OUT if args.src == DEFAULT_SRC else args.src.with_suffix(".pdf"))

    body = markdown.markdown(
        args.src.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code"],
    )
    html = f"<!doctype html><meta charset='utf-8'><style>{CSS}</style><body>{body}</body>"

    with tempfile.TemporaryDirectory() as td:
        html_file = Path(td) / "guide.html"
        html_file.write_text(html, encoding="utf-8")
        cmd = [
            find_browser(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
            f"--print-to-pdf={args.out}", html_file.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not args.out.exists() or args.out.stat().st_size == 0:
            sys.exit(f"error: PDF not produced.\n{res.stderr[-500:]}")
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
