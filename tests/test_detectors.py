import pytest

from spet.detectors import BY_ID, DETECTORS, rates, spans


def hits(det: str, text: str) -> list[str]:
    return [text[s:e] for s, e, d in spans(text, (BY_ID[det],))]


CASES = {
    "apology": (["Sorry about that.", "I apologize for the confusion.", "My apologies."],
                ["He felt sorrowful.", "No problem."]),
    "flattery": (["Great question!", "That's an interesting point.", "What a great idea"],
                 ["The question is hard.", "A great deal of work."]),
    "hedge": (["It might rain.", "Perhaps not.", "It seems fine.", "I think so.", "I'm not sure."],
              ["You may leave.", "It looks like a cat.", "This could work."]),
    "booster": (["It is clearly wrong.", "Absolutely.", "Without a doubt."], ["It is wrong."]),
    "list_item": (["- one", "1. first", "  * nested", "2) second"], ["-1 degrees", "Version 1.2 is out"]),
    "heading": (["## Setup", "# Title"], ["#hashtag", "C# is a language"]),
    "bold": (["This is **important**."], ["2 * 3 * 4"]),
    "parenthetical": (["Rust (a systems language) is fast."], ["f(x)", "()"]),
    "question": (["What do you mean?"], ["I know what you mean."]),
    "clarify": (["Could you provide more details?", "Can you clarify?", "I need more context."],
                ["You could provide feedback later."]),
    "offer": (["Let me know if you need anything.", "I'm happy to help.", "Feel free to ask.", "Hope this helps!"],
              ["Let me know your name."]),
    "caveat": (["It works. However, it is slow.", "But not today."], ["Everything but the kitchen sink."]),
    "disclaimer": (["Please note that rates vary.", "I'm not a lawyer.", "Consult a professional."],
                   ["Note the date."]),
    "meta": (["Let me explain.", "Here's how it works.", "In summary, yes."], ["Here is the file."]),
    "self_ai": (["As an AI, I can't.", "I'm just an AI."], ["AI is useful."]),
    "exclamation": (["Wow!"], ["Wow."]),
    "emoji": (["Nice 🎉"], ["Nice :)"]),
}


@pytest.mark.parametrize("det", sorted(CASES))
def test_detector_examples(det):
    pos, neg = CASES[det]
    for t in pos:
        assert hits(det, t), f"{det} should match: {t!r}"
    for t in neg:
        assert not hits(det, t), f"{det} should NOT match: {t!r}"


def test_every_detector_has_cases():
    assert set(CASES) == {d.id for d in DETECTORS}


def test_spans_are_in_bounds_and_sorted():
    text = "Sorry! Great question. However, it might be (roughly) fine?\n- a\n- b 🎉"
    sp = spans(text)
    assert sp == sorted(sp, key=lambda t: (t[0], t[1]))
    assert all(0 <= s < e <= len(text) for s, e, _ in sp)


def test_rates_per_100_words():
    r = rates("sorry sorry " + "word " * 98)
    assert r["apology"] == pytest.approx(2.0)
    assert rates("")["apology"] == 0.0


def test_typographic_apostrophes():
    assert hits("meta", "Here’s how it works.")
    assert hits("offer", "I’m happy to help.")


def test_list_item_spans_whole_line():
    assert hits("list_item", "1. First step here") == ["1. First step here"]
