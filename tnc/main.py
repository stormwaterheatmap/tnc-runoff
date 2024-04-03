from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import numpy

from . import convert, wwhm
from .bucket import ClimateTSBucket, get_client
from .hspf_runner import InputTS, SimInfo, run_hrus


def run_one_inputfile(
    input_file,
    siminfo,
    hrus: list[str] | None = None,
    client: ClimateTSBucket | None = None,
):
    if client is None:  # pragma: no cover
        client = get_client()
    data = client.get_json(input_file)
    input_ts: InputTS = {
        "PREC": numpy.array(data["precip"]) * convert.MM_TO_INCH,
        # TODO: use petinp from bucket
        "PETINP": wwhm.get_temp_evap(siminfo["start"], siminfo["stop"]),
    }

    return run_hrus(input_ts, siminfo, hrus)


def send_results_for_one_inputfile(input_file, results, max_workers=None, client=None):
    start = perf_counter()
    if client is None:  # pragma: no cover
        client = get_client()
    args = []
    for hru, data in results.items():
        ext = "json" if not data["exception"] else "error"
        path = "/".join(input_file.split("/")[:-1]) + f"/results/{hru}.{ext}"
        args.append((path, data))

    with ThreadPoolExecutor(max_workers) as executor:
        _ = [executor.submit(client.send_json, path, data) for path, data in args]
    end = perf_counter()
    elapsed = end - start
    return input_file, elapsed


def run_and_send_results_for_one_inputfile(
    *,
    input_file,
    siminfo,
    max_workers=None,
    hrus: list[str] | None = None,
    client: ClimateTSBucket | None = None,
):
    start = perf_counter()
    if client is None:  # pragma: no cover
        client = get_client()

    start = perf_counter()
    results = run_one_inputfile(input_file, siminfo, hrus=hrus, client=client)
    end = perf_counter()

    _, send_time = send_results_for_one_inputfile(
        input_file, results, max_workers=max_workers, client=client
    )

    run_time = end - start
    return input_file, run_time, send_time


def gather_args(
    model: str | list[str] | None = None,
    gridcell: str | list[str] | None = None,
    client: ClimateTSBucket | None = None,
) -> list[dict[str, str | SimInfo]]:
    if client is None:  # pragma: no cover
        client = get_client()
    if model is None:
        model = client.models
    if isinstance(model, str):
        model = [model]

    valid_models = {m for m in client.models for substr in model if substr in m}
    args: list[dict[str, str | SimInfo]] = []
    for model in valid_models:
        siminfo = client.get_TNC_siminfo(model)
        gridcells_precip = client.get_precip_files(model=model, gridcell=gridcell)
        for input_file in sorted(gridcells_precip):
            args.append({"input_file": input_file, "siminfo": siminfo})
    return args
