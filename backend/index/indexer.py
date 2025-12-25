import os
import math
import io
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from typing import Dict, List, Any
from .preprocess import preprocess
from .pdf_reader import extract_text_from_pdf, PDFExtractionError


def extract_text_from_docx(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError as e:
            raise ValueError("Not a valid .docx file") from e

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs = []
    for p in root.findall(".//w:p", ns):
        texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
        if texts:
            paragraphs.append("".join(texts))

    return "\n".join(paragraphs)

def build_index(documents_dir):
    """
    Builds:
    - doc_id_map: {doc_id -> file_path}
    - forward_index: {doc_id -> raw_text}
    Additionally builds an inverted index and stats needed for ranking.
    """

    doc_id_map = {}
    forward_index = {}
    postings: Dict[str, List[Dict[str, int]]] = defaultdict(list)
    df: Dict[str, int] = defaultdict(int)

    doc_id = 0

    for filename in sorted(os.listdir(documents_dir)):
        file_path = os.path.join(documents_dir, filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".pdf", ".docx", ".doc"]:
            continue

        if ext == ".pdf":
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            try:
                text = extract_text_from_pdf(pdf_bytes).strip()
            except PDFExtractionError:
                continue
        else:
            with open(file_path, "rb") as f:
                docx_bytes = f.read()
            try:
                text = extract_text_from_docx(docx_bytes).strip()
            except Exception:
                continue

        if not text:
            continue

        doc_id_map[doc_id] = file_path
        forward_index[doc_id] = text

        tokens = preprocess(text)
        if tokens:
            counts = Counter(tokens)
            for token, tf in counts.items():
                postings[token].append({"doc_id": doc_id, "tf": int(tf)})
                df[token] += 1

        doc_id += 1

    for token, plist in postings.items():
        plist.sort(key=lambda x: x["doc_id"])

    N = len(doc_id_map)
    idf: Dict[str, float] = {}
    for token, dfi in df.items():
        idf[token] = math.log((N + 1) / (dfi + 1)) + 1.0

    doc_norm: Dict[int, float] = defaultdict(float)
    for token, plist in postings.items():
        w_idf = idf[token]
        for entry in plist:
            tf = entry["tf"]
            w_tf = 1.0 + math.log(tf)
            doc_norm[entry["doc_id"]] += (w_tf * w_idf) ** 2
    for d in list(doc_norm.keys()):
        doc_norm[d] = math.sqrt(doc_norm[d])

    return {
        "doc_id_map": doc_id_map,
        "forward_index": forward_index,
        "postings": dict(postings),
        "df": dict(df),
        "idf": idf,
        "N": N,
        "doc_norm": dict(doc_norm),
    }
