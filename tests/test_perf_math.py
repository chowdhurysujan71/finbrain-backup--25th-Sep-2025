from finbrain.ops import perf

def test_p95_nearest_rank():
    for _ in range(19):
        perf.record(100.0)
    perf.record(1000.0)
    assert perf.count() == 20
    val = perf.p95()
    assert val is not None and val >= 1000.0 - 1e-6