import asyncio

from spet import schedule
from spet.providers import StubProvider

SECTIONS = ["You are helpful.", "Always apologise.", "Use bullet points."]
QUERIES = ["How do I boil an egg?", "Rewrite: 'pls send report'"]


def test_grid_is_identical_across_configs():
    jobs = schedule.build(SECTIONS, QUERIES, n_per_query=3, run_seed=7)
    by_cfg: dict[str, list] = {}
    for j in jobs:
        by_cfg.setdefault(j.config, []).append((j.query_idx, j.sample_idx, j.seed, j.user))
    grids = list(by_cfg.values())
    assert len(by_cfg) == 1 + len(SECTIONS)
    assert all(g == grids[0] for g in grids)


def test_removed_section_is_absent_and_others_present():
    for j in schedule.build(SECTIONS, QUERIES, 1, 0):
        for i, s in enumerate(SECTIONS):
            assert (s in j.system) == (i != j.removed)


def test_user_message_is_exactly_the_query():
    """Regression for audit M1: nothing (cache-busters, tags) may leak into the prompt."""
    stub = StubProvider(lambda s, u, seed: "ok")
    jobs = schedule.build(SECTIONS, QUERIES, 4, 1)

    async def go():
        for j in jobs:
            await stub.complete(j.system, j.user, temperature=0.7, seed=j.seed)

    asyncio.run(go())
    assert {r["user"] for r in stub.requests} == set(QUERIES)
    assert all("[sample" not in r["system"] + r["user"] for r in stub.requests)


def test_seeds_differ_by_cell_and_depend_on_run_seed():
    a = {(j.query_idx, j.sample_idx): j.seed for j in schedule.build(SECTIONS, QUERIES, 3, 1)}
    b = {(j.query_idx, j.sample_idx): j.seed for j in schedule.build(SECTIONS, QUERIES, 3, 2)}
    assert len(set(a.values())) == len(a)
    assert a != b


def test_skip_sections():
    cfgs = {j.config for j in schedule.build(SECTIONS, QUERIES, 1, 0, skip={1})}
    assert cfgs == {"full", "without_0", "without_2"}
