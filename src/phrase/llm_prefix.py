from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from .core import random_int
from .mnemonic import MnemonicDependencyError

DEFAULT_LLM_PREFIX_MODEL = "Qwen/Qwen3-8B-Base"
DEFAULT_CHOICES_PER_STEP = 1024
DEFAULT_SCAN_TOKENS = 50_000
DEFAULT_PREFIX_LENGTH = 3
DEFAULT_MAX_WORD_TOKENS = 8
DEFAULT_TEMPERATURE = 0.7
DEFAULT_CONTEXT = "A vivid memorable sentence: "

_ASCII_LETTERS = re.compile(r"^[a-z]+$")
_GERMAN_FOLD = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
    }
)


@dataclass(frozen=True, slots=True)
class LlmPrefixResult:
    """Generated password material and audit data for LLM-prefix mode."""

    password: str
    mnemonic: str
    prefixes: list[str]
    words: list[str]
    candidate_counts: list[int]
    entropy_bits: float
    model_id: str
    model_revision: str | None
    prefix_length: int
    choices_per_step: int

    @property
    def entropy_formula(self) -> str:
        if not self.candidate_counts:
            return "0"
        if len(set(self.candidate_counts)) == 1:
            count = self.candidate_counts[0]
            return f"{len(self.candidate_counts)} x log2({count})"
        return " + ".join(f"log2({count})" for count in self.candidate_counts)


@lru_cache(maxsize=2)
def _load_model(
    model_id: str,
    revision: str | None = None,
    local_files_only: bool = False,
):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise MnemonicDependencyError(
            "llm-prefix generation needs the optional dependencies: transformers, torch, accelerate"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=revision,
        local_files_only=local_files_only,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=revision,
        device_map="auto",
        torch_dtype="auto",
        local_files_only=local_files_only,
    )
    model.eval()
    return tokenizer, model, torch


def _fold_ascii(text: str) -> str:
    folded = text.translate(_GERMAN_FOLD).lower()
    normalized = unicodedata.normalize("NFKD", folded)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _strip_word_start(text: str) -> str:
    stripped = text.replace("Ġ", " ").replace("▁", " ").lstrip()
    while stripped and unicodedata.category(stripped[0]).startswith("P"):
        stripped = stripped[1:].lstrip()
    return stripped


def _leading_letters(text: str) -> str:
    letters: list[str] = []
    for char in text:
        if not char.isalpha():
            break
        letters.append(char)
    return _fold_ascii("".join(letters))


def normalize_prefix(token_text: str, prefix_length: int) -> str | None:
    """Return an ASCII lowercase password prefix from decoded token text."""
    if prefix_length <= 0:
        raise ValueError("prefix_length must be greater than zero")

    letters = _leading_letters(_strip_word_start(token_text))
    if len(letters) < prefix_length:
        return None

    prefix = letters[:prefix_length]
    if not _ASCII_LETTERS.fullmatch(prefix):
        return None
    return prefix


def unique_prefixes_from_token_ids(
    tokenizer,
    token_ids: list[int],
    *,
    prefix_length: int,
    limit: int,
) -> list[str]:
    """Decode ranked token ids into the first distinct normalized prefixes."""
    if limit <= 0:
        raise ValueError("choices_per_step must be greater than zero")

    seen: set[str] = set()
    prefixes: list[str] = []
    special_ids = set(getattr(tokenizer, "all_special_ids", []) or [])
    for token_id in token_ids:
        if token_id in special_ids:
            continue
        token_text = tokenizer.decode([token_id], clean_up_tokenization_spaces=False)
        prefix = normalize_prefix(token_text, prefix_length)
        if prefix is None or prefix in seen:
            continue
        seen.add(prefix)
        prefixes.append(prefix)
        if len(prefixes) == limit:
            break
    return prefixes


def _resolved_model_revision(tokenizer, model, requested_revision: str | None) -> str | None:
    for source in (getattr(model, "config", None), tokenizer):
        revision = getattr(source, "_commit_hash", None)
        if revision:
            return revision
    init_kwargs = getattr(tokenizer, "init_kwargs", None)
    if isinstance(init_kwargs, dict) and init_kwargs.get("_commit_hash"):
        return init_kwargs["_commit_hash"]
    return requested_revision


def _model_device(model):
    device = getattr(model, "device", None)
    if device is not None:
        return device
    return next(model.parameters()).device


def _tokenize_on_model(tokenizer, model, text: str) -> dict:
    inputs = tokenizer(text, return_tensors="pt")
    device = _model_device(model)
    return {name: tensor.to(device) for name, tensor in inputs.items()}


def _ranked_next_token_ids(tokenizer, model, torch, context: str, scan_tokens: int) -> list[int]:
    if scan_tokens <= 0:
        raise ValueError("scan_tokens must be greater than zero")

    inputs = _tokenize_on_model(tokenizer, model, context)
    with torch.inference_mode():
        outputs = model(**inputs)

    logits = outputs.logits[0, -1, :]
    count = min(scan_tokens, logits.shape[-1])
    return torch.topk(logits, k=count).indices.tolist()


def _complete_word(
    tokenizer,
    model,
    torch,
    context: str,
    prefix: str,
    *,
    max_word_tokens: int,
    temperature: float,
) -> str:
    if max_word_tokens <= 0:
        return prefix

    inputs = _tokenize_on_model(tokenizer, model, context + prefix)
    prompt_length = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            do_sample=True,
            temperature=temperature,
            max_new_tokens=max_word_tokens,
            pad_token_id=tokenizer.eos_token_id,
        )[0]

    generated = tokenizer.decode(
        output[prompt_length:],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    suffix = _leading_letters(generated)
    return prefix + suffix


def generate_llm_prefix_phrase(
    *,
    model_id: str = DEFAULT_LLM_PREFIX_MODEL,
    model_revision: str | None = None,
    words: int = 10,
    prefix_length: int = DEFAULT_PREFIX_LENGTH,
    choices_per_step: int = DEFAULT_CHOICES_PER_STEP,
    scan_tokens: int = DEFAULT_SCAN_TOKENS,
    separator: str = "-",
    context: str = DEFAULT_CONTEXT,
    max_word_tokens: int = DEFAULT_MAX_WORD_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    local_files_only: bool = False,
    allow_shortfall: bool = False,
) -> LlmPrefixResult:
    """Generate uniformly sampled password prefixes from local LM-ranked candidates."""
    if words <= 0:
        raise ValueError("words must be greater than zero")
    if prefix_length <= 0:
        raise ValueError("prefix_length must be greater than zero")
    if choices_per_step <= 0:
        raise ValueError("choices_per_step must be greater than zero")
    if scan_tokens <= 0:
        raise ValueError("scan_tokens must be greater than zero")
    if max_word_tokens < 0:
        raise ValueError("max_word_tokens must not be negative")
    if temperature <= 0:
        raise ValueError("temperature must be greater than zero")

    tokenizer, model, torch = _load_model(model_id, model_revision, local_files_only)
    resolved_revision = _resolved_model_revision(tokenizer, model, model_revision)
    current_context = context if not context or context[-1].isspace() else f"{context} "
    prefixes: list[str] = []
    full_words: list[str] = []
    candidate_counts: list[int] = []

    for position in range(words):
        token_ids = _ranked_next_token_ids(tokenizer, model, torch, current_context, scan_tokens)
        candidates = unique_prefixes_from_token_ids(
            tokenizer,
            token_ids,
            prefix_length=prefix_length,
            limit=choices_per_step,
        )
        if len(candidates) < choices_per_step and not allow_shortfall:
            raise ValueError(
                f"only {len(candidates)} unique prefixes found at position {position + 1}; "
                "increase --scan-tokens, lower --choices-per-step, or use --allow-shortfall"
            )
        if not candidates:
            raise ValueError(f"no unique prefixes found at position {position + 1}")

        chosen = candidates[random_int(len(candidates))]
        word = _complete_word(
            tokenizer,
            model,
            torch,
            current_context,
            chosen,
            max_word_tokens=max_word_tokens,
            temperature=temperature,
        )
        prefixes.append(chosen)
        full_words.append(word)
        candidate_counts.append(len(candidates))
        current_context += f"{word} "

    entropy_bits = sum(math.log2(count) for count in candidate_counts)
    return LlmPrefixResult(
        password=separator.join(prefixes),
        mnemonic=" ".join(full_words),
        prefixes=prefixes,
        words=full_words,
        candidate_counts=candidate_counts,
        entropy_bits=entropy_bits,
        model_id=model_id,
        model_revision=resolved_revision,
        prefix_length=prefix_length,
        choices_per_step=choices_per_step,
    )
