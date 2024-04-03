import pytest

from ...main import gather_args, get_client, run_and_send_results_for_one_inputfile


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
        **kwargs, max_workers=None, hrus=None, client=client
    )
