from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from random import SystemRandom
from typing import Iterable, Sequence

_VALID_LINE = re.compile(r"^[1-6]{5}\t(.+)$")
_LANGUAGES = ("de", "en", "fr", "nl")
_SHUFFLER = SystemRandom()


class UnknownLanguageError(ValueError):
    """Raised when a built-in wordlist language is not available."""


def read(reader: Iterable[str]) -> list[str]:
    """Read a Diceware wordlist stream into a sorted list of unique words."""
    words: set[str] = set()
    for line in reader:
        match = _VALID_LINE.match(line.rstrip("\r\n"))
        if match:
            words.add(match.group(1))
    return sorted(words)


def read_file(filename: str | Path) -> list[str]:
    """Read a Diceware wordlist file into a sorted list of unique words."""
    with Path(filename).open(encoding="utf-8") as wordlist_file:
        return read(wordlist_file)


def _load_wordlist(language: str) -> list[str]:
    if language not in _LANGUAGES:
        raise UnknownLanguageError(f"no such language: {language}")

    wordlist = resources.files("phrase").joinpath("wordlists", f"{language}.txt")
    with wordlist.open(encoding="utf-8") as wordlist_file:
        return read(wordlist_file)


WORDLISTS = {language: _load_wordlist(language) for language in _LANGUAGES}


def available_languages() -> list[str]:
    """Return the available built-in wordlist language codes."""
    return sorted(WORDLISTS)


def random_int(max_value: int) -> int:
    """Return a secure random integer in the range [0, max_value)."""
    if max_value <= 0:
        raise ValueError("random_int: max_value must be greater than zero")
    return secrets.randbelow(max_value)


def random_words(wordlist: Sequence[str], count: int) -> list[str]:
    """Return count secure random words from wordlist."""
    if not wordlist:
        return []
    return [wordlist[random_int(len(wordlist))] for _ in range(count)]


def random_number(digits: int) -> int:
    """Return a secure random number with the requested number of digits."""
    if digits <= 0:
        raise ValueError("random_number: digits must be greater than zero")

    minimum = 0 if digits == 1 else 10 ** (digits - 1)
    width = 10**digits - minimum
    return random_int(width) + minimum


@dataclass(slots=True)
class Generator:
    """Generate random passphrases using built-in or custom wordlists."""

    wordlist: Sequence[str] | None = None
    language: str | None = None
    words: int = 0
    separator: str = ""
    capitalize: bool = False
    digits: int = 0

    def phrase(self) -> str:
        wordlist = self.wordlist
        if self.language and not wordlist:
            try:
                wordlist = WORDLISTS[self.language]
            except KeyError as exc:
                raise UnknownLanguageError(f"no such language: {self.language}") from exc
            self.wordlist = wordlist

        passphrase = random_words(wordlist or [], self.words)
        if self.capitalize:
            passphrase = [word.title() for word in passphrase]

        if self.digits > 0:
            passphrase.append(str(random_number(self.digits)))
            _SHUFFLER.shuffle(passphrase)

        return self.separator.join(passphrase)


def generate(
    *,
    wordlist: Sequence[str] | None = None,
    language: str | None = "en",
    words: int = 4,
    separator: str = " ",
    capitalize: bool = False,
    digits: int = 0,
) -> str:
    """Generate a passphrase with the same defaults as the CLI."""
    return Generator(
        wordlist=wordlist,
        language=language,
        words=words,
        separator=separator,
        capitalize=capitalize,
        digits=digits,
    ).phrase()
