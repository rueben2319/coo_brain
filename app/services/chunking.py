import re
from typing import List


def chunk_text(
    text: str,
    target_tokens: int = 500,
    overlap_tokens: int = 60,
    approx_chars_per_token: float = 4.0,
) -> List[str]:
    """
    Chunks text into segments of approximately `target_tokens` with `overlap_tokens` overlap.
    Preserves paragraph and sentence boundaries wherever possible.
    """
    if not text or not text.strip():
        return []

    cleaned_text = text.strip()
    target_chars = int(target_tokens * approx_chars_per_token)
    overlap_chars = int(overlap_tokens * approx_chars_per_token)

    if len(cleaned_text) <= target_chars:
        return [cleaned_text]

    # Split into paragraphs first
    paragraphs = re.split(r"(\n\s*\n)", cleaned_text)
    units: List[str] = []

    for p in paragraphs:
        if not p:
            continue
        if len(p) > target_chars:
            # Split large paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", p)
            for s in sentences:
                if len(s) > target_chars:
                    # Hard-split very long sentences
                    for i in range(0, len(s), target_chars - overlap_chars):
                        units.append(s[i : i + target_chars])
                else:
                    units.append(s)
        else:
            units.append(p)

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for unit in units:
        unit_len = len(unit)
        if current_length + unit_len > target_chars and current_chunk:
            combined = "".join(current_chunk).strip()
            if combined:
                chunks.append(combined)

            # Build overlap from recent units
            overlap_units: List[str] = []
            overlap_accum = 0
            for prev in reversed(current_chunk):
                if overlap_accum + len(prev) <= overlap_chars:
                    overlap_units.insert(0, prev)
                    overlap_accum += len(prev)
                else:
                    break

            current_chunk = overlap_units + [unit]
            current_length = sum(len(u) for u in current_chunk)
        else:
            current_chunk.append(unit)
            current_length += unit_len

    if current_chunk:
        combined = "".join(current_chunk).strip()
        if combined and (not chunks or chunks[-1] != combined):
            chunks.append(combined)

    return chunks
