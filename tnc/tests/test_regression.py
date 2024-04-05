import pytest

from ..hspf_runner import build_numba_ts, run_hru


@pytest.mark.parametrize("hru", ["hru010", "hru250"])
def test_regression(regression_input_ts, regression_siminfo, regression_result_ts, hru):
    ts = build_numba_ts(regression_input_ts)

    _ = run_hru(ts, regression_siminfo, hru)

    for k, v in ts.items():
        ts[k] = v[: regression_siminfo["steps"]]

    exp = regression_result_ts[hru]

    assert ts["SURO"].sum() > 0

    for k in set(ts.keys()).intersection(exp.keys()):
        check = (ts[k].round(4) - exp[k]).max()
        assert check < 1e-3, (k, check)
