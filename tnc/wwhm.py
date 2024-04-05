from datetime import datetime
from functools import cache

import pandas

from .config import settings

_VALID_SOIL_TYPES = {0: "A/B", 1: "C", 2: "D"}
_VALID_LANDUSES = {0: "forest", 1: "pasture", 2: "lawn", 5: "impervious"}
_VALID_SLOPE_CLASSES = {0: "flat", 1: "mod", 2: "steep"}


@cache
def get_wwhm_params_per():
    wwhm_params_per = (
        pandas.read_csv(settings.PERLND, index_col=0)
        .reset_index()
        .assign(index=lambda df: df["index"].str.replace(" ", "").str.strip())
    )

    wwhm_params_per[["__soil", "__use", "__slope"]] = wwhm_params_per[
        "index"
    ].str.split(",", expand=True)

    wwhm_params_per["hru"] = (
        "hru"
        + wwhm_params_per["__soil"]
        .str.lower()
        .replace({str(v).lower(): str(k) for k, v in _VALID_SOIL_TYPES.items()})
        + wwhm_params_per["__use"]
        .str.lower()
        .replace({str(v).lower(): str(k) for k, v in _VALID_LANDUSES.items()})
        + wwhm_params_per["__slope"]
        .str.lower()
        .replace({str(v).lower(): str(k) for k, v in _VALID_SLOPE_CLASSES.items()})
    )

    return (
        wwhm_params_per.drop(
            columns=[c for c in wwhm_params_per.columns if "__" in c or "index" in c]
        )
        .set_index("hru")
        .sort_index()
    )


@cache
def get_wwhm_params_imp():
    wwhm_params_imp = (
        pandas.read_csv(settings.IMPLND, index_col=0)
        .reset_index()
        .assign(index=lambda df: df["index"].str.replace(" ", "").str.strip())
    )

    wwhm_params_imp[["__use", "__slope"]] = wwhm_params_imp["index"].str.split(
        ",", expand=True
    )

    wwhm_params_imp["hru"] = (
        "hru2"
        + wwhm_params_imp["__use"]
        .str.lower()
        .replace({str(v).lower(): str(k) for k, v in _VALID_LANDUSES.items()})
        + wwhm_params_imp["__slope"]
        .str.lower()
        .replace({str(v).lower(): str(k) for k, v in _VALID_SLOPE_CLASSES.items()})
    )
    return (
        wwhm_params_imp.drop(
            columns=[c for c in wwhm_params_imp.columns if "__" in c or "index" in c]
        )
        .set_index("hru")
        .sort_index()
    )


@cache
def get_temp_evap(start, end):
    et_factor = 1

    nyears = (end.year + 1) - (start.year - 1) + 1

    _wwhm_evap = (
        pandas.read_csv(settings.TEMP_EVAP, sep=r"\s+", parse_dates=["Date"])
        .assign(Month=lambda df: df["Date"].dt.month)
        .groupby("Month")[["1-in"]]
        .mean()
    )

    wwhm_evap = (
        pandas.concat([_wwhm_evap] * nyears, ignore_index=True)[["1-in"]]
        .assign(
            datetime=pandas.date_range(
                start=datetime(start.year - 1, 1, 1), periods=12 * (nyears), freq="ME"
            )
        )
        .set_index("datetime")
        .resample("1D")
        .bfill()  # Convert from monthly to daily frequency
        .resample("1h")
        .ffill()  # Convert from daily to hourly frequency
        .loc[start:end]
        .to_numpy()
        .flatten()
        / 24
        * et_factor  # Convert from units of in/day to in/hr and apply et factor
    )

    return wwhm_evap


@cache
def wwhm_hru_params() -> dict[str, dict[str, int | float]]:
    wwhm_params_per = get_wwhm_params_per()
    wwhm_params_imp = get_wwhm_params_imp()

    hru_params = {}

    for df in [wwhm_params_imp, wwhm_params_per]:
        hrus = df.index
        for hru in hrus:
            hru_params[hru] = df.loc[hru].to_dict()

    return hru_params
