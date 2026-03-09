"""
Code Unescape Utility

Extracts code from markdown code blocks returned by AI models.
Also provides literal escape-sequence replacement for Bedrock output.
"""

import re
from typing import Optional


def unescape_code_output(text: str) -> str:
    """Replace literal escaped sequences with actual characters.

    Handles the two-character sequences (backslash followed by n/t/r),
    NOT actual escape characters. This fixes Bedrock model responses
    that return literal ``\\n`` instead of real newlines.

    Args:
        text: The raw text potentially containing literal escape sequences.

    Returns:
        Text with literal ``\\n``, ``\\t``, and ``\\r`` replaced by
        actual newline, tab, and carriage-return characters.
    """
    if not text:
        return text

    result = text.replace("\\n", "\n")
    result = result.replace("\\t", "\t")
    result = result.replace("\\r", "\r")
    return result


def extract_code_from_markdown(text: str) -> str:
    """
    Extract code from markdown code blocks.
    
    Handles formats like:
    - ```sql\nCODE\n```
    - ```\nCODE\n```
    - Plain text without code blocks
    
    Args:
        text: Text potentially containing markdown code blocks
        
    Returns:
        Extracted code or original text if no code blocks found
    """
    if not text:
        return text
    
    # Pattern to match markdown code blocks with optional language specifier
    # Matches: ```sql\nCODE\n``` or ```\nCODE\n```
    pattern = r'```(?:\w+)?\s*\n(.*?)\n```'
    
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        # Return first code block (most common case)
        return matches[0].strip()
    
    # No code blocks found, return original text
    return text.strip()


def extract_all_code_blocks(text: str) -> list[str]:
    """
    Extract all code blocks from markdown.
    
    Args:
        text: Text containing markdown code blocks
        
    Returns:
        List of extracted code blocks
    """
    if not text:
        return []
    
    pattern = r'```(?:\w+)?\s*\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    return [match.strip() for match in matches]


def has_code_blocks(text: str) -> bool:
    """
    Check if text contains markdown code blocks.
    
    Args:
        text: Text to check
        
    Returns:
        True if code blocks found
    """
    if not text:
        return False
    
    pattern = r'```(?:\w+)?\s*\n.*?\n```'
    return bool(re.search(pattern, text, re.DOTALL))
