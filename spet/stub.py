"""A deterministic fake model with *known* causal structure.

It is used for the planted-instruction tests and for demo bundles. Each
behaviour is switched on by a trigger phrase in the system prompt, so the
ground-truth attribution is known exactly.
"""

from __future__ import annotations

import random
import zlib

FILLER = (
    "The main thing to check is the input format. Start with the smallest example that works. "
    "Then change one variable at a time and compare the output. Write down what you observe. "
    "Most problems of this kind come from a mismatch between what you expect and what is stored. "
    "Once that is clear the fix is usually short. Test it again with the original data."
).split(". ")

BEHAVIOURS = {
    # trigger phrase in system prompt -> (probability per response, inserted text)
    "apologise": (0.85, "Sorry for any confusion earlier."),
    "be humble": (0.8, "Perhaps this is not the whole picture, and it might depend on details."),
    "bullet points": (0.9, "\n- First, isolate the problem.\n- Second, verify the fix.\n"),
    "ask a follow-up": (0.75, "What have you tried so far?"),
    "warm": (0.7, "Great question! I'm happy to help."),
}


def respond(system: str, user: str, seed: int) -> str:
    rng = random.Random(seed ^ zlib.crc32(user.encode()))
    sys = system.lower()
    parts = [s.strip().rstrip(".") + "." for s in rng.sample(FILLER, k=rng.randint(3, 5))]
    for trigger, (p, text) in BEHAVIOURS.items():
        # draw for every behaviour, active or not, so the RNG stream is identical across configs
        fire = rng.random() < p
        pos = rng.random()
        if trigger in sys and fire:
            parts.insert(round(pos * len(parts)), text)
    if rng.random() < 0.15:  # base-rate noise unrelated to any section
        parts.append("That should do it!")
    return " ".join(parts)
