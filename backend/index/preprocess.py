import re
from typing import List, Set

STOPWORDS: Set[str] = {
    "a","an","the","and","or","but","if","then","else","for","to","of","in","on","at","by","with","is","are","was","were","be","been","being","it","its","as","that","this","these","those","not","no","do","does","did","how","why","what","which","who","whom","from"
}

_TOKEN_RE = re.compile(r"[^a-z0-9]+")

def preprocess(text: str, stopwords: Set[str] = STOPWORDS) -> List[str]:
    """Lowercase, remove non-alphanum, tokenize, remove stopwords."""
    if not text:
        return []
    text = text.lower()
    text = _TOKEN_RE.sub(" ", text)
    tokens = [t for t in text.split() if t and t not in stopwords]
    return tokens
