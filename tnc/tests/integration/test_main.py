import pandas
import pytest

from ...hspf_runner import get_TNC_siminfo
from ...main import (
    build_ts,
    gather_args,
    get_client,
    run_and_send_results_for_one_inputfile,
)


@pytest.fixture(scope="module")
def client():
    c = get_client()

    def overwrite_send(destination_filename, data):
        return destination_filename

    c.send_json = overwrite_send

    return c


@pytest.mark.parametrize("model", [None, "HIS", ["HIS"], "--missing--"])
@pytest.mark.parametrize("gridcell", [None, "R17", ["C42"], "--missing--"])
def test_gather_args_integration(model, gridcell, client):
    args = gather_args(model, gridcell, client)

    if model == "--missing--" or gridcell == "--missing--":
        assert len(args) == 0
    else:
        assert len(args) > 0


def test_run_and_send_integration(client):
    kwargs = gather_args(client.models[0], client.gridcells[0], client).pop()

    run_and_send_results_for_one_inputfile(
        **kwargs, max_workers=None, hrus=["hru010", "hru250"], client=client
    )


@pytest.mark.parametrize("gridcell", ["R18C42", "R17C42"])
def test_get_ts_from_client_integration(client, gridcell):
    input_file = client.get_precip_files("HIS", gridcell).pop()

    data = client.get_json(input_file)
    start = pandas.to_datetime(data["start_time"])
    stop = pandas.to_datetime(data["end_time"]) + pandas.Timedelta("23h")
    siminfo = get_TNC_siminfo(start, stop)

    ts = build_ts(data, siminfo)

    v1, v2 = ts.values()
    assert len(v1) == len(v2), input_file
