from __future__ import annotations

import math
import re
import secrets
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from random import SystemRandom
from typing import Iterable, Sequence, TypeVar

_VALID_LINE = re.compile(r"^[1-6]{5}\t(.+)$")
_LANGUAGES = ("de", "en", "fr", "nl")
_SHUFFLER = SystemRandom()
_T = TypeVar("_T")


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


def prefix_entries(wordlist: Sequence[str], length: int) -> list[tuple[str, str]]:
    """Return sorted unique prefixes paired with representative full words."""
    if length <= 0:
        raise ValueError("prefix_length must be greater than zero")

    entries: dict[str, str] = {}
    for word in sorted(wordlist):
        entries.setdefault(word[:length], word)
    return sorted(entries.items())


def prefix_wordlist(wordlist: Sequence[str], length: int) -> list[str]:
    """Return sorted unique prefixes for a truncation length."""
    return [prefix for prefix, _ in prefix_entries(wordlist, length)]


def random_items(items: Sequence[_T], count: int) -> list[_T]:
    """Return count secure random items from a sequence."""
    if not items:
        return []
    return [items[random_int(len(items))] for _ in range(count)]


def random_words(wordlist: Sequence[str], count: int) -> list[str]:
    """Return count secure random words from wordlist."""
    return random_items(wordlist, count)


def digit_choices(digits: int) -> int:
    """Return the count of possible numbers for a digit length."""
    if digits <= 0:
        raise ValueError("digits must be greater than zero")
    return 10 if digits == 1 else 9 * 10 ** (digits - 1)


def random_number(digits: int) -> int:
    """Return a secure random number with the requested number of digits."""
    minimum = 0 if digits == 1 else 10 ** (digits - 1)
    return random_int(digit_choices(digits)) + minimum


@dataclass(slots=True)
class Generator:
    """Generate random passphrases using built-in or custom wordlists."""

    wordlist: Sequence[str] | None = None
    language: str | None = None
    words: int = 0
    separator: str = ""
    capitalize: bool = False
    digits: int = 0
    prefix_length: int | None = None

    def _resolve_wordlist(self) -> Sequence[str] | None:
        wordlist = self.wordlist
        if self.language and not wordlist:
            try:
                wordlist = WORDLISTS[self.language]
            except KeyError as exc:
                raise UnknownLanguageError(f"no such language: {self.language}") from exc
            self.wordlist = wordlist
        return wordlist

    def _selected_tokens(self) -> tuple[list[str], list[str] | None]:
        wordlist = self._resolve_wordlist()
        full_words = None
        if self.prefix_length is not None:
            entries = random_items(prefix_entries(wordlist or [], self.prefix_length), self.words)
            passphrase = [prefix for prefix, _ in entries]
            full_words = [word for _, word in entries]
        else:
            passphrase = random_words(wordlist or [], self.words)

        if self.capitalize:
            passphrase = [word.title() for word in passphrase]
            if full_words is not None:
                full_words = [word.title() for word in full_words]

        if self.digits > 0:
            number = str(random_number(self.digits))
            if full_words is None:
                passphrase.append(number)
                _SHUFFLER.shuffle(passphrase)
            else:
                pairs = list(zip(passphrase, full_words))
                pairs.append((number, number))
                _SHUFFLER.shuffle(pairs)
                passphrase = [prefix for prefix, _ in pairs]
                full_words = [word for _, word in pairs]

        return passphrase, full_words

    def entropy_bits(self) -> float:
        wordlist = self._resolve_wordlist() or []
        word_slots = max(self.words, 0)
        if self.prefix_length is not None:
            choice_count = len(prefix_entries(wordlist, self.prefix_length))
        else:
            choice_count = len(wordlist)

        entropy = 0.0
        if word_slots > 0 and choice_count > 0:
            entropy += word_slots * math.log2(choice_count)

        if self.digits > 0:
            entropy += math.log2(digit_choices(self.digits))
            if word_slots > 0 and choice_count > 0:
                entropy += math.log2(word_slots + 1)

        return entropy

    def phrase(self) -> str:
        passphrase, _ = self._selected_tokens()
        return self.separator.join(passphrase)

    def phrase_with_full_words(self) -> tuple[str, str | None]:
        passphrase, full_words = self._selected_tokens()
        full_phrase = self.separator.join(full_words) if full_words is not None else None
        return self.separator.join(passphrase), full_phrase


def generate(
    *,
    wordlist: Sequence[str] | None = None,
    language: str | None = "en",
    words: int = 4,
    separator: str = " ",
    capitalize: bool = False,
    digits: int = 0,
    prefix_length: int | None = None,
) -> str:
    """Generate a passphrase with the same defaults as the CLI."""
    return Generator(
        wordlist=wordlist,
        language=language,
        words=words,
        separator=separator,
        capitalize=capitalize,
        digits=digits,
        prefix_length=prefix_length,
    ).phrase()
