#!/usr/bin/env python3
"""Render WHITEPAPER.md -> docs/pd_tmpfs_rsync_whitepaper.pdf"""
from pathlib import Path
import markdown
from weasyprint import HTML

root = Path(__file__).resolve().parents[1]
md = (root / "WHITEPAPER.md").read_text(encoding="utf-8")
html_body = markdown.markdown(
    md,
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)
html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>Accelerating Physical Design Jobs with tmpfs and rsync</title>
<style>
@page {{ size: Letter; margin: 0.85in; }}
body {{ font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.35; color: #111; }}
h1 {{ font-size: 18pt; }}
h2 {{ font-size: 13pt; margin-top: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.15em; }}
h3 {{ font-size: 11.5pt; margin-top: 0.9em; }}
code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 8.8pt; }}
pre {{ background: #f6f8fa; border: 1px solid #e1e4e8; padding: 0.6em 0.8em; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.6em 0 1em; font-size: 9.5pt; }}
th, td {{ border: 1px solid #ccc; padding: 0.28em 0.45em; vertical-align: top; }}
th {{ background: #f0f3f6; }}
blockquote {{ border-left: 3px solid #888; margin-left: 0; padding-left: 0.8em; color: #333; }}
</style></head><body>{html_body}</body></html>
"""
out = root / "docs" / "pd_tmpfs_rsync_whitepaper.pdf"
HTML(string=html, base_url=str(out.parent)).write_pdf(out)
print(f"wrote {out} ({out.stat().st_size} bytes)")
