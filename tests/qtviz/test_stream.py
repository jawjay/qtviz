"""0.6 increment 1 — the streaming source ([D76], milestone-0.6-live §1).

`qv.stream(...)` is a mutable, append-able tabular `DataRef` with a
ring-buffer rolling window, notifying through the existing `DataRef.subscribe`
seam. Pure Python + numpy — no Qt; thread-safety is a lock, marshaling is the
View-side binding's job (increment 2).
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import ValidationError  # noqa: E402

pytestmark = pytest.mark.tier1


def test_stream_appends_scalars_and_arrays():
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=0.0, v=1.0)                               # scalars
    feed.append(t=np.array([1.0, 2.0]), v=np.array([2.0, 3.0]))  # arrays
    assert feed.size() == 3
    assert np.allclose(feed.series("t"), [0.0, 1.0, 2.0])
    assert np.allclose(feed.series("v"), [1.0, 2.0, 3.0])
    assert set(feed.schema().names) == {"t", "v"}
    assert feed.schema().kind == "tabular"


def test_stream_rolling_window_drops_old_rows():
    feed = qv.stream({"t": float}, window=5)
    feed.append(t=np.arange(3.0))
    feed.append(t=np.arange(3.0, 8.0))                      # 8 total → keep last 5
    assert feed.size() == 5
    assert np.allclose(feed.series("t"), [3.0, 4.0, 5.0, 6.0, 7.0])
    feed.append(t=np.arange(100.0))                         # one append > window
    assert feed.size() == 5
    assert np.allclose(feed.series("t"), [95.0, 96.0, 97.0, 98.0, 99.0])


def test_stream_append_validation():
    feed = qv.stream({"t": float, "v": float})
    with pytest.raises(ValidationError, match="column"):
        feed.append(t=1.0)                                  # missing v
    with pytest.raises(ValidationError, match="length"):
        feed.append(t=np.arange(3.0), v=np.arange(2.0))     # ragged
    with pytest.raises(ValidationError, match="window"):
        qv.stream({"t": float}, window=0)


def test_stream_subscribe_fires_per_append_and_disposes():
    feed = qv.stream({"t": float})
    hits: list = []
    sub = feed.subscribe(lambda ref: hits.append(ref.version()))
    feed.append(t=1.0)
    feed.append(t=2.0)
    assert hits == [1, 2]
    sub.dispose()
    feed.append(t=3.0)
    assert hits == [1, 2]                                   # unsubscribed


def test_stream_fingerprint_tracks_version():
    feed = qv.stream({"t": float})
    fp0 = feed.fingerprint()
    feed.append(t=1.0)
    assert feed.fingerprint() != fp0                        # value identity churns
    assert feed.version() == 1


def test_stream_resolve_is_a_snapshot():
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.arange(4.0), v=np.arange(4.0))
    arrays = feed.resolve_channels({"x": "t", "y": "v"})
    feed.append(t=99.0, v=99.0)                             # mutate after resolve
    assert len(arrays["x"]) == 4                            # snapshot unmoved
    assert 99.0 not in arrays["x"]


def test_stream_element_construction_and_expression():
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.arange(5.0), v=np.arange(5.0))
    el = qv.Curve(feed, x="t", y=qv.col("v") * 2.0)         # accessors work
    resolved = el.data.resolve_channels(el.channels())
    assert np.allclose(resolved["y"], np.arange(5.0) * 2.0)
    with pytest.raises(ValidationError):                    # schema-validated
        qv.Curve(feed, x="t", y="nope")


def test_stream_threaded_appends_are_consistent():
    feed = qv.stream({"t": float}, window=50_000)
    n_threads, n_each = 4, 2_000

    def worker(k: int) -> None:
        for i in range(n_each):
            feed.append(t=float(k * n_each + i))

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert feed.size() == n_threads * n_each
    assert feed.version() == n_threads * n_each
    vals = feed.series("t")
    assert len(np.unique(vals)) == n_threads * n_each       # no torn/lost rows
