from backuper.utils.gitignore_lines import (
    gitignore_pattern_lines,
    gitignore_pattern_lines_from_text,
    iter_gitignore_pattern_lines,
)


def test_iter_gitignore_pattern_lines_skips_blank_and_hash_comments() -> None:
    lines = ["", "  ", "\t", "# comment", "keep.txt", "#also-a-comment"]
    assert list(iter_gitignore_pattern_lines(lines)) == ["keep.txt"]


def test_iter_gitignore_pattern_lines_preserves_leading_space_before_hash() -> None:
    assert list(iter_gitignore_pattern_lines([" #not-a-comment"])) == [
        " #not-a-comment"
    ]


def test_gitignore_pattern_lines_from_text_splits_crlf_and_strips_bom() -> None:
    text = "\ufeff# ignored\r\n\r\nignored.txt\r\n"
    assert gitignore_pattern_lines_from_text(text) == ("ignored.txt",)


def test_gitignore_pattern_lines_from_text_bom_strip_matches_utf8_sig_semantics() -> (
    None
):
    # First logical line is a comment once BOM is stripped (same as utf-8-sig decode).
    text = "\ufeff# file header comment\nreal.txt\n"
    assert gitignore_pattern_lines_from_text(text) == ("real.txt",)


def test_gitignore_pattern_lines_tuple_wrapper_matches_iter() -> None:
    raw = ["a", "", " #leading-space-hash.txt"]
    assert gitignore_pattern_lines(raw) == tuple(iter_gitignore_pattern_lines(raw))
