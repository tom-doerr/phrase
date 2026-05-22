# phrase - the passphrase generator

`phrase` is a command-line tool to generate easy-to-remember passwords from
random words.

## Installation

### Python

Install the Python package from PyPI:

    $ python -m pip install diceware-phrase

Or install the current checkout for development:

    $ python -m pip install -e ".[dev]"

Install local LLM dependencies when you want `--mnemonic` or `llm-prefix`:

    $ python -m pip install -e ".[llm]"

### Download

Just download the
[latest release](https://github.com/bjoernalbers/phrase/releases/latest)
for your platform and make it executable, i.e. like this:

    $ curl -L https://github.com/bjoernalbers/phrase/releases/latest/download/phrase-darwin-arm64 -o /usr/local/bin/phrase
    $ chmod +x /usr/local/bin/phrase

### Build it yourself

Clone this repo and build the binary via `make`.

## Usage

Generate random passphrase:

    $ phrase
    correct horse battery staple

Generate several outputs in any mode with `-n`/`--count`. The older `-p`/`--passphrases` option is still accepted as an alias:

    $ phrase --count 3

Generate a German passphrase from unique three-character word prefixes:

    $ phrase -l de -w 8 --prefix-length 3
    rommee emmy spicken bahn butter litschi zinken frost
    rom emm spi bah but lit zin fro
    entropy: 85.55 bits

Generate a local-only mnemonic after the password material is fixed. The model is loaded in-process through Hugging Face Transformers; the LLM only sees the already-generated password material and must not choose or alter it. Thinking models may print their thinking process, and the CLI guarantees a final `Mnemonic sentence:` marker if the model stops before producing one:

    $ phrase -l de -w 8 --prefix-length 3 --mnemonic --mnemonic-model Qwen/Qwen3.5-0.8B
    rommee emmy spicken bahn butter litschi zinken frost
    rom emm spi bah but lit zin fro
    mnemonic: Rommee-Emmy spickt Bahn-Butter-Litschi, zinkt Frost.
    entropy: 85.55 bits

Generate prefixes from local base-LM ranked candidate sets, while keeping the entropy source as uniform CSPRNG selection over the actual normalized prefix set. The default model is `Qwen/Qwen3-8B-Base`; pass `--model` for any Hugging Face model id or local path:

    $ phrase llm-prefix --words 10 --prefix-length 3 --choices-per-step 1024
    password: mar-rav-lun-cof-yel-fog-sto-gar-elu-nar
    mnemonic: marble raven lunar coffee yellow fog stone garden elusive narrator
    entropy: 100.00 bits = 10 x log2(1024)
    model: Qwen/Qwen3-8B-Base
    prefix length: 3
    candidate counts: 1024 1024 1024 1024 1024 1024 1024 1024 1024 1024

Use `--model-revision` to pin a Hugging Face revision and `--local-files-only` to require an already cached model or local model path. If a step cannot find the requested number of unique prefixes, the command fails unless `--allow-shortfall` is set; entropy is always computed from the printed candidate counts. After each random prefix choice, mnemonic words are completed with the model's most likely same-word continuation tokens; the next uniform choice happens only at the next word start.

Use the Python API:

    >>> from phrase import generate
    >>> generate()
    'correct horse battery staple'

Getting help:

    $ phrase -h
    ...

## Python packaging

Build the source distribution and wheel:

    $ python -m build

Validate the distribution metadata before uploading:

    $ python -m twine check dist/*

## License

phrase is released under the [MIT License](LICENSE).

The built-in wordlists come from these sources:

- [`de`](https://raw.githubusercontent.com/bjoernalbers/diceware-wordlist-german/main/wordlist-german-diceware.txt): Copyright by [Björn Albers](https://github.com/bjoernalbers/diceware-wordlist-german) ([MIT License](https://github.com/bjoernalbers/diceware-wordlist-german/blob/main/LICENSE))
- [`en`](https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt): Copyright by [Electronic Frontier Foundation](https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases) ([Creative Commons Attribution License](https://www.eff.org/copyright))
- [`fr`](https://raw.githubusercontent.com/ArthurPons/diceware-fr-alt/master/diceware-fr-alt.txt): Copyright by [Arthur Pons](https://github.com/ArthurPons/diceware-fr-alt) ([MIT License](https://github.com/ArthurPons/diceware-fr-alt/blob/master/LICENSE))
- [`nl`](https://mko.re/diceware/diceware-wordlist-composites-nl.txt): Copyright by [Remko Tronçon](https://el-tramo.be/blog/diceware-nl) ([MIT License](https://github.com/remko/dicewords/blob/master/LICENSE))
