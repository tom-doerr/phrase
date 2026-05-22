from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import Generator, available_languages, read_file
from .llm_prefix import (
    DEFAULT_CHOICES_PER_STEP,
    DEFAULT_LLM_PREFIX_MODEL,
    DEFAULT_PREFIX_LENGTH,
    DEFAULT_SCAN_TOKENS,
    DEFAULT_CONTEXT as DEFAULT_LLM_PREFIX_CONTEXT,
    DEFAULT_MAX_WORD_TOKENS,
    DEFAULT_TEMPERATURE as DEFAULT_LLM_PREFIX_TEMPERATURE,
    generate_llm_prefix_phrase,
)
from .mnemonic import (
    DEFAULT_MAX_NEW_TOKENS as DEFAULT_MNEMONIC_MAX_NEW_TOKENS,
    DEFAULT_MNEMONIC_MODEL,
    DEFAULT_TEMPERATURE as DEFAULT_MNEMONIC_TEMPERATURE,
    MnemonicDependencyError,
    generate_mnemonic,
)


def _installed_version() -> str:
    try:
        return version("diceware-phrase")
    except PackageNotFoundError:
        return __version__


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phrase",
        description="Generate easy-to-remember passwords from random words.",
        epilog="Subcommands: llm-prefix (local LM-ranked prefix generator)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-w", "--words", type=int, default=4, help="Words per passphrase")
    parser.add_argument(
        "-s",
        "--separator",
        default=" ",
        help="Separator between words",
    )
    parser.add_argument(
        "-C",
        "--capitalize",
        action="store_true",
        help="Capitalize all words",
    )
    parser.add_argument("-d", "--digits", type=int, default=0, help="Digits per passphrase")
    parser.add_argument(
        "--prefix-length",
        type=int,
        help="Use unique first-N-character prefixes as generated words",
    )
    parser.add_argument(
        "--mnemonic",
        action="store_true",
        help="Generate a local-LLM mnemonic after the password is generated",
    )
    parser.add_argument(
        "--mnemonic-model",
        default=DEFAULT_MNEMONIC_MODEL,
        help="Hugging Face model id or local model path for --mnemonic",
    )
    parser.add_argument(
        "--mnemonic-local-files-only",
        action="store_true",
        help="Only load mnemonic model files already present in the local HF cache/path",
    )
    parser.add_argument(
        "--mnemonic-max-new-tokens",
        type=int,
        default=DEFAULT_MNEMONIC_MAX_NEW_TOKENS,
        help="Maximum tokens to generate for mnemonic output",
    )
    parser.add_argument(
        "--mnemonic-temperature",
        type=float,
        default=DEFAULT_MNEMONIC_TEMPERATURE,
        help="Sampling temperature for mnemonic output",
    )
    parser.add_argument(
        "-l",
        "--language",
        choices=available_languages(),
        default="en",
        help="Language of passphrase",
    )
    parser.add_argument("-f", "--file", type=Path, help="Diceware wordlist file")
    parser.add_argument(
        "-p",
        "--passphrases",
        "-n",
        "--count",
        dest="passphrases",
        metavar="COUNT",
        type=_positive_int,
        default=1,
        help="Complete outputs to generate",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_version()}",
    )
    return parser


def build_llm_prefix_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phrase llm-prefix",
        description="Generate uniformly sampled password prefixes from local LM-ranked candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-w", "--words", type=int, default=10, help="Prefix chunks to generate")
    parser.add_argument(
        "-s",
        "--separator",
        default="-",
        help="Separator between password prefixes",
    )
    parser.add_argument(
        "--prefix-length",
        type=int,
        default=DEFAULT_PREFIX_LENGTH,
        help="Characters to keep from each selected word start",
    )
    parser.add_argument(
        "--choices-per-step",
        type=int,
        default=DEFAULT_CHOICES_PER_STEP,
        help="Uniform prefix choices required at each word position",
    )
    parser.add_argument(
        "--scan-tokens",
        type=int,
        default=DEFAULT_SCAN_TOKENS,
        help="Ranked next-token candidates to scan for unique prefixes",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_LLM_PREFIX_MODEL,
        help="Hugging Face base model id or local model path",
    )
    parser.add_argument(
        "--model-revision",
        help="Optional Hugging Face model revision/hash to pin",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Only load model files already present in the local HF cache/path",
    )
    parser.add_argument(
        "--context",
        default=DEFAULT_LLM_PREFIX_CONTEXT,
        help="Initial local LM context before the first selected prefix",
    )
    parser.add_argument(
        "--max-word-tokens",
        type=int,
        default=DEFAULT_MAX_WORD_TOKENS,
        help="Maximum generated tokens used to complete each selected prefix into a mnemonic word",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_LLM_PREFIX_TEMPERATURE,
        help="Sampling temperature for mnemonic word completion",
    )
    parser.add_argument(
        "--allow-shortfall",
        action="store_true",
        help="Allow fewer than --choices-per-step prefixes and report the lower entropy",
    )
    parser.add_argument(
        "-p",
        "--passphrases",
        "-n",
        "--count",
        dest="passphrases",
        metavar="COUNT",
        type=_positive_int,
        default=1,
        help="Complete outputs to generate",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_version()}",
    )
    return parser


def _print_llm_prefix_result(result) -> None:
    model = result.model_id
    if result.model_revision:
        model = f"{model}@{result.model_revision}"
    print(f"password: {result.password}")
    print(f"mnemonic: {result.mnemonic}")
    print(f"entropy: {result.entropy_bits:.2f} bits = {result.entropy_formula}")
    print(f"model: {model}")
    print(f"prefix length: {result.prefix_length}")
    print("candidate counts: " + " ".join(str(count) for count in result.candidate_counts))


def main_llm_prefix(argv: Sequence[str] | None = None) -> int:
    parser = build_llm_prefix_parser()
    args = parser.parse_args(argv)

    try:
        for index in range(args.passphrases):
            if index:
                print()
            result = generate_llm_prefix_phrase(
                model_id=args.model,
                model_revision=args.model_revision,
                words=args.words,
                prefix_length=args.prefix_length,
                choices_per_step=args.choices_per_step,
                scan_tokens=args.scan_tokens,
                separator=args.separator,
                context=args.context,
                max_word_tokens=args.max_word_tokens,
                temperature=args.temperature,
                local_files_only=args.local_files_only,
                allow_shortfall=args.allow_shortfall,
            )
            _print_llm_prefix_result(result)
    except (OSError, ValueError, MnemonicDependencyError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "llm-prefix":
        return main_llm_prefix(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        wordlist = read_file(args.file) if args.file else None
        generator = Generator(
            wordlist=wordlist,
            language=args.language,
            words=args.words,
            separator=args.separator,
            capitalize=args.capitalize,
            digits=args.digits,
            prefix_length=args.prefix_length,
        )
        entropy_bits = generator.entropy_bits()
        for _ in range(args.passphrases):
            phrase, full_phrase = generator.phrase_with_full_words()
            if full_phrase is not None:
                print(full_phrase)
            print(phrase)
            if args.mnemonic:
                mnemonic = generate_mnemonic(
                    phrase,
                    full_phrase,
                    model_id=args.mnemonic_model,
                    max_new_tokens=args.mnemonic_max_new_tokens,
                    temperature=args.mnemonic_temperature,
                    local_files_only=args.mnemonic_local_files_only,
                )
                print(f"mnemonic: {mnemonic}")
            print(f"entropy: {entropy_bits:.2f} bits")
    except (OSError, ValueError, MnemonicDependencyError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")

    return 0
