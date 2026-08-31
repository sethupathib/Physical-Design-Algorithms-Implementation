#!/usr/bin/env python3
"""Render WHITEAPER.md -> docs/iouring_fc_io_whitepaper.pdf"""
from pathlib import Path

import markdown
from weasyprint import HTML

root = Path(__file__).resolve().parents[1]
md_path = next(root.glob("WHITE*.md"))
body = markdown.markdown(
    md_path.read_text(encoding="utf-8"),
    extensions=["tables", "fenced_code", "sane_lists", "toc"],
)
figs = ""
for name in (
    "fig_architecture.png",
    "fig_workloads.png",
    "fig_speedup.png",
    "fig_claim_scope.png",
):
    p = root / "docs" / "figures" / name
    if p.exists():
        figs += f'<p><img src="{p}" style="max-width:100%;"/></p>\n'

html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>io_uring for Fusion Compiler Workflows</title>
<style>
@page {{ size: Letter; margin: 0.75in; }}
body {{ font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.35; color: #111; }}
h1 {{ font-size: 17pt; }} h2 {{ font-size: 13pt; margin-top: 1.1em; border-bottom: 1px solid #ccc; }}
h3 {{ font-size: 11.5pt; }}
code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; }}
pre {{ background: #f6f8fa; border: 1px solid #e1e4e8; padding: 0.55em 0.75em; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0 0.9em; font-size: 9.2pt; }}
th, td {{ border: 1px solid #ccc; padding: 0.25em 0.4em; vertical-align: top; }}
th {{ background: #f0f3f6; }}
blockquote {{ border-left: 3px solid #0ea5e9; margin: 0.6em 0; padding: 0.2em 0.8em; color: #333; }}
img {{ margin: 0.6em 0; }}
</style></head><body>{body}{figs}</body></html>"""

out = root / "docs" / "iouring_fc_io_whitepaper.pdf"
out.parent.mkdir(parents=True, exist_ok=True)
HTML(string=html, base_url=str(root / "docs")).write_pdf(out)
print(f"wrote {out} ({out.stat().st_size} bytes)")
