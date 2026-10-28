import io, re, zipfile
from xml.sax.saxutils import escape


def make_docx(title, body):
    """Minimal dependency-free .docx writer. body is plain text; blank-line separated paragraphs; lines starting '# ' are headings."""
    def para(t, h=False):
        rpr = '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>' if h else ""
        return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>'
    parts = [para(title, True)]
    for line in (body or "").splitlines():
        parts.append(para(line[2:], True) if line.startswith("# ") else para(line))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{"".join(parts)}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def make_pdf(title, body):
    """PDF via reportlab if installed, else None."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except Exception:
        return None
    buf = io.BytesIO()
    st = getSampleStyleSheet()
    story = [Paragraph(escape(title), st["Title"]), Spacer(1, 12)]
    for line in (body or "").splitlines():
        story.append(Paragraph(escape(line) or "&nbsp;", st["Heading3"] if line.startswith("# ") else st["BodyText"]))
    SimpleDocTemplate(buf, pagesize=A4).build(story)
    return buf.getvalue()


def make_ics(events):
    """events: dicts with id, title, due_date (YYYY-MM-DD), description."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Legal S India//EN"]
    for e in events:
        d = e["due_date"].replace("-", "")
        lines += ["BEGIN:VEVENT", f"UID:lsi-{e['id']}@legal-s-india", f"DTSTAMP:{d}T000000Z", f"DTSTART;VALUE=DATE:{d}",
                  f"SUMMARY:{re.sub(r'[\r\n,;]', ' ', e['title'])}", f"DESCRIPTION:{re.sub(r'[\r\n,;]', ' ', e.get('description') or '')}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def redact(text, terms):
    for t in [t.strip() for t in terms if t and t.strip()]:
        text = re.sub(re.escape(t), "[REDACTED]", text, flags=re.I)
    return text
