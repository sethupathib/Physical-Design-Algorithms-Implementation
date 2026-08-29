#!/usr/bin/env python3
from pathlib import Path
import markdown
from weasyprint import HTML

root = Path(__file__).resolve().parents[1]
md_path = next(root.glob("WHITE*.md"))
body = markdown.markdown(md_path.read_text(encoding="utf-8"),
                         extensions=["tables", "fenced_code", "sane_lists"])
figs = ""
for name in ("fig_chipmind_mapping.png", "fig_causal_chain.png", "fig_accuracy_snapshot.png"):
    p = root / "docs" / "figures" / name
    if p.exists():
        figs += f'<p><img src="{p}" style="max-width:100%"/></p>'
html = f"""<!doctype html><html><head><meta charset="utf-8"/>
<style>
@page {{ size: Letter; margin: 0.75in; }}
body {{ font-family: DejaVu Serif, Georgia, serif; font-size: 10.5pt; }}
h1 {{ font-size: 17pt; }} h2 {{ font-size: 13pt; border-bottom: 1px solid #ccc; }}
code, pre {{ font-family: DejaVu Sans Mono, monospace; font-size: 8.6pt; }}
pre {{ background: #f6f8fa; padding: 0.5em; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.2pt; }}
th, td {{ border: 1px solid #ccc; padding: 0.25em 0.4em; }}
th {{ background: #f0f3f6; }}
</style></head><body>{body}{figs}</body></html>"""
out = root / "docs" / "pdkg_whitepaper.pdf"
HTML(string=html, base_url=str(root / "docs")).write_pdf(out)
print(f"wrote {out} ({out.stat().st_size} bytes)")
