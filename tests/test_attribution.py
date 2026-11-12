import asyncio

import numpy as np
import pytest

from spet import attribution as A
from spet.run import RunSpec, execute
from spet.providers import StubProvider
from spet.stub import respond

SECTIONS = [
    "You are a support assistant for a developer tools company.",  # 0: no planted behaviour
    "Always apologise when the user reports a problem.",            # 1: apology
    "Be humble about uncertainty.",                                  # 2: hedge
    "Answer in plain prose. Keep answers under 200 words.",          # 3: no planted behaviour
]
QUERIES = ["My build fails with a missing module.", "How do I rotate an API key?", "Why is my query slow?"]
PLANTED = {("apology", 1), ("hedge", 2)}


def test_bh_matches_reference():
    # sorted p .01,.03,.04,.2 -> p*m/rank .04,.06,.0533,.2 -> running min from the top .04,.0533,.0533,.2
    q = A.benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert q == pytest.approx([0.04, 0.16 / 3, 0.16 / 3, 0.2])


def test_sign_flip_exact_extremes():
    rng = np.random.default_rng(0)
    assert A.sign_flip_p(np.zeros(8), rng) == 1.0
    # all 8 diffs positive and equal: only the all-+ and all-- sign vectors are as extreme -> 2/256
    assert A.sign_flip_p(np.ones(8), rng) == pytest.approx(2 / 256)


def test_shapley_additive_game_is_exact():
    w = [3.0, -1.0, 0.5, 2.0]
    phi = A.shapley_values(4, lambda s: sum(w[i] for i in s))
    assert phi == pytest.approx(w)


def test_shapley_interaction_splits_evenly():
    phi = A.shapley_values(3, lambda s: 1.0 if {0, 1} <= s else 0.0)
    assert phi == pytest.approx([0.5, 0.5, 0.0])


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_planted_instructions_are_recovered(seed):
    spec = RunSpec(id="t", title="t", sections=SECTIONS, queries=QUERIES, n_per_query=8, seed=seed)
    b = asyncio.run(execute(spec, StubProvider(respond)))
    sig = {(e.detector, e.section) for e in b.effects if e.significant}
    # exactly the planted effects: no misses, no spill-over onto other quirks or inert sections
    assert sig == PLANTED, f"missed {PLANTED - sig}, spurious {sig - PLANTED}"
    for d, k in PLANTED:
        e = next(e for e in b.effects if (e.detector, e.section) == (d, k))
        assert e.delta > 0 and e.ci[0] > 0
