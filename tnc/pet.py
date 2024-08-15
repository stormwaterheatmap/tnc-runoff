from functools import lru_cache

import pandas

from . import convert
from .config import settings
from .hspf_runner import SimInfo


@lru_cache
def load_evap():
    evap = (
        pandas.read_csv(settings.PET_MM_DAILY, parse_dates=["date_arb_year"])
        .iloc[:, 1:]
        .assign(month=lambda df: df.date_arb_year.dt.month.astype(str))
        .assign(day=lambda df: df.date_arb_year.dt.day.astype(str))
        .drop(columns=["date_arb_year"])
    )

    return evap


def build_evap_ts(siminfo: SimInfo):
    evap = load_evap()[["month", "day", siminfo["gridcell"]]]
    evap_ts = (
        pandas.date_range(siminfo["start"], siminfo["stop"], freq="h")
        .to_frame(name="datetime")
        .assign(month=lambda df: df.datetime.dt.month.astype(str))
        .assign(day=lambda df: df.datetime.dt.day.astype(str))
        .merge(evap, how="left", on=["month", "day"])
        .set_index("datetime")
        .loc[:, siminfo["gridcell"]]
        .div(24)
        .mul(convert.MM_TO_INCH)
    )

    return evap_ts
