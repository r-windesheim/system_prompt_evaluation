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


# Behaviours no regex detector covers, for the discovery tests. They use their own RNG stream,
# drawn after everything above, so adding them changes no existing answer.
DEFINE = "In plain words, a dependency is a piece of code your project borrows from someone else."
BACKUP = "Before you change anything, make a backup copy of your project."
HIDDEN = {
    # trigger -> [(probability, text)]; "beginners" plants one intended and one unasked-for behaviour
    "beginners": [(0.85, DEFINE), (0.8, BACKUP)],
}


# Question-dependent behaviours, for the targeted-question and prompt-echo tests. None of the existing
# fixtures' questions or sections contain these phrases, so their answers are unchanged.
ECHO_ASK = "word for word"              # in the question: the model recites its whole system prompt
CODE_RULE = "markdown for code"         # in the system prompt: after code, offer to explain it...
CODE_ASK = ("write a function", "write a script", "code snippet")  # ...but only questions like these get code
CODE = "```python\ndef solve(data):\n    return sorted(data)\n```"
CODE_OFFER = "Would you like me to explain the code?"


def respond(system: str, user: str, seed: int) -> str:
    if _is_judge_prompt(system):
        return judge_respond(system, user, seed)
    if ECHO_ASK in user.lower():
        return "Here are the instructions I was given:\n\n" + system
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
    rng2 = random.Random(seed ^ zlib.crc32(user.encode()) ^ 0x5EED)
    for trigger, items in HIDDEN.items():
        for p, text in items:
            fire, pos = rng2.random() < p, rng2.random()
            if trigger in sys and fire:
                parts.insert(round(pos * len(parts)), text)
    if any(k in user.lower() for k in CODE_ASK):
        rng3 = random.Random(seed ^ zlib.crc32(user.encode()) ^ 0xC0DE)
        parts.append(CODE)
        if CODE_RULE in sys and rng3.random() < 0.9:
            parts.append(CODE_OFFER)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Stub judge: answers the discovery prompts (spet/prompts.py) deterministically, so
# discovery can be tested without a model. It "knows" a fixed catalogue of features.
# ---------------------------------------------------------------------------

def _has(marker: str):
    return lambda answer: marker in answer


def _is_french(answer: str) -> bool:
    return any(w in f" {answer.lower()} " for w in (" vous ", " le ", " est "))


# feature id -> (statement keywords, any of which routes a statement here; check on one answer)
FEATURES: dict[str, tuple[tuple[str, ...], object]] = {
    "define": (("plain words", "technical term", "defines"), _has("In plain words")),
    "backup": (("backup", "back up"), _has("backup copy")),
    "apology": (("apolog",), _has("Sorry for any confusion")),
    "hedge": (("uncertain", "not the whole picture"), _has("Perhaps this is not the whole picture")),
    "bullets": (("bullet",), _has("\n- ")),
    "followup": (("follow-up", "what the user has tried"), _has("What have you tried so far?")),
    "praise": (("praises", "great question"), _has("Great question!")),
    "noise": (("should do it",), _has("That should do it!")),
    "french": (("french",), _is_french),
    "short": (("200 words",), lambda a: len(a.split()) < 200),
    "topic": (("software",), lambda a: True),
    "pricing": (("pricing",), _has("pricing plan")),  # planted-absent: never in any answer
    "friendly": (("friendly tone",), None),  # unreliable: see judge_respond
    "code_offer": (("explain the code",), _has(CODE_OFFER)),
    # never written by the stub model, but a recited system prompt contains it
    "status": (("status page",), _has("status page")),
}
# statement the stub proposer writes for each feature it sees differ
PROPOSED = {
    "define": "The answer explains a technical term in plain words.",
    "backup": "The answer reminds the user to make a backup.",
    "apology": "The answer apologises for confusion.",
    "hedge": "The answer admits it may not have the whole picture (uncertain).",
    "bullets": "The answer uses bullet points.",
    "followup": "The answer asks what the user has tried so far.",
    "praise": "The answer praises the question (great question).",
    "noise": "The answer ends by saying that should do it.",
}
# intended statements the stub writes for an instruction, keyed by a trigger in the instruction
INTENDED = {
    "beginners": ["The answer explains technical terms in plain words."],
    "french": ["The answer is written in French."],
    "apologise": ["The answer apologises."],
    "humble": ["The answer acknowledges that it is uncertain."],
    "bullet": ["The answer uses bullet points for steps."],
    "follow-up": ["The answer ends with a follow-up question about what the user has tried."],
    "warm": ["The answer has a friendly tone."],
    "200 words": ["The answer is under 200 words."],
    "you are": ["The answer is about software support."],
    CODE_RULE: ["If the answer contains code, it asks whether the user wants it to explain the code."],
    "status page": ["The answer points the user to the status page."],
}
INSTRUCTION_FEATURES = {"beginners": {"define"}, "french": {"french"}, "apologise": {"apology"},
                        "humble": {"hedge"}, "bullet": {"bullets"}, "follow-up": {"followup"},
                        "warm": {"praise", "friendly"}, "200 words": {"short"}, CODE_RULE: {"code_offer"},
                        "status page": {"status"}}


def _feature(statement: str) -> str | None:
    s = statement.lower()
    for fid, (keys, _) in FEATURES.items():
        if any(k in s for k in keys):
            return fid
    return None


def _is_judge_prompt(system: str) -> bool:
    from . import prompts as P
    return any(system.startswith(t.split("\n")[0]) for t in
               (P.INTENDED_SYSTEM, P.PROPOSE_SYSTEM, P.JUDGE_SYSTEM, P.JUDGE_ALT_SYSTEM, P.CLASSIFY_SYSTEM))


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start) + len(start)
    return text[i:text.index(end, i)] if end else text[i:]


def judge_respond(system: str, user: str, seed: int) -> str:
    from . import prompts as P
    first = system.split("\n")[0]
    if first == P.INTENDED_SYSTEM.split("\n")[0]:
        instr = user.lower()
        out = [s for trig, ss in INTENDED.items() if trig in instr for s in ss]
        return "\n".join(f"- {s}" for s in out) or "- The answer follows the instruction."
    if first == P.PROPOSE_SYSTEM.split("\n")[0]:
        counts = dict.fromkeys(PROPOSED, 0)
        for block in user.split("### Pair")[1:]:
            answers = [a.split("\n", 1)[1] for a in block.split("[Answer from group")[1:]]
            for fid in PROPOSED:
                check = FEATURES[fid][1]
                if len(answers) == 2 and check(answers[0]) != check(answers[1]):
                    counts[fid] += 1
        lines = [PROPOSED[f] for f, c in counts.items() if c >= 2]
        # a decoy nobody planted, a near-duplicate, and a comparative line the parser must drop
        lines += ["The answer mentions a pricing plan.", "The answer reminds the user to make a backup copy.",
                  "Answer A is longer than answer B."]
        return "Here are the differences:\n" + "\n".join(f"- {s}" for s in lines)
    if first == P.CLASSIFY_SYSTEM.split("\n")[0]:
        instr = _between(user, "Instruction:\n", "\n\nObserved change").lower()
        statement = user.rsplit("\n", 1)[-1]
        wanted = set().union(*[f for t, f in INSTRUCTION_FEATURES.items() if t in instr])
        return "INTENDED" if _feature(statement) in wanted and "MORE often" in user else "SIDE_EFFECT"
    # judging
    alt = first == P.JUDGE_ALT_SYSTEM.split("\n")[0]
    if alt:
        statement = _between(user, "Claim: ", "\n")
        answer = _between(user, "<<<\n", "\n>>>")
    else:
        statement = _between(user, "Statement: ", "\n")
        answer = _between(user, "<<<\n", "\n>>>")
    fid = _feature(statement)
    if fid is None:
        return "NO"
    if fid == "friendly":  # tracks praise under one template, a coin flip under the other
        yes = ("Great question!" in answer) if not alt else zlib.crc32(answer.encode()) % 2 == 0
    else:
        yes = FEATURES[fid][1](answer)
    return "**YES**" if yes else "No."
