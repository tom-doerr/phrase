from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import Generator, available_languages, read_file


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
        )
        for _ in range(args.passphrases):
            print(generator.phrase())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")

    return 0
