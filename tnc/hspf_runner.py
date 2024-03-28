import traceback as tb
from datetime import datetime

import numpy
import pandas
from HSP2.IWATER import iwater
from HSP2.PWATER import pwater
from numba import types
from numba.typed import Dict
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from . import convert, wwhm


class SimInfo(TypedDict):
    start: datetime
    stop: datetime
    delt: int
    steps: int
    units: int


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


def get_input_ts(data, siminfo):
    return {
        "PREC": numpy.array(data["precip"]) * convert.MM_TO_INCH,
        "PETINP": wwhm.get_bs_evap(siminfo["start"], siminfo["stop"]),
    }


def build_uci(params: pandas.Series) -> dict:
    return {"PARAMETERS": params.to_dict()}


def build_ts(
    steps: int, input_ts: dict[str, numpy.ndarray], hru: str, params: pandas.Series
):
    tsf = Dict.empty(key_type=types.unicode_type, value_type=types.float64[:])

    ui_ts_params = ["NSUR", "RETSC"]
    if hru[-2:-1] != "5":  # 5 means impervious, else means pervious
        ui_ts_params = [
            "AGWRC",
            "CEPSC",
            "DEEPFR",
            "INFILT",
            "INTFW",
            "IRC",
            "KVARY",
            "LZETP",
            "LZSN",
            "NSUR",
            "UZSN",
        ]
    tsf.update(input_ts)

    for param in ui_ts_params:
        tsf[param] = numpy.full(steps, params[param])

    return tsf


def run_hspf(*, siminfo, uci, ts, func=iwater, precision=4):
    errors, msgs = func(None, siminfo=siminfo, uci=uci, ts=ts)
    zeros = numpy.zeros(siminfo["steps"])
    results = {
        "SURO": zeros + ts.get("SURO", zeros).round(precision),
        "AGWO": zeros + ts.get("AGWO", zeros).round(precision),
        "INTFW": zeros + ts.get("INTFW", zeros).round(precision),
    }

    return results, errors, msgs


def run_hrus(input_ts, siminfo):
    all_hru_results = {}

    wwhm_params_per = wwhm.get_wwhm_params_per()
    wwhm_params_imp = wwhm.get_wwhm_params_imp()

    for df in [wwhm_params_imp, wwhm_params_per]:
        hrus = df.index
        for hru in hrus:
            param_series = df.loc[hru]

            uci = build_uci(param_series)
            ts = build_ts(siminfo["steps"], input_ts, hru, param_series)
            func = pwater if hru[-2:-1] != "5" else iwater
            try:
                results, errors, msgs = run_hspf(
                    siminfo=siminfo, uci=uci, ts=ts, func=func
                )
                exception = None

            except Exception as e:
                results, errors, msgs = None, None, None
                exception = "".join(tb.format_exception(None, e, e.__traceback__))

            all_hru_results[hru] = {
                "results": results,
                "errors": errors,
                "messages": msgs,
                "exception": exception,
            }

    return all_hru_results
