"""ADF to text conversion."""

from __future__ import annotations

from jira_qa_crew.jira.adf import extract_text


def test_plain_string_passes_through() -> None:
    assert extract_text("hello") == "hello"


def test_none_becomes_empty_string() -> None:
    assert extract_text(None) == ""


def test_nested_paragraphs_are_all_collected() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "First line."}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Second line."}]},
        ],
    }
    result = extract_text(doc)
    # The naive content[0].content[0].text approach loses the second paragraph.
    assert "First line." in result
    assert "Second line." in result


def test_bullet_lists_become_dashes() -> None:
    doc = {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "One"}]}
                ],
            },
            {
                "type": "listItem",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Two"}]}
                ],
            },
        ],
    }
    result = extract_text(doc)
    assert "- One" in result
    assert "- Two" in result


def test_hard_break_becomes_newline() -> None:
    doc = {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": "a"},
            {"type": "hardBreak"},
            {"type": "text", "text": "b"},
        ],
    }
    assert extract_text(doc) == "a\nb"


def test_mentions_and_emoji_render_readably() -> None:
    doc = {
        "type": "paragraph",
        "content": [
            {"type": "mention", "attrs": {"text": "@jane"}},
            {"type": "text", "text": " done "},
            {"type": "emoji", "attrs": {"shortName": ":tada:"}},
        ],
    }
    result = extract_text(doc)
    assert "@jane" in result
    assert ":tada:" in result


def test_code_block_content_is_preserved() -> None:
    doc = {
        "type": "codeBlock",
        "content": [{"type": "text", "text": "const total = 0;"}],
    }
    assert "const total = 0;" in extract_text(doc)


def test_runaway_blank_lines_are_collapsed() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "A"}]},
            {"type": "paragraph", "content": []},
            {"type": "paragraph", "content": []},
            {"type": "paragraph", "content": [{"type": "text", "text": "B"}]},
        ],
    }
    assert "\n\n\n" not in extract_text(doc)
