import pytest
from typer.testing import CliRunner

from ..cli import create_app
from ..main import get_client

runner = CliRunner()


def client_factory():
    c = get_client()

    def overwrite_send(destination_filename, data):  # pragma: no cover
        return destination_filename

    c.send_json = overwrite_send
    c.send_parquet = overwrite_send

    return c


@pytest.fixture(scope="module")
def app():
    return create_app(client_factory=client_factory)


def test_app_find(app):
    result = runner.invoke(app, ["find", "-g", "R18"])
    assert result.exit_code == 0
    assert "WRF-NARR_HIS" in result.stdout
    print(result.stdout)


def test_app_run(app):
    result = runner.invoke(app, ["run", "-m", "HIS", "-g", "R18C41", "-h", "hru200"])
    assert result.exit_code == 0, result.stdout
    print(result.stdout)


def test_app_run_failed(app):
    result = runner.invoke(app, ["run", "-m", "HIS", "-g", "R18C41", "-h", "200"])
    assert result.exit_code == 1, result.stdout
    print(result.stdout)
