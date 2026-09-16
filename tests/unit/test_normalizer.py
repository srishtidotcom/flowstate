from backend.preprocessing.normalizer import chunk_whatsapp


def test_whatsapp_chunks_preserve_deterministic_source_references(tmp_path):
    source = tmp_path / "chat.txt"
    source.write_text(
        "ignored header\n"
        "[12/03/2024, 09:14:32] Alice: Finish the slides\n",
        encoding="utf-8",
    )

    chunks = chunk_whatsapp(str(source))

    assert len(chunks) == 1
    assert chunks[0].source_ref == "chat.txt:2"
    assert chunks[0].text == "Finish the slides"
