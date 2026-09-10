from app.services.chunking import chunk_text


def test_chunk_short_text():
    text = "Short text about farm operations."
    chunks = chunk_text(text, target_tokens=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_long_text():
    # Build text of ~1500 words (~2000 tokens)
    paragraphs = [
        f"Paragraph {i}: Operational procedures for section {i}. This describes the irrigation and pest management protocols for field {i}."
        for i in range(50)
    ]
    full_text = "\n\n".join(paragraphs)

    chunks = chunk_text(full_text, target_tokens=100, overlap_tokens=20)
    assert len(chunks) > 1

    # Verify each chunk is reasonable size
    for chunk in chunks:
        assert len(chunk) > 0
        assert len(chunk) < 2500  # bounded
