"""Build docs/FSP_Talent_documentation.pdf from the Markdown documents (TZ 5.2: documentation in doc or pdf).

Requirements (only for whoever rebuilds the PDF, not for running the platform):
    pip install markdown playwright && playwright install chromium
    npm install --prefix docs/tools mermaid@11
    cd frontend && npm ci          # fonts of the brand book come from @fontsource

    python docs/tools/build_pdf.py
    python docs/tools/build_pdf.py --pitch   # HTML-черновик слайдов решения; сдача — PDF из pitch.pptx в PowerPoint
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
OUT = DOCS / "FSP_Talent_documentation.pdf"
REPO = "https://github.com/KonkovDV/fsp-talent/blob/main/"
MERMAID = DOCS / "tools" / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
FONTS = ROOT / "frontend" / "node_modules" / "@fontsource-variable"

# Order follows TZ 3.4: the main document first, then the details it links to.
PARTS = [
    ("SOLUTION.md", "Сопроводительная документация"),
    ("REQUIREMENTS.md", "Соответствие техническому заданию"),
    ("INSTALL.md", "Сборка, развёртывание и запуск"),
    ("USER_GUIDE.md", "Руководство пользователя стенда"),
    ("VALIDATION_ASSESSMENT.md", "Проверка теста на грейд"),
    ("VALIDATION_MATCHING.md", "Проверка подбора"),
    ("LOAD_TEST.md", "Нагрузочная проверка"),
    ("FSP_INTEGRATION.md", "Интеграция с ФСП"),
    ("TRUST_AND_ATS.md", "Защита от фиктивных вакансий и ATS"),
    ("API_ERRORS.md", "Коды ошибок API"),
    ("DESIGN.md", "Дизайн-система"),
    ("THIRD_PARTY.md", "Сторонние компоненты и лицензии"),
]


def _links(text: str, name: str) -> str:
    """Relative links point to the repository: the PDF travels without the files next to it."""
    def fix(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            return m.group(0)
        if target.startswith("#"):
            target = f"docs/{name}{target}"
        elif target.startswith("../"):
            target = target[3:]
        elif not target.startswith("docs/"):
            target = f"docs/{target}"
        return f"[{label}]({REPO}{target})"
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", fix, text)


def _part(name: str, index: int) -> str:
    text = _links((DOCS / name).read_text(encoding="utf-8"), name)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # Pictures sit next to the Markdown in docs/; the HTML is loaded without a base URL.
    body = re.sub(r'<img src="(?!https?:|file:)([^"]+)"', lambda m: f'<img src="{(DOCS / m.group(1)).as_uri()}"', body)
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  lambda m: f'<div class="mermaid">{m.group(1)}</div>', body, flags=re.S)
    return f'<section class="part" id="part-{index}">{body}</section>'


def _font_face() -> str:
    faces = []
    for family, folder in (("Golos Text", "golos-text"), ("JetBrains Mono", "jetbrains-mono")):
        for file in sorted((FONTS / folder / "files").glob("*-wght-normal.woff2")):
            faces.append(f"@font-face{{font-family:'{family}';src:url('{file.as_uri()}') format('woff2');"
                         "font-weight:100 900;font-style:normal;}")
    return "\n".join(faces)


CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
html { font-family: 'Golos Text', sans-serif; font-size: 10pt; color: #1B1C21; line-height: 1.5; }
h1, h2, h3, h4 { font-family: 'JetBrains Mono', monospace; line-height: 1.25; color: #1B1C21; }
h1 { font-size: 19pt; margin: 0 0 10pt; padding-bottom: 6pt; border-bottom: 3pt solid #402FFF; }
h2 { font-size: 13.5pt; margin: 16pt 0 6pt; color: #2A1DD6; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; break-after: avoid; }
.part { break-before: page; }
p, li { orphans: 3; widows: 3; }
a { color: #2A1DD6; text-decoration: none; }
code { font-family: 'JetBrains Mono', monospace; font-size: 8.6pt; background: #F1F1F4; padding: 0 2pt; border-radius: 2pt; }
pre { background: #F4F4F7; border: 0.6pt solid #DADAE2; border-radius: 4pt; padding: 7pt 9pt; white-space: pre-wrap;
      break-inside: avoid; font-size: 8.4pt; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.6pt; break-inside: auto; }
th { background: #EEEDFF; color: #1B1C21; text-align: left; font-weight: 600; }
th, td { border: 0.6pt solid #CFCFDA; padding: 3pt 5pt; vertical-align: top; }
tr { break-inside: avoid; }
blockquote { margin: 8pt 0; padding: 4pt 10pt; border-left: 3pt solid #402FFF; background: #F5F4FF; }
details > summary { font-weight: 600; }
.mermaid { text-align: center; margin: 8pt 0; break-inside: avoid; }
.mermaid svg { max-width: 100%; height: auto; }
.part img { max-width: 100%; height: auto; break-inside: avoid; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover img { width: 70mm; }
.cover .title { font-family: 'JetBrains Mono', monospace; font-size: 26pt; font-weight: 700; line-height: 1.15; margin-top: 30mm; }
.cover .lead { font-size: 12pt; color: #3B3C46; max-width: 140mm; margin-top: 8pt; }
.cover .band { height: 6pt; background: linear-gradient(90deg, #402FFF 85%, #EC1D35 85%); margin: 14pt 0; }
.toc { break-before: page; }
.toc ol { font-size: 11pt; line-height: 1.9; }
"""


def build() -> Path:
    if not MERMAID.is_file():
        sys.exit(f"mermaid not found: {MERMAID}. Run: npm install --prefix docs/tools mermaid@11")
    today = dt.date.today().strftime("%d.%m.%Y")
    toc = "".join(f'<li><a href="#part-{i}">{html.escape(title)}</a></li>' for i, (_, title) in enumerate(PARTS))
    cover = f"""
<section class="cover">
  <div>
    <img src="{(DOCS / 'assets' / 'logo.png').as_uri()}" alt="ФСП Талант">
    <div class="title">ФСП Талант<br>Сопроводительная документация</div>
    <div class="lead" style="margin-top:6pt">команда Дмитрия Конькова</div>
    <div class="band"></div>
    <div class="lead">Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника
      Федерации спортивного программирования. ЛЦТ 2026, раздел 3.4 технического задания.</div>
  </div>
  <div class="lead">Репозиторий: https://github.com/KonkovDV/fsp-talent<br>Сборка документа: {today}<br>
    Исходные тексты — Markdown в каталоге docs/, этот файл собран скриптом docs/tools/build_pdf.py.</div>
</section>
<section class="toc"><h1>Содержание</h1><ol>{toc}</ol></section>"""
    parts = "".join(_part(name, i) for i, (name, _) in enumerate(PARTS))
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>{_font_face()}{CSS}</style></head>
<body>{cover}{parts}
<script src="{MERMAID.as_uri()}"></script>
<script>
mermaid.initialize({{startOnLoad: false, theme: 'neutral', fontFamily: 'Golos Text', themeVariables: {{fontSize: '15px'}},
  flowchart: {{htmlLabels: true, useMaxWidth: true}}, sequence: {{useMaxWidth: true}}}});
mermaid.run({{querySelector: '.mermaid'}}).then(() => document.body.dataset.ready = '1');
</script></body></html>"""
    tmp = DOCS / "tools" / "documentation.html"
    tmp.write_text(page, encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        tab = browser.new_page()
        tab.on("pageerror", lambda e: print("page error:", e, file=sys.stderr))
        tab.goto(tmp.as_uri())
        tab.wait_for_selector("body[data-ready='1']", timeout=60_000)
        tab.wait_for_timeout(500)
        tab.pdf(path=str(OUT), format="A4", print_background=True, display_header_footer=True,
                header_template="<span></span>",
                footer_template=('<div style="font-size:7pt;color:#777;width:100%;padding:0 16mm;'
                                 'display:flex;justify-content:space-between;font-family:sans-serif">'
                                 '<span>ФСП Талант · сопроводительная документация</span>'
                                 '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'),
                margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        browser.close()
    tmp.unlink()
    return OUT


def build_pitch() -> Path:
    """Print the slides that docs/tools/build_pitch.mjs wrote, one slide per page."""
    out = DOCS / "pitch.pdf"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        tab = browser.new_page()
        tab.goto((DOCS / "pitch.html").as_uri())
        tab.wait_for_load_state("networkidle")
        tab.pdf(path=str(out), width="13.333in", height="7.5in", print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        browser.close()
    return out


if __name__ == "__main__":
    print(build_pitch() if "--pitch" in sys.argv else build())
