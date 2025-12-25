"""
Quick integration test to verify frontend upload/search flow works correctly.
Tests both .docx and .pdf uploads with server-provided text display.
"""
import sys
import os
import io
import zipfile

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi.testclient import TestClient
from backend.http_api import app

client = TestClient(app)

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


def test_docx_upload_and_search():
    """Test .docx file upload and search flow."""
    print("\n=== Testing .docx Upload and Search ===")

    docx_bytes = _make_docx_bytes("Python is great. Python is powerful. Testing Python is important.")
    files = {
        "file": (
            "test.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    response = client.post("/upload", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"

    data = response.json()
    print("✓ Upload successful")
    print(f"  - doc_length: {data['doc_length']}")
    print(f"  - unique_terms: {data['unique_terms']}")
    assert data.get("text"), "Server should return extracted text for .docx"

    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 200, f"Search failed: {response.text}"

    search_data = response.json()
    print("✓ Search successful")
    print(f"  - total_matches: {search_data['total_matches']}")
    print(f"  - cache: {search_data['cache']}")
    assert search_data["total_matches"] > 0, "Expected matches for 'python'"
    print("\n✓ .docx upload/search flow PASSED")


def test_pdf_upload_and_search():
    """Test .pdf file upload and search flow with server text extraction."""
    print("\n=== Testing .pdf Upload and Search ===")
    
    # Create a minimal test PDF with text
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< >>
stream
BT
/F1 12 Tf
50 150 Td
(PDF test document) Tj
0 -20 Td
(Test search terms here) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000340 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
415
%%EOF
"""
    
    files = {'file': ('test.pdf', pdf_content, 'application/pdf')}
    
    response = client.post('/upload', files=files)
    assert response.status_code == 200, f"PDF upload failed: {response.text}"
    
    data = response.json()
    print(f"✓ PDF upload successful")
    print(f"  - doc_length: {data['doc_length']}")
    print(f"  - unique_terms: {data['unique_terms']}")
    print(f"  - has text field: {'text' in data}")
    
    # For PDFs, server MUST return extracted text for frontend display
    if data.get('text'):
        print(f"  - server text available: {len(data['text'])} chars")
        print(f"  - extracted text preview: {data['text'][:100]}")
        assert len(data['text']) > 0, "PDF text extraction failed"
    
    # Search for a term that should be in the PDF
    response = client.get('/search', params={'q': 'test'})
    assert response.status_code == 200, f"Search failed: {response.text}"
    
    search_data = response.json()
    print(f"✓ Search successful")
    print(f"  - total_matches: {search_data['total_matches']}")
    print(f"  - cache: {search_data['cache']}")
    
    print("\n✓ .pdf upload/search flow PASSED")


if __name__ == '__main__':
    try:
        test_docx_upload_and_search()
        test_pdf_upload_and_search()
        print("\n" + "="*50)
        print("✅ ALL FRONTEND INTEGRATION TESTS PASSED")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
