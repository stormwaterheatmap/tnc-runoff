from ..hspf_runner import get_input_ts, run_hrus


def test_run_hrus(regression_input_ts, regression_siminfo):
    ts = get_input_ts(regression_input_ts)

    res = run_hrus(ts, regression_siminfo)

    assert len(res) == 30
