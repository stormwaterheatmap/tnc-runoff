from datetime import datetime
from pathlib import Path

import numpy
import pandas
import pytest

from ..hspf_runner import get_TNC_siminfo

regression_data = Path(__file__).parent / "regression_data"


@pytest.fixture(scope="module")
def regression_input_ts():
    return {
        k: numpy.array(v)
        for k, v in pandas.read_csv(regression_data / "test_inputs.csv")
        .to_dict(orient="list")
        .items()
    }


@pytest.fixture(scope="module")
def regression_result_ts():
    return {
        "hru010": {
            k: numpy.array(v)
            for k, v in pandas.read_csv(regression_data / "hru010_results.csv")
            .to_dict(orient="list")
            .items()
        },
        "hru250": {
            k: numpy.array(v)
            for k, v in pandas.read_csv(regression_data / "hru250_results.csv")
            .to_dict(orient="list")
            .items()
        },
    }


@pytest.fixture(scope="module")
def regression_siminfo():
    return get_TNC_siminfo(
        datetime(1980, 1, 1), datetime(1981, 1, 1), model="m", gridcell="R18C42"
    )
