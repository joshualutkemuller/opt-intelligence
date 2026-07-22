"""Tests for _strip_repeated_table_headers."""

from collateral_schedule.llm_parser import _strip_repeated_table_headers


def _table_block(page: int, col_hdr: str, *data_rows: str) -> str:
    lines = [f"[page {page} table 1]", col_hdr] + list(data_rows)
    return "\n".join(lines)


class TestStripRepeatedTableHeaders:
    def test_repeated_header_stripped_from_second_block(self):
        col = "| A | B | C |"
        t1 = _table_block(1, col, "| r1a | r1b | r1c |")
        t2 = _table_block(2, col, "| r2a | r2b | r2c |")
        result = _strip_repeated_table_headers(t1 + "\n\n" + t2)
        blocks = result.split("\n\n")
        # First block keeps its header.
        assert col in blocks[0]
        # Second block should NOT contain the col header line again.
        second_lines = [l for l in blocks[1].splitlines() if col.strip() in l]
        assert not second_lines, f"Duplicate header still present: {blocks[1]}"

    def test_unique_headers_not_stripped(self):
        col1 = "| A | B | C |"
        col2 = "| X | Y | Z |"
        t1 = _table_block(1, col1, "| r1a |")
        t2 = _table_block(2, col2, "| r2a |")
        result = _strip_repeated_table_headers(t1 + "\n\n" + t2)
        assert col1 in result
        assert col2 in result

    def test_three_consecutive_repeats(self):
        col = "| Asset | Haircut |"
        blocks = [_table_block(i, col, f"| row{i} |") for i in range(1, 4)]
        text = "\n\n".join(blocks)
        result = _strip_repeated_table_headers(text)
        result_blocks = result.split("\n\n")
        assert col in result_blocks[0]
        for rb in result_blocks[1:]:
            assert col not in rb.split("\n")[1:], f"Header repeated in {rb}"

    def test_non_table_paragraph_resets_tracking(self):
        col = "| A | B |"
        t1 = _table_block(1, col, "| r1 |")
        prose = "Some prose paragraph."
        t2 = _table_block(2, col, "| r2 |")
        text = "\n\n".join([t1, prose, t2])
        result = _strip_repeated_table_headers(text)
        result_blocks = result.split("\n\n")
        # After a prose paragraph, the header is "new" and should be kept.
        assert col in result_blocks[2]

    def test_non_table_text_unchanged(self):
        prose = "Hello world.\nThis is a paragraph."
        result = _strip_repeated_table_headers(prose)
        assert result == prose
