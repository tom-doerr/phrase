"""Python API for generating Diceware-style passphrases."""

from .core import (
    WORDLISTS,
    Generator,
    UnknownLanguageError,
    available_languages,
    generate,
    prefix_wordlist,
    read,
    read_file,
)

__all__ = [
    "Generator",
    "UnknownLanguageError",
    "WORDLISTS",
    "available_languages",
    "generate",
    "prefix_wordlist",
    "read",
    "read_file",
]

__version__ = "0.2.0"
