"""Builds a tiny, valid one-page PDF. Used for demo data and tests, so no PDF library is needed."""


def make_pdf(title, lines=()):
    def esc(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content = f"BT /F1 16 Tf 72 720 Td ({esc(title)}) Tj ET\n"
    y = 690
    for line in lines:
        content += f"BT /F1 11 Tf 72 {y} Td ({esc(line)}) Tj ET\n"
        y -= 18
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out
