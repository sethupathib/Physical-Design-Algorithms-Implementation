#!/usr/bin/env python3
"""Render WHITEPAPER.md -> docs/vortex_vs_adhoc_whitepaper.pdf"""
from pathlib import Path

import markdown
from weasyprint import HTML

root = Path(__file__).resolve().parents[1]
md = (root / "WHITEPAPER.md").read_text(encoding="utf-8")
body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "sane_lists"])
html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>Policy-as-Code vs Ad-Hoc Scripting for PD Log Forensics</title>
<style>
@page {{ size: Letter; margin: 0.8in; }}
body {{ font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.35; color: #111; }}
h1 {{ font-size: 17pt; }} h2 {{ font-size: 13pt; margin-top: 1.1em; border-bottom: 1px solid #ccc; }}
h3 {{ font-size: 11.5pt; }}
code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; }}
pre {{ background: #f6f8fa; border: 1px solid #e1e4e8; padding: 0.55em 0.75em; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0 0.9em; font-size: 9.2pt; }}
th, td {{ border: 1px solid #ccc; padding: 0.25em 0.4em; vertical-align: top; }}
th {{ background: #f0f3f6; }}
</style></head><body>{body}</body></html>"""
out = root / "docs" / "vortex_vs_adhoc_whitepaper.pdf"
out.parent.mkdir(parents=True, exist_ok=True)
HTML(string=html, base_url=str(root / "docs")).write_pdf(out)
print(f"wrote {out} ({out.stat().st_size} bytes)")
