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
