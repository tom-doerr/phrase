from __future__ import annotations

import math
import re
from io import StringIO

import pytest

from phrase import (
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


def test_prefix_wordlist_keeps_unique_prefixes() -> None:
    assert prefix_entries(["alpha", "alpine", "bravo"], 2) == [
        ("al", "alpha"),
        ("br", "bravo"),
    ]
    assert prefix_wordlist(["alpha", "alpine", "bravo"], 2) == ["al", "br"]


def test_generator_uses_prefix_length() -> None:
    generator = Generator(wordlist=["gopher"], words=2, separator=" ", prefix_length=3)

    assert generator.phrase() == "gop gop"


def test_generator_reports_full_words_for_prefix_length() -> None:
    generator = Generator(wordlist=["gopher"], words=2, separator=" ", prefix_length=3)

    assert generator.phrase_with_full_words() == ("gop gop", "gopher gopher")


def test_generator_estimates_entropy() -> None:
    assert Generator(wordlist=["alpha", "bravo"], words=3).entropy_bits() == 3
    assert (
        Generator(wordlist=["alpha", "alpine", "bravo"], words=2, prefix_length=2).entropy_bits()
        == 2
    )
    assert Generator(wordlist=["alpha", "bravo"], words=1, digits=1).entropy_bits() == (
        math.log2(2) + math.log2(10) + math.log2(2)
    )


def test_generator_rejects_invalid_prefix_length() -> None:
    with pytest.raises(ValueError, match="prefix_length must be greater than zero"):
        Generator(wordlist=["gopher"], words=1, prefix_length=0).phrase()


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


def test_digit_choices() -> None:
    assert digit_choices(1) == 10
    assert digit_choices(2) == 90


def test_cli_generates_passphrases(capsys) -> None:
    assert main(["-w", "1", "-l", "en", "-p", "2"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4
    assert lines[0] in WORDLISTS["en"]
    assert lines[1] == "entropy: 12.92 bits"
    assert lines[2] in WORDLISTS["en"]
    assert lines[3] == "entropy: 12.92 bits"


def test_cli_reads_custom_wordlist(tmp_path, capsys) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    assert main(["-w", "2", "-f", str(wordlist)]) == 0

    assert capsys.readouterr().out == "gopher gopher\nentropy: 0.00 bits\n"


def test_cli_uses_prefix_length(tmp_path, capsys) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    assert main(["-w", "2", "-f", str(wordlist), "--prefix-length", "3"]) == 0

    assert capsys.readouterr().out == "gopher gopher\ngop gop\nentropy: 0.00 bits\n"
