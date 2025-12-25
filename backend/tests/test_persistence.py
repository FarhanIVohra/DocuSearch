import os
import json
import tempfile
import io
import zipfile
from backend.index.indexer import build_index
from backend.index.storage import save_index, load_index


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


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as docs_dir:
        pdf_path = os.path.join(docs_dir, "a.pdf")
        with open(pdf_path, "wb") as f:
            f.write(_make_minimal_pdf_bytes(["Search engines index documents"]))

        docx_path = os.path.join(docs_dir, "b.docx")
        with open(docx_path, "wb") as f:
            f.write(_make_docx_bytes("Search engines rank documents"))

        idx = build_index(docs_dir)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "index.json")
        save_index(idx, path)
        assert os.path.exists(path)

        loaded = load_index(path)
        # Basic keys presence and types
        for key in ["doc_id_map", "forward_index", "postings", "df", "idf", "N", "doc_norm"]:
            assert key in loaded
        assert isinstance(loaded["N"], int)
        # postings serialized as list of dicts
        for token, plist in loaded["postings"].items():
            assert isinstance(plist, list)
            if plist:
                assert "doc_id" in plist[0] and "tf" in plist[0]
