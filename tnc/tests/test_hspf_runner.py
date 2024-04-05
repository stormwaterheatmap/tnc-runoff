from ..hspf_runner import build_numba_ts, run_hrus


def test_run_hrus(regression_input_ts, regression_siminfo):
    ts = build_numba_ts(regression_input_ts)
    res = run_hrus(ts, regression_siminfo)
    assert len(res) == 30

    for hru, data in res.items():
        assert data["exception"] is None, data["exception"]
        suro_result = data["results"]["SURO"]
        assert suro_result.sum() > 0.0, hru
