import traceback as tb
from datetime import datetime
from typing import Any, cast

import numpy
import pandas
from HSP2.IWATER import iwater
from HSP2.PWATER import pwater
from numba import types
from numba.typed import Dict
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from . import wwhm


class SimInfo(TypedDict):
    start: datetime
    stop: datetime
    delt: int
    steps: int
    units: int


InputTS = dict[str, numpy.ndarray]


siminfo_validator = TypeAdapter(SimInfo)


def get_TNC_siminfo(start: datetime, end: datetime) -> SimInfo:
    delt: int = 60
    siminfo = siminfo_validator.validate_python(
        {
            "start": start,
            "stop": end,
            "delt": delt,
            "steps": int((end - start).days * (1440 / delt)),
            "units": 1,
        }
    )

    return siminfo


def build_numba_ts(data):
    ts = Dict.empty(key_type=types.unicode_type, value_type=types.float64[:])
    ts.update(data)

    return ts


def build_uci(params: dict) -> dict:
    return {"PARAMETERS": params}


def run_hspf(*, siminfo: SimInfo, uci, ts, func=iwater, precision=4):
    """
    ts: mutable numba.typed.Dict
    """
    errors, msgs = func(None, siminfo=siminfo, uci=uci, ts=ts)
    zeros = numpy.zeros(siminfo["steps"])
    dix = pandas.date_range(
        start=pandas.Timestamp("1970-01-01 00:00:00"),
        end=siminfo["stop"],
        freq="1h",
    )
    ixi = cast(int, dix.get_loc(siminfo["start"]))
    ixe = ixi + siminfo["steps"]
    results = {
        "ix": numpy.arange(ixi, ixe, dtype=numpy.uint32),
        "SURO": (zeros + ts.get("SURO", zeros).round(precision)).astype(numpy.float32),
        "AGWO": (zeros + ts.get("AGWO", zeros).round(precision)).astype(numpy.float32),
        "IFWO": (zeros + ts.get("IFWO", zeros).round(precision)).astype(numpy.float32),
    }

    return results, errors, msgs


def run_hru(ts, siminfo: SimInfo, hru: str) -> dict:
    """
    ts: mutable numba.typed.Dict
    """
    params = wwhm.wwhm_hru_params()[hru]

    uci = build_uci(params)
    func = pwater if hru[-2:-1] != "5" else iwater
    try:
        results, errors, msgs = run_hspf(siminfo=siminfo, uci=uci, ts=ts, func=func)
        exception = None

    except Exception as e:  # pragma: no cover
        results, errors, msgs = None, None, None
        exception = "".join(tb.format_exception(None, e, e.__traceback__))

    return {
        "hru": hru,
        "results": results,
        "errors": errors,
        "messages": msgs,
        "exception": exception,
    }


def run_hrus(
    input_ts: InputTS, siminfo, hrus: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    if hrus is None:  # pragma: no cover
        hrus = list(wwhm.wwhm_hru_params().keys())

    all_hru_results = {}

    for hru in hrus:
        ts = build_numba_ts(input_ts)  # this must be built for each hru; it's mutable
        all_hru_results[hru] = run_hru(ts, siminfo, hru)
    return all_hru_results
