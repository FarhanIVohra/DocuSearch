import math
from typing import Dict, List, Tuple
from .preprocess import preprocess


def _and_intersect(posting_lists: List[List[Dict[str, int]]]) -> List[int]:
    """Return sorted intersection of doc_ids present in all posting lists."""
    if not posting_lists:
        return []
    posting_lists = sorted(posting_lists, key=len)
    base = posting_lists[0]
    docs = [e["doc_id"] for e in base]
    common = set(docs)
    for plist in posting_lists[1:]:
        dset = {e["doc_id"] for e in plist}
        common &= dset
        if not common:
            return []
    return sorted(common)


def search(query: str, index: Dict) -> List[Tuple[int, float]]:
    """
    AND-based retrieval with TF-IDF scoring and cosine normalization.
    Returns list of (doc_id, score) sorted by score desc.
    """
    tokens = preprocess(query)
    if not tokens:
        return []

    postings = index.get("postings", {})
    idf = index.get("idf", {})
    doc_norm = index.get("doc_norm", {})

    lists = []
    for t in tokens:
        plist = postings.get(t)
        if not plist:
            return []
        lists.append(plist)

    candidate_docs = _and_intersect(lists)
    if not candidate_docs:
        return []

    tf_map: Dict[str, Dict[int, int]] = {}
    for t in set(tokens):
        d = {}
        for e in postings[t]:
            d[e["doc_id"]] = e["tf"]
        tf_map[t] = d

    scores: Dict[int, float] = {}
    for d in candidate_docs:
        s = 0.0
        for t in set(tokens):
            tf = tf_map[t].get(d)
            if not tf:
                s = 0.0
                break
            w_tf = 1.0 + math.log(tf)
            w_idf = idf.get(t, 0.0)
            s += w_tf * w_idf
        norm = doc_norm.get(d, 1.0)
        if norm > 0:
            s = s / norm
        scores[d] = s

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return ranked
