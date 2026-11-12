import pytest
from pydantic import ValidationError

from spet import bundle as B


def _minimal(**over):
    data = dict(
        meta=dict(id="t", title="t", created_at="2026-11-12T00:00:00Z", model="stub", provider="stub",
                  temperature=0.7, n_per_query=1, seed=0, queries=["q"]),
        sections=[dict(id=0, label="A", text="Be kind.")],
        configs=[dict(id="full"), dict(id="without_0", removed=0)],
        responses=[dict(config="full", query_idx=0, sample_idx=0, text="Sorry!",
                        spans=[dict(start=0, end=5, detector="apology")])],
        detectors=[dict(id="apology", label="Apology", group="Deference")],
        effects=[dict(detector="apology", section=0, full_mean=20, ablated_mean=0, delta=20,
                      ci=(10, 30), p=0.01, q=0.01, significant=True, n_pairs=1)],
    )
    data.update(over)
    return data


def test_roundtrip(tmp_path):
    b = B.RunBundle.model_validate(_minimal())
    p = tmp_path / "b.json"
    B.dump(b, p)
    assert B.load(p) == b


def test_rejects_out_of_bounds_span():
    bad = _minimal(responses=[dict(config="full", query_idx=0, sample_idx=0, text="Hi",
                                   spans=[dict(start=0, end=5, detector="apology")])])
    with pytest.raises(ValidationError):
        B.RunBundle.model_validate(bad)


def test_requires_full_config():
    with pytest.raises(ValidationError):
        B.RunBundle.model_validate(_minimal(configs=[dict(id="without_0", removed=0)], responses=[]))


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        B.RunBundle.model_validate(_minimal(extra=1))


def test_schema_exports():
    assert '"RunBundle"' in B.json_schema()
