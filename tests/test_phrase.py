from __future__ import annotations

import re
from io import StringIO

import pytest

from phrase import (
    WORDLISTS,
    Generator,
    UnknownLanguageError,
    available_languages,
    generate,
    read,
    read_file,
)
from phrase.cli import main
from phrase.core import random_int, random_number


def test_wordlists_are_available() -> None:
    assert available_languages() == ["de", "en", "fr", "nl"]
    assert set(WORDLISTS) == {"de", "en", "fr", "nl"}
    assert "abacus" in WORDLISTS["en"]
    assert all(len(wordlist) > 7_000 for wordlist in WORDLISTS.values())


def test_read_parses_diceware_words() -> None:
    source = StringIO(
        "\n"
        "#11111\tignored\n"
        "11111\tgopher\n"
        "11112\tgopher\n"
        "11113\talpha\n"
        "99999\tignored\n"
    )

    assert read(source) == ["alpha", "gopher"]


def test_read_file(tmp_path) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    assert read_file(wordlist) == ["gopher"]


def test_generator_defaults_to_empty_phrase() -> None:
    assert Generator().phrase() == ""


def test_generator_uses_custom_wordlist() -> None:
    generator = Generator(wordlist=["gopher"], words=2, separator=" ")

    assert generator.phrase() == "gopher gopher"


def test_generator_capitalizes_words() -> None:
    generator = Generator(wordlist=["gopher"], words=1, capitalize=True)

    assert generator.phrase() == "Gopher"


def test_generator_adds_digits() -> None:
    one_digit = Generator(digits=1).phrase()
    multiple_digits = Generator(digits=10).phrase()

    assert re.fullmatch(r"[0-9]", one_digit)
    assert re.fullmatch(r"[1-9][0-9]{9}", multiple_digits)


def test_generator_loads_language() -> None:
    generated = Generator(language="en", words=1).phrase()

    assert generated in WORDLISTS["en"]


def test_generator_rejects_unknown_language() -> None:
    with pytest.raises(UnknownLanguageError, match="no such language: xx"):
        Generator(language="xx", words=1).phrase()


def test_generate_uses_cli_defaults() -> None:
    generated = generate(wordlist=["gopher"])

    assert generated == "gopher gopher gopher gopher"


def test_random_int_validates_max_value() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        random_int(0)


def test_random_number_bounds() -> None:
    assert 0 <= random_number(1) <= 9
    assert 10 <= random_number(2) <= 99
    assert 100 <= random_number(3) <= 999


def test_cli_generates_passphrases(capsys) -> None:
    assert main(["-w", "1", "-l", "en", "-p", "2"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert all(line in WORDLISTS["en"] for line in lines)


def test_cli_reads_custom_wordlist(tmp_path, capsys) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    assert main(["-w", "2", "-f", str(wordlist)]) == 0

    assert capsys.readouterr().out == "gopher gopher\n"
