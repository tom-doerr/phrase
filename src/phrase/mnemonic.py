from __future__ import annotations

import re
from functools import lru_cache

DEFAULT_MNEMONIC_MODEL = "Qwen/Qwen3.5-0.8B"
DEFAULT_MAX_NEW_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.6
_FINAL_MNEMONIC = re.compile(r"\bmnemonic sentence\s*:", re.IGNORECASE)


class MnemonicDependencyError(RuntimeError):
    """Raised when optional local LLM dependencies are unavailable."""


@lru_cache(maxsize=2)
def _load_model(model_id: str, local_files_only: bool = False):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise MnemonicDependencyError(
            "mnemonic generation needs the optional dependencies: transformers, torch, accelerate"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=local_files_only)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype="auto",
        local_files_only=local_files_only,
    )
    model.eval()
    return tokenizer, model, torch


def build_prompt(prefix_phrase: str, full_phrase: str | None = None) -> str:
    context = f"Password prefixes: {prefix_phrase}"
    if full_phrase:
        context += f"\nFull source words: {full_phrase}"

    return (
        "Create one short, vivid, memorable mnemonic sentence for remembering a password.\n"
        "The actual password is exactly the prefix sequence; the mnemonic is only a memory aid. "
        "Do not change, sort, omit, or add password prefixes. The mnemonic sentence may use "
        "the full source words or other words that start with those prefixes, as long as their "
        "order matches the password prefixes. Use this exact output format and do not add extra "
        "analysis:\n"
        "Thinking Process:\n"
        "1. Map the prefixes to source or same-prefix memory words.\n"
        "2. Choose one vivid sentence that preserves the prefix order.\n"
        "Mnemonic sentence: <one sentence>\n"
        f"{context}\n"
    )


def _decode_response(tokenizer, output_ids, prompt_length: int) -> str:
    generated = output_ids[prompt_length:]
    text = tokenizer.decode(generated, skip_special_tokens=True).strip()
    return " ".join(text.split())


def ensure_final_mnemonic(text: str, prefix_phrase: str, full_phrase: str | None = None) -> str:
    """Append a final mnemonic marker when a thinking model stops before one."""
    cleaned = " ".join(text.split())
    if _FINAL_MNEMONIC.search(cleaned):
        return cleaned

    fallback = (full_phrase or prefix_phrase).strip().rstrip(".")
    if not fallback:
        return cleaned
    if cleaned:
        return f"{cleaned} Mnemonic sentence: {fallback}."
    return f"Mnemonic sentence: {fallback}."


def generate_mnemonic(
    prefix_phrase: str,
    full_phrase: str | None = None,
    *,
    model_id: str = DEFAULT_MNEMONIC_MODEL,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    local_files_only: bool = False,
) -> str:
    """Generate a local-only mnemonic sentence with a Hugging Face causal LM."""
    if max_new_tokens <= 0:
        raise ValueError("mnemonic max_new_tokens must be greater than zero")
    if temperature <= 0:
        raise ValueError("mnemonic temperature must be greater than zero")

    tokenizer, model, torch = _load_model(model_id, local_files_only)
    prompt = build_prompt(prefix_phrase, full_phrase)

    if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
        messages = [
            {"role": "system", "content": "You write compact private memory aids."},
            {"role": "user", "content": prompt},
        ]
        inputs = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
    else:
        inputs = tokenizer(prompt, return_tensors="pt")

    inputs = {name: tensor.to(model.device) for name, tensor in inputs.items()}
    prompt_length = inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            do_sample=True,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
            remove_invalid_values=True,
            renormalize_logits=True,
        )[0]

    text = _decode_response(tokenizer, output, prompt_length)
    return ensure_final_mnemonic(text, prefix_phrase, full_phrase)
