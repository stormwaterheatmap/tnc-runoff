import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

import numpy
import pandas
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from . import convert, wwhm
from .bucket import ClimateTSBucket, get_client
from .hspf_runner import InputTS, get_TNC_siminfo, run_hrus


def build_petinp(siminfo, data):
    start = siminfo["start"]
    end = siminfo["stop"]

    petinp = (
        pandas.DataFrame({"petinp": data["petinp"].get("data", [])})
        .assign(datetime=pandas.date_range(start=start, end=end, freq="1D"))
        .set_index("datetime")
        .reindex(
            pandas.date_range(
                start=start,
                end=end,
                freq="1h",
            ),
            method="ffill",
        )  # aah! this result is hourly freq but in mm/day!
        .div(24)  # aah! this result is mm/hr
        .div(25.4)  # phew, this result is in/hr
        .to_numpy()
        .flatten()
    )

    return petinp


def build_ts(
    data,
    siminfo,
):
    precip = numpy.array(data["prec"].get("data")) * convert.MM_TO_INCH
    if "petinp" in data:
        petinp = build_petinp(siminfo, data)
    else:
        petinp = wwhm.get_temp_evap(siminfo["start"], siminfo["stop"])

    input_ts: InputTS = {"PREC": precip, "PETINP": petinp}

    return input_ts


def run_one_inputfile(
    input_file,
    hrus: list[str] | None = None,
    client: ClimateTSBucket | None = None,
):
    if client is None:  # pragma: no cover
        client = get_client()
    data = client.get_json(input_file)
    start = pandas.to_datetime(data["start_time"])
    stop = pandas.to_datetime(data["end_time"]) + pandas.Timedelta("23h")
    siminfo = get_TNC_siminfo(start, stop)
    input_ts: InputTS = build_ts(data, siminfo)

    return run_hrus(input_ts, siminfo, hrus)


def send_results_for_one_hru(
    input_file_path: str, hru: str, data: dict, client=None
) -> tuple[str, str]:
    if client is None:  # pragma: no cover
        client = get_client()
    base_path = "/".join(input_file_path.split("/")[:-1])
    ext = "meta" if not data["exception"] else "error"
    if ext == "meta":  # pragma: no cover
        client.rm_blob(base_path + f"/results/{hru}.error")

    res = data.pop("results", None)
    resname = ""
    if res:  # pragma: no branch
        table = pa.table(res)
        b = io.BytesIO()
        pq.write_table(table, b)
        b.seek(0)

        parquet_path = base_path + f"/results/{hru}.parquet"
        resname = client.send_parquet(parquet_path, b.read())

    meta_path = base_path + f"/results/{hru}.{ext}"
    meta_name = client.send_json(meta_path, data)

    return resname, meta_name


def send_results_for_one_inputfile(
    input_file, results, max_workers=None, client=None
) -> tuple[str, float, list[tuple[str, str]]]:
    start = perf_counter()
    if client is None:  # pragma: no cover
        client = get_client()

    completed = []
    with ThreadPoolExecutor(max_workers) as executor:
        futures = [
            executor.submit(
                send_results_for_one_hru, input_file, hru, data, client=client
            )
            for hru, data in results.items()
        ]

        for future in as_completed(futures):
            success = future.result()
            completed.append(success)
    end = perf_counter()
    elapsed = end - start
    return input_file, elapsed, completed


def run_and_send_results_for_one_inputfile(
    *,
    input_file,
    max_workers=None,
    hrus: list[str] | None = None,
    client: ClimateTSBucket | None = None,
):
    start = perf_counter()
    if client is None:  # pragma: no cover
        client = get_client()

    start = perf_counter()
    results = run_one_inputfile(input_file, hrus=hrus, client=client)
    end = perf_counter()

    _, send_time, completed = send_results_for_one_inputfile(
        input_file, results, max_workers=max_workers, client=client
    )

    run_time = end - start
    return input_file, run_time, send_time, completed


def gather_args(
    model: str | list[str] | None = None,
    gridcell: str | list[str] | None = None,
    client: ClimateTSBucket | None = None,
) -> list[dict[str, str]]:
    if client is None:  # pragma: no cover
        client = get_client()
    if model is None:
        model = client.models
    if isinstance(model, str):
        model = [model]

    valid_models = {m for m in client.models for substr in model if substr in m}
    args: list[dict[str, str]] = []
    for model in valid_models:
        gridcells_precip = client.get_precip_files(model=model, gridcell=gridcell)
        for input_file in sorted(gridcells_precip):
            args.append({"input_file": input_file})
    return args


def run(
    model: str | list[str] | None = None,
    gridcell: str | list[str] | None = None,
    hrus: list[str] | None = None,
):  # pragma: no cover
    """
    Run the HSPF IWater and PWater routines for the selected Precip & PET files
    and upload the result to Google Cloud Storage.

    EXAMPLES:
    >>> tnc run

    >>> tnc run -m HIS -m NARR -g R17 -g C42

    >>> tnc run -m HIS -g R17C42 -h hru250
    """
    args = gather_args(model, gridcell)
    if hrus is None:
        hrus = list(wwhm.wwhm_hru_params().keys())
    nargs = len(args) * len(hrus)

    timings = []
    start = perf_counter()

    print(f"processing {len(args)} input files...")

    for kwargs in tqdm(args):
        _, seconds, send_time, completed = run_and_send_results_for_one_inputfile(
            **kwargs,
            hrus=hrus,
            max_workers=None,
            client=None,
        )
        timings.append((seconds, send_time))

    end_all = perf_counter()

    tot_time = end_all - start
    time_per_cell = tot_time / len(args)
    avg_time = sum([a + b for a, b in timings]) / len(timings)
    avg_compute_time = sum([a for a, _ in timings]) / len(timings)
    avg_send_time = sum([b for _, b in timings]) / len(timings)

    print(f"full job [N={nargs}] took {tot_time: 0.1f} seconds (wall)")
    print(f"avg gridcell took {avg_time: 0.2f} seconds (per core)")
    print(f"each gridcell took {time_per_cell: 0.3f} seconds (wall)")
    print(f"avg hru took {avg_time / len(hrus): 0.3f} seconds (per core)")
    print(f"each hru took {time_per_cell / len(hrus): 0.3f} seconds (wall)")
    print(f"avg gridcell compute time {avg_compute_time: 0.3f} seconds (wall)")
    print(f"avg gridcell upload time {avg_send_time: 0.3f} seconds (wall)")
    print([(round(a, 3), round(b, 3)) for a, b in timings])


if __name__ == "__main__":  # pragma: no cover
    run()
