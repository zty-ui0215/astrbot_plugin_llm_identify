from __future__ import annotations

from pathlib import Path


def write_pdf_report(title: str, body: str, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception:
        path.write_text(f"{title}\n\n{body}", encoding="utf-8")
        return path

    doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [Paragraph(_escape(title), styles["Title"]), Spacer(1, 12)]
    for line in body.splitlines():
        if not line.strip():
            story.append(Spacer(1, 8))
        else:
            story.append(Paragraph(_escape(line), styles["BodyText"]))
    doc.build(story)
    return path


def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
