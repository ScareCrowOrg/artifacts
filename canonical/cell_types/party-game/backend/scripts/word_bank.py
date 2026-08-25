"""
party-game — Word Bank, guess normalization and AI word selection.

This module is the single source of truth for the game's *word content*:

- ``WORD_BANK`` — curated offline vocabulary grouped by category.  Used as a
  deterministic fallback whenever the LLM word picker is unavailable (EP-3).
- ``pick_word`` / ``pick_category`` — deterministic selection (seeded ``rng``
  for tests).
- ``guess_matches`` — normalized guess validation (exact or contains; accents,
  case and punctuation are stripped).
- ``generate_hint`` — progressive template hints (length → first letter →
  last letter), no LLM round-trip required for hints in the MVP.
- ``pick_word_with_llm`` — tries an LLM (Ollama, ``/api/generate``) for a
  word, falling back to the word bank on ANY failure (network, timeout,
  malformed answer).

Naming is English (RULESET.md 4.3).  The module is pure Python + stdlib so it
can be unit-tested without a running backend.
"""

import json
import logging
import os
import random
import re
import urllib.request
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Vocabulary ────────────────────────────────────────────────────────────────

#: Curated offline word bank.  Category → words (lowercase, ASCII).
WORD_BANK: Dict[str, List[str]] = {
    "animals": [
        "dog", "cat", "horse", "elephant", "penguin", "dolphin", "lion",
        "butterfly", "rabbit", "whale",
    ],
    "objects": [
        "umbrella", "ladder", "rocket", "telescope", "scissors", "balloon",
        "clock", "candle", "key", "bridge",
    ],
    "food": [
        "pizza", "banana", "sandwich", "chocolate", "carrot", "watermelon",
        "cupcake", "popcorn", "spaghetti", "lemon",
    ],
    "places": [
        "beach", "castle", "mountain", "school", "hospital", "airport",
        "jungle", "desert", "stadium", "library",
    ],
    "actions": [
        "running", "singing", "sleeping", "dancing", "cooking", "swimming",
        "reading", "climbing", "painting", "laughing",
    ],
}

DEFAULT_CATEGORIES: List[str] = list(WORD_BANK)

#: Number of wrong guesses before the backend publishes a hint (per round).
HINT_WRONG_COUNT: int = 3

_SAFE_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z\s'-]{1,40}$")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]")
_ACCENTS = str.maketrans({
    "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "å": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n",
})


# ── Public API ────────────────────────────────────────────────────────────────


def normalize_text(text: str) -> str:
    """Return a comparable form of *text*: lowercase, accent-folded, no punctuation.

    Accents are collapsed to their ASCII base (á → a) so a Portuguese guess
    (e.g. "pénguim") matches the same English word ("penguin").
    """
    return _NORMALIZE_RE.sub("", text.lower().translate(_ACCENTS))


def guess_matches(guess: str, secret: str) -> bool:
    """Return True when *guess* matches *secret*: exact, or a phrase that
    CONTAINS the secret word (e.g. "it's a penguin").

    Deliberately one-directional: a short guess being a prefix of the secret
    (e.g. "key" for "monkey", "ele" for "elephant") does NOT match.
    """
    g = normalize_text(guess)
    s = normalize_text(secret)
    if not g or not s:
        return False
    return g == s or s in g


def pick_category(rng: Optional[random.Random] = None) -> str:
    """Return a random category from the word bank."""
    r = rng or random
    return r.choice(DEFAULT_CATEGORIES)


def pick_word(
    category: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> Tuple[str, str]:
    """Return ``(category, word)``.

    Uses *category* when provided (and present in the bank), otherwise a random
    category.  Deterministic when an ``rng`` is supplied (tests).
    """
    r = rng or random
    if category and category in WORD_BANK:
        cat = category
    else:
        cat = r.choice(DEFAULT_CATEGORIES)
    return cat, r.choice(WORD_BANK[cat])


def word_length_hint(secret: str) -> str:
    """Return a masked length hint, e.g. ``_ _ _ _`` for 'rocket'."""
    return " ".join("_" for _ in secret)


def generate_hint(
    secret: str,
    hint_count: int,
    category: Optional[str] = None,
) -> str:
    """Return a progressive template hint for *hint_count* (1-based)."""
    first = secret[0].upper() if secret else "?"
    last = secret[-1].upper() if secret else "?"
    if hint_count <= 1:
        parts = [f"The word has {len(secret)} letters"]
        if category:
            parts.append(f"belongs to the category '{category}'")
        return ", ".join(parts) + "."
    if hint_count == 2:
        return f"The word starts with '{first}'."
    if hint_count == 3:
        return f"The word starts with '{first}' and ends with '{last}'."
    if hint_count == 4:
        return f"Mask: {word_length_hint(secret)}. It starts with '{first}'."
    return f"One of the '{category}' words." if category else "Keep guessing!"


def _sanitize_llm_word(raw: str, category: Optional[str]) -> Optional[str]:
    """Extract a single valid word from an LLM free-text answer, or None."""
    if not raw:
        return None
    # Take the first whitespace/comma-separated token that looks like a word.
    for token in re.split(r"[\s,;.!]+", raw.strip()):
        token = token.strip("'\"[]{}()")
        if _SAFE_WORD_RE.match(token):
            return token.lower()
    return None


def _llm_pick_word(
    base_url: str,
    model: str,
    timeout: float,
    category: Optional[str] = None,
) -> Optional[str]:
    """Call the Ollama ``/api/generate`` endpoint; return a word or None."""
    prompt = (
        "You pick a single secret word for a drawing/guessing game "
        "(Gartic-like). Reply with ONLY the word, lowercase, no explanation, "
        "no quotes."
    )
    if category:
        prompt += f" Choose a word from the category '{category}'."
    else:
        prompt += " Choose a common, drawable noun."

    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 12},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return _sanitize_llm_word(payload.get("response", ""), category)


def _ollama_base_url() -> str:
    """Resolve the Ollama base URL for the RUNNING environment.

    Order: ``OLLAMA_BASE_URL`` env → ``OLLAMA_HOST`` env → backend config
    (``ollama_base_url`` from settings.json, when importable) → loopback.
    Without this, the cell script hardcoding ``localhost:11434`` would be
    unreachable from the backend container (its own loopback).
    """
    env = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST")
    if env:
        return env
    try:
        from backend.app.config import Config  # type: ignore

        configured = Config.ollama_base_url()
        if configured:
            return configured
    except Exception:
        pass
    return "http://localhost:11434"


def pick_word_with_llm(
    base_url: Optional[str] = None,
    model: str = "mistral",
    timeout: float = 5.0,
    category: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> Tuple[str, str]:
    """Return ``(category, word)`` — LLM first, word bank fallback (EP-3).

    *base_url* defaults to the resolved environment config
    (``_ollama_base_url``).  Any failure in the LLM path (unreachable service,
    timeout, malformed answer, or a word the sanitizer rejects) falls back to
    the deterministic word bank, so the game never blocks on the model.
    """
    url = base_url or _ollama_base_url()
    try:
        word = _llm_pick_word(url, model, timeout, category)
        if word and _SAFE_WORD_RE.match(word):
            cat = category if (category and category in WORD_BANK) else _nearest_category(word)
            return cat, word
        logger.info("[party-game] LLM word picker returned nothing usable; using word bank")
    except Exception as exc:  # network / timeout / JSON errors
        logger.warning("[party-game] LLM word pick failed (%s); using word bank", exc)
    return pick_word(category, rng)


def _nearest_category(word: str) -> Optional[str]:
    """Return the bank category that contains *word*, or None (no category).

    None is deliberate: an LLM word outside the bank must NOT get a random
    category, or the hint would claim a wrong category.
    """
    for cat, words in WORD_BANK.items():
        if word in words:
            return cat
    return None
