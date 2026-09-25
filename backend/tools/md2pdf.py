"""Сборка PDF-версий документации из Markdown.

docker compose run --rm -v ./docs:/docs backend sh -c \
  "pip install --user -q markdown==3.7 && python tools/md2pdf.py /docs/user-guide.md /docs/user-guide.pdf"
"""
import sys
from datetime import date
from pathlib import Path

import markdown
from weasyprint import HTML

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 18mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #777; } }
body { font-family: "DejaVu Sans", sans-serif; font-size: 10pt; line-height: 1.5; color: #111; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; border-bottom: 1pt solid #ccc; padding-bottom: 3pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; page-break-inside: auto; }
th, td { border: 0.6pt solid #999; padding: 3pt 6pt; vertical-align: top; text-align: left; }
th { background: #f1f3f5; }
tr { page-break-inside: avoid; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt; background: #f1f3f5; padding: 0 2pt; }
.meta { color: #555; margin-bottom: 16pt; }
"""


def main(src: str, dst: str) -> None:
    text = Path(src).read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>" \
           f"{body.replace('</h1>', f'</h1><div class=meta>Версия 1.0 · {date.today():%d.%m.%Y}</div>', 1)}</body></html>"
    HTML(string=html).write_pdf(dst)
    print(f"Готово: {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
