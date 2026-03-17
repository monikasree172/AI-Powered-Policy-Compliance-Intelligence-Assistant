"""
Semantic document chunker for policy PDFs.
Uses hierarchical strategy: NIST function → subcategory → fixed-size fallback.
"""

import re
from dataclasses import dataclass
from typing import Optional

NIST_FUNCTIONS = {"GOVERN": "GV", "IDENTIFY": "ID", "PROTECT": "PR", "DETECT": "DE", "RESPOND": "RS", "RECOVER": "RC"}
SUBCATEGORY_PATTERN = re.compile(r"\b(GV|ID|PR|DE|RS|RC)\.[A-Z]{2}-\d{2}\b")
FUNCTION_HEADER_PATTERN = re.compile(r"(?m)^(GOVERN|IDENTIFY|PROTECT|DETECT|RESPOND|RECOVER)\s*[\r\n]")


@dataclass
class PolicyChunk:
    text: str
    source: str
    framework: str
    nist_function: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    chunk_id: str
    page_number: Optional[int] = None


def chunk_policy_document(text: str, source: str = "NIST CSF 2.0", framework: str = "NIST",
                           chunk_size: int = 512, chunk_overlap: int = 128) -> list:
    chunks = []
    chunk_index = 0
    sections = _split_by_nist_functions(text)

    for function_name, section_text in sections:
        subcategory_chunks = _split_by_subcategory(section_text, function_name)
        for subcat_id, subcat_text in subcategory_chunks:
            sub_texts = _fixed_size_split(subcat_text, chunk_size, chunk_overlap)
            for sub_text in sub_texts:
                if not sub_text.strip():
                    continue
                category = _extract_category(subcat_id)
                chunk = PolicyChunk(
                    text=sub_text.strip(), source=source, framework=framework,
                    nist_function=function_name, category=category, subcategory=subcat_id,
                    chunk_id=f"{source}_{function_name}_{chunk_index}",
                )
                chunks.append(chunk)
                chunk_index += 1

    if not chunks:
        for i, text_piece in enumerate(_fixed_size_split(text, chunk_size, chunk_overlap)):
            if text_piece.strip():
                chunks.append(PolicyChunk(
                    text=text_piece.strip(), source=source, framework=framework,
                    nist_function=None, category=None, subcategory=None,
                    chunk_id=f"{source}_fallback_{i}",
                ))
    return chunks


def _split_by_nist_functions(text: str) -> list:
    matches = list(FUNCTION_HEADER_PATTERN.finditer(text))
    if not matches:
        return [("GENERAL", text)]
    results = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        results.append((match.group(1), text[start:end]))
    return results if results else [("GENERAL", text)]


def _split_by_subcategory(text: str, function_name: str) -> list:
    results = []
    lines = text.split("\n")
    current_subcat = f"{NIST_FUNCTIONS.get(function_name, 'GN')}.GEN-00"
    current_lines = []
    for line in lines:
        match = SUBCATEGORY_PATTERN.search(line)
        if match:
            if current_lines:
                results.append((current_subcat, "\n".join(current_lines)))
            current_subcat = match.group(0)
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        results.append((current_subcat, "\n".join(current_lines)))
    return results if results else [(f"{NIST_FUNCTIONS.get(function_name, 'GN')}.GEN-00", text)]


def _fixed_size_split(text: str, chunk_size: int, overlap: int) -> list:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        chunk = " ".join(words[start:start + chunk_size])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _extract_category(subcategory_id: str) -> Optional[str]:
    if not subcategory_id:
        return None
    parts = subcategory_id.split("-")
    return parts[0] if parts else None
