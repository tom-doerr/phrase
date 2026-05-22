from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import Generator, available_languages, read_file
from .mnemonic import DEFAULT_MNEMONIC_MODEL, MnemonicDependencyError, generate_mnemonic


def _installed_version() -> str:
    try:
        return version("diceware-phrase")
    except PackageNotFoundError:
        return __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phrase",
        description="Generate easy-to-remember passwords from random words.",
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
        default=96,
        help="Maximum tokens to generate for mnemonic output",
    )
    parser.add_argument(
        "--mnemonic-temperature",
        type=float,
        default=0.6,
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
        type=int,
        default=1,
        help="Passphrases to generate",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_version()}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
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
