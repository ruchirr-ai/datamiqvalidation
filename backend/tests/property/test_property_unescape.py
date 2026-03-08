# Feature: code-conversion-enhancements, Property 9: Unescape code output
"""
Property test: Unescape code output.

For any string containing literal escaped sequences (\\n, \\t, \\r),
applying the unescape function should replace all such sequences with
their actual character equivalents. Applying the unescape function to
a string with no escaped sequences should return the string unchanged.

**Validates: Requirements 10.1, 10.2, 10.4**
"""

import pytest
from hypothesis import given, settings, strategies as st

from utils.unescape import unescape_code_output


# Strategy: generate strings that may contain literal escape sequences
ESCAPE_PAIRS = [("\\n", "\n"), ("\\t", "\t"), ("\\r", "\r")]


@st.composite
def string_with_escapes(draw):
    """Generate a string that contains random literal escape sequences
    interspersed with normal text segments."""
    num_segments = draw(st.integers(min_value=1, max_value=10))
    parts = []
    for _ in range(num_segments):
        # Either a normal text segment or a literal escape sequence
        choice = draw(st.integers(min_value=0, max_value=3))
        if choice == 0:
            parts.append("\\n")
        elif choice == 1:
            parts.append("\\t")
        elif choice == 2:
            parts.append("\\r")
        else:
            # Normal text (avoid generating accidental escape sequences)
            segment = draw(st.text(
                alphabet=st.characters(
                    blacklist_characters="\\",
                ),
                min_size=0,
                max_size=20,
            ))
            parts.append(segment)
    return "".join(parts)


@settings(max_examples=20)
@given(text=string_with_escapes())
def test_unescape_replaces_all_literal_escapes(text):
    """Property 9: All literal escape sequences are replaced with actual characters.

    **Validates: Requirements 10.1, 10.2, 10.4**
    """
    result = unescape_code_output(text)

    # After unescaping, no literal \\n, \\t, or \\r should remain
    assert "\\n" not in result
    assert "\\t" not in result
    assert "\\r" not in result

    # Count replacements: each literal escape in input should become
    # the corresponding actual character in output
    expected = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    assert result == expected


@settings(max_examples=20)
@given(text=st.text(
    alphabet=st.characters(blacklist_characters="\\"),
    min_size=0,
    max_size=200,
))
def test_unescape_no_escapes_returns_unchanged(text):
    """Property 9: Strings with no escape sequences are returned unchanged.

    **Validates: Requirements 10.1, 10.2, 10.4**
    """
    result = unescape_code_output(text)
    assert result == text


def test_unescape_empty_string():
    """Edge case: empty string returns empty string."""
    assert unescape_code_output("") == ""


def test_unescape_mixed_escapes():
    """Edge case: string with all three escape types."""
    input_text = "SELECT 1\\nFROM t\\tWHERE x\\r"
    expected = "SELECT 1\nFROM t\tWHERE x\r"
    assert unescape_code_output(input_text) == expected
