import io
import os
import tempfile
import zipfile

from backend.index.indexer import build_index
from backend.index import pdf_reader


def _make_docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>""",
        )
    return buf.getvalue()


def _make_minimal_pdf_bytes(lines: list[str]) -> bytes:
    escaped = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in lines]
    stream_lines = ["BT", "/F1 12 Tf", "50 150 Td"]
    for i, l in enumerate(escaped):
        if i > 0:
            stream_lines.append("0 -20 Td")
        stream_lines.append(f"({l}) Tj")
    stream_lines += ["ET"]
    stream = "\n".join(stream_lines).encode("ascii", errors="ignore")

    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    obj4 = b"4 0 obj\n<< >>\nstream\n" + stream + b"\nendstream\nendobj\n"
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    offsets = [0]
    parts = [header, obj1, obj2, obj3, obj4, obj5]
    acc = len(header)
    for part in parts[1:]:
        offsets.append(acc)
        acc += len(part)
    xref_start = acc

    xref = ["xref", "0 6", "0000000000 65535 f "]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n ")
    xref_bytes = ("\n".join(xref) + "\n").encode("ascii")
    trailer = b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_start).encode("ascii") + b"\n%%EOF\n"
    return b"".join(parts) + xref_bytes + trailer

def test_build_index():
    with tempfile.TemporaryDirectory() as docs_dir:
        pdf_path = os.path.join(docs_dir, "a.pdf")
        with open(pdf_path, "wb") as f:
            f.write(_make_minimal_pdf_bytes(["Search engines index documents", "Search indexing works"]))

        docx_path = os.path.join(docs_dir, "b.docx")
        with open(docx_path, "wb") as f:
            f.write(_make_docx_bytes("Search engines index documents. Search is fast."))

        index = build_index(docs_dir)

    assert len(index["doc_id_map"]) == 2
    assert len(index["forward_index"]) == 2

    print("\nDocuments indexed:")
    for doc_id, path in index["doc_id_map"].items():
        print(doc_id, path)

    print("\nForward index:")
    for doc_id, text in index["forward_index"].items():
        print(doc_id, "→", text)

    print("\n✅ INDEXING WORKS CORRECTLY")


def test_pdf_text_validation_rejects_garbled_text():
    garbled_single_letters = ("A B C D E F G H I J K L M N O P Q R S T U V W X Y Z " * 40).strip()
    score = pdf_reader._readability_score(pdf_reader._normalize_text_for_preview(garbled_single_letters))
    assert score < 0.55

    garbled_no_whitespace = ("Â" * 500).strip()
    score = pdf_reader._readability_score(pdf_reader._normalize_text_for_preview(garbled_no_whitespace))
    assert score < 0.55

if __name__ == "__main__":
    test_build_index()
