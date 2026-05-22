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
from phrase.llm_prefix import (
    LlmPrefixResult,
    generate_llm_prefix_phrase,
    normalize_prefix,
    unique_prefixes_from_token_ids,
)
from phrase.mnemonic import DEFAULT_MAX_NEW_TOKENS, build_prompt, ensure_final_mnemonic


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


def test_cli_count_alias_generates_passphrases(tmp_path, capsys) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    assert main(["-w", "1", "-f", str(wordlist), "--count", "2"]) == 0

    assert capsys.readouterr().out == (
        "gopher\n"
        "entropy: 0.00 bits\n"
        "gopher\n"
        "entropy: 0.00 bits\n"
    )


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

def test_build_prompt_keeps_password_and_mnemonic_separate() -> None:
    prompt = build_prompt("rom emm spi", "rommee emmy spicken")

    assert "Password prefixes: rom emm spi" in prompt
    assert "Full source words: rommee emmy spicken" in prompt
    assert "Do not change" in prompt


def test_ensure_final_mnemonic_appends_fallback_after_visible_thinking() -> None:
    assert ensure_final_mnemonic(
        "Thinking Process: still choosing",
        "pec bez puz",
        "pech bezahlen puzzeln",
    ) == "Thinking Process: still choosing Mnemonic sentence: pech bezahlen puzzeln."


def test_ensure_final_mnemonic_keeps_model_final_sentence() -> None:
    assert ensure_final_mnemonic(
        "Thinking Process: done Mnemonic sentence: pech bezahlt puzzelnde Pferde.",
        "pec bez puz",
        "pech bezahlen puzzeln",
    ) == "Thinking Process: done Mnemonic sentence: pech bezahlt puzzelnde Pferde."


def test_cli_generates_local_mnemonic(monkeypatch, tmp_path, capsys) -> None:
    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text("11111\tgopher\n", encoding="utf-8")

    def fake_mnemonic(prefix_phrase, full_phrase=None, **kwargs):
        assert prefix_phrase == "gop"
        assert full_phrase == "gopher"
        assert kwargs["model_id"] == "test/model"
        assert kwargs["max_new_tokens"] == DEFAULT_MAX_NEW_TOKENS
        return "Gopher remembers gop."

    monkeypatch.setattr("phrase.cli.generate_mnemonic", fake_mnemonic)

    assert (
        main(
            [
                "-w",
                "1",
                "-f",
                str(wordlist),
                "--prefix-length",
                "3",
                "--mnemonic",
                "--mnemonic-model",
                "test/model",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out == (
        "gopher\n"
        "gop\n"
        "mnemonic: Gopher remembers gop.\n"
        "entropy: 0.00 bits\n"
    )


class FakePrefixTokenizer:
    all_special_ids = [99]
    eos_token_id = 99
    token_text = {
        0: " marble",
        1: " market",
        2: " raven",
        3: " lunar",
        4: " 4bad",
        5: " Überfall",
        99: "<eos>",
    }

    def decode(self, ids, **kwargs):
        return self.token_text[ids[0]]


def test_normalize_prefix_folds_and_rejects_ambiguous_tokens() -> None:
    assert normalize_prefix(" Station", 3) == "sta"
    assert normalize_prefix("ĠRaven", 3) == "rav"
    assert normalize_prefix(" Überfall", 3) == "ueb"
    assert normalize_prefix(" st", 3) is None
    assert normalize_prefix(" 123abc", 3) is None


def test_unique_prefixes_deduplicates_password_prefixes() -> None:
    tokenizer = FakePrefixTokenizer()

    assert unique_prefixes_from_token_ids(
        tokenizer,
        [0, 1, 2, 99, 3, 4, 5],
        prefix_length=3,
        limit=4,
    ) == ["mar", "rav", "lun", "ueb"]


def test_generate_llm_prefix_phrase_uses_uniform_prefix_choices(monkeypatch) -> None:
    tokenizer = FakePrefixTokenizer()
    choices = [1, 0]

    monkeypatch.setattr("phrase.llm_prefix._load_model", lambda *args: (tokenizer, object(), object()))
    monkeypatch.setattr("phrase.llm_prefix._ranked_next_token_ids", lambda *args: [0, 1, 2, 3])
    monkeypatch.setattr(
        "phrase.llm_prefix._complete_word",
        lambda tokenizer, model, torch, context, prefix, **kwargs: f"{prefix}word",
    )
    monkeypatch.setattr("phrase.llm_prefix.random_int", lambda limit: choices.pop(0))

    result = generate_llm_prefix_phrase(
        model_id="test/base",
        model_revision="abc123",
        words=2,
        prefix_length=3,
        choices_per_step=2,
        scan_tokens=4,
        separator="-",
    )

    assert result.password == "rav-mar"
    assert result.mnemonic == "ravword marword"
    assert result.candidate_counts == [2, 2]
    assert result.entropy_bits == 2.0
    assert result.entropy_formula == "2 x log2(2)"
    assert result.model_id == "test/base"
    assert result.model_revision == "abc123"


def test_generate_llm_prefix_phrase_fails_on_shortfall(monkeypatch) -> None:
    tokenizer = FakePrefixTokenizer()

    monkeypatch.setattr("phrase.llm_prefix._load_model", lambda *args: (tokenizer, object(), object()))
    monkeypatch.setattr("phrase.llm_prefix._ranked_next_token_ids", lambda *args: [0, 1])

    with pytest.raises(ValueError, match="only 1 unique prefixes found at position 1"):
        generate_llm_prefix_phrase(
            words=1,
            prefix_length=3,
            choices_per_step=2,
            scan_tokens=2,
        )


def test_cli_llm_prefix_prints_audit_trail(monkeypatch, capsys) -> None:
    def fake_generate(**kwargs):
        assert kwargs["model_id"] == "test/base"
        assert kwargs["model_revision"] == "rev"
        assert kwargs["words"] == 2
        assert kwargs["prefix_length"] == 3
        assert kwargs["choices_per_step"] == 1024
        return LlmPrefixResult(
            password="mar-rav",
            mnemonic="marble raven",
            prefixes=["mar", "rav"],
            words=["marble", "raven"],
            candidate_counts=[1024, 1024],
            entropy_bits=20.0,
            model_id="test/base",
            model_revision="rev",
            prefix_length=3,
            choices_per_step=1024,
        )

    monkeypatch.setattr("phrase.cli.generate_llm_prefix_phrase", fake_generate)

    assert main(["llm-prefix", "--words", "2", "--model", "test/base", "--model-revision", "rev"]) == 0

    assert capsys.readouterr().out == (
        "password: mar-rav\n"
        "mnemonic: marble raven\n"
        "entropy: 20.00 bits = 2 x log2(1024)\n"
        "model: test/base@rev\n"
        "prefix length: 3\n"
        "candidate counts: 1024 1024\n"
    )


def test_cli_llm_prefix_count_alias_generates_multiple(monkeypatch, capsys) -> None:
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        index = len(calls)
        return LlmPrefixResult(
            password=f"mar-rav-{index}",
            mnemonic=f"marble raven {index}",
            prefixes=["mar", "rav"],
            words=["marble", "raven"],
            candidate_counts=[1024, 1024],
            entropy_bits=20.0,
            model_id="test/base",
            model_revision=None,
            prefix_length=3,
            choices_per_step=1024,
        )

    monkeypatch.setattr("phrase.cli.generate_llm_prefix_phrase", fake_generate)

    assert main(["llm-prefix", "--words", "2", "--model", "test/base", "--count", "2"]) == 0

    assert len(calls) == 2
    assert capsys.readouterr().out == (
        "password: mar-rav-1\n"
        "mnemonic: marble raven 1\n"
        "entropy: 20.00 bits = 2 x log2(1024)\n"
        "model: test/base\n"
        "prefix length: 3\n"
        "candidate counts: 1024 1024\n"
        "\n"
        "password: mar-rav-2\n"
        "mnemonic: marble raven 2\n"
        "entropy: 20.00 bits = 2 x log2(1024)\n"
        "model: test/base\n"
        "prefix length: 3\n"
        "candidate counts: 1024 1024\n"
    )
