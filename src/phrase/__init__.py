"""Python API for generating Diceware-style passphrases."""

from .core import (
    WORDLISTS,
    Generator,
    UnknownLanguageError,
    available_languages,
    digit_choices,
    generate,
    prefix_entries,
    prefix_wordlist,
    read,
    read_file,
)

__all__ = [
    "Generator",
    "UnknownLanguageError",
    "WORDLISTS",
    "available_languages",
    "digit_choices",
    "generate",
    "prefix_entries",
    "prefix_wordlist",
    "read",
    "read_file",
]

__version__ = "0.3.1"
