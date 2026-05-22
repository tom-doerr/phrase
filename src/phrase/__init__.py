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
from .llm_prefix import (
    DEFAULT_LLM_PREFIX_MODEL,
    LlmPrefixResult,
    generate_llm_prefix_phrase,
    normalize_prefix,
    unique_prefixes_from_token_ids,
)
from .mnemonic import DEFAULT_MNEMONIC_MODEL, MnemonicDependencyError, build_prompt, generate_mnemonic

__all__ = [
    "Generator",
    "UnknownLanguageError",
    "WORDLISTS",
    "available_languages",
    "digit_choices",
    "generate",
    "DEFAULT_LLM_PREFIX_MODEL",
    "LlmPrefixResult",
    "generate_llm_prefix_phrase",
    "normalize_prefix",
    "unique_prefixes_from_token_ids",
    "DEFAULT_MNEMONIC_MODEL",
    "MnemonicDependencyError",
    "build_prompt",
    "generate_mnemonic",
    "prefix_entries",
    "prefix_wordlist",
    "read",
    "read_file",
]

__version__ = "0.5.3"
