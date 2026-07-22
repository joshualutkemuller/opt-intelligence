"""Tests for the table-aware _split_chunks function."""

import pytest

from collateral_schedule.llm_parser import _split_chunks


def _make_table(page: int, table: int, n_rows: int, row_width: int = 40) -> str:
    header = f"[page {page} table {table}]"
    col_header = "| col_a | col_b | col_c |"
    rows = [f"| row{i:04d} | {i * 10:8d} | {'X' * (row_width - 20):s} |" for i in range(n_rows)]
    return "\n".join([header, col_header, *rows])


class TestSplitChunksBasic:
    def test_short_text_returns_single_chunk(self):
        text = "hello world\n\nsome more text"
        chunks = _split_chunks(text, max_chars=1000, max_chunks=5)
        assert len(chunks) == 1
        assert "hello world" in chunks[0]

    def test_empty_text_returns_empty(self):
        assert _split_chunks("", 1000, 5) == []

    def test_splits_at_paragraph_boundary(self):
        # Build two paragraphs that together exceed max_chars but each is under.
        para_a = "A" * 500
        para_b = "B" * 500
        text = para_a + "\n\n" + para_b
        chunks = _split_chunks(text, max_chars=600, max_chunks=5)
        assert len(chunks) == 2
        assert chunks[0].startswith("A")
        assert chunks[1].startswith("B")

    def test_max_chunks_respected(self):
        paragraphs = "\n\n".join(["X" * 100] * 20)
        chunks = _split_chunks(paragraphs, max_chars=150, max_chunks=3)
        assert len(chunks) <= 3


class TestTableBlockHandling:
    def test_small_table_stays_intact(self):
        table = _make_table(1, 1, n_rows=3)
        text = table
        chunks = _split_chunks(text, max_chars=5000, max_chunks=5)
        assert len(chunks) == 1
        assert "[page 1 table 1]" in chunks[0]

    def test_large_table_splits_on_rows_not_mid_char(self):
        # Build a table whose total size exceeds max_chars.
        table = _make_table(1, 1, n_rows=50, row_width=60)
        assert len(table) > 2000
        chunks = _split_chunks(table, max_chars=2000, max_chunks=6)
        # Every chunk should start with the table header.
        for chunk in chunks:
            assert "[page 1 table 1]" in chunk
        # No chunk should end mid-pipe (i.e. cut inside a '|' row).
        for chunk in chunks:
            lines = chunk.splitlines()
            for line in lines:
                if line.startswith("| row"):
                    assert line.endswith("|"), f"Row was cut: {line!r}"

    def test_column_header_repeated_in_each_sub_chunk(self):
        table = _make_table(1, 1, n_rows=50, row_width=60)
        chunks = _split_chunks(table, max_chars=2000, max_chunks=6)
        assert len(chunks) > 1  # ensure we actually split
        for chunk in chunks:
            assert "| col_a | col_b | col_c |" in chunk

    def test_section_tag_carried_to_next_chunk(self):
        table_text = _make_table(2, 1, n_rows=3)
        # Follow the table with a prose paragraph that will spill to a new chunk.
        prose = "P" * 800
        text = table_text + "\n\n" + prose
        # max_chars just over the table but under table+prose combined.
        chunks = _split_chunks(text, max_chars=len(table_text) + 10, max_chunks=5)
        # The prose chunk should carry the section context.
        prose_chunks = [c for c in chunks if "PPP" in c]
        assert prose_chunks, "Prose paragraph missing from chunks"
        for pc in prose_chunks:
            assert "[page 2 table 1]" in pc

    def test_non_table_paragraph_hard_split_carries_context(self):
        # A non-table paragraph that is itself > max_chars should be split with
        # the last-seen section tag prepended.
        table_text = _make_table(3, 1, n_rows=2)
        big_prose = "Z" * 3000
        text = table_text + "\n\n" + big_prose
        chunks = _split_chunks(text, max_chars=2000, max_chunks=6)
        z_chunks = [c for c in chunks if "ZZZ" in c]
        assert z_chunks
        for zc in z_chunks:
            assert "[page 3 table 1]" in zc
