import pytest

from ...bucket import get_client


def test_client_integration():
    client = get_client()

    assert len(client.models) > 0
    assert len(client.gridcells) > 0
    precip_files = client.get_precip_files()
    assert len(precip_files) > 0
    precip_files = client.get_precip_files(gridcell="R17")
    assert len(precip_files) > 0
    precip_files = client.get_precip_files(client.models[0])
    assert len(precip_files) > 0

    m = client.models[0]
    assert "datetime" in str(client.get_datetime_file(m))
    assert "start" in client.get_TNC_siminfo(m)
    assert "start" in client.get_TNC_siminfo(m)  # check cache
    assert "precip" in client.get_json(precip_files[0])

    with pytest.raises(ValueError):
        client.get_datetime_file("not_found")
    with pytest.raises(ValueError):
        client.get_json("not_found.json")

    with pytest.raises(ValueError):
        client.get_json("not_json.csv")

    with pytest.raises(ValueError):
        client.get_TNC_siminfo("not a model")
