import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from time import perf_counter

import numpy
import orjson
import pandas
from tqdm import tqdm

from . import convert, pet, wwhm
from .bucket import ClientFactory, ClimateTSBucket, get_client
from .hspf_runner import InputTS, SimInfo, get_TNC_siminfo, run_hrus


def build_petinp(siminfo, data):  # pragma: no cover
    start = siminfo["start"]
    end = siminfo["stop"]

    daterange = pandas.date_range(start=start, end=end, freq="1D")
    petinp = (
        pandas.DataFrame({"petinp": data["petinp"].get("data", [])[: len(daterange)]})
        .assign(datetime=daterange)
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
        .to_numpy()
        .flatten()
        * convert.MM_TO_INCH  # phew, this result is in/hr
    )

    return petinp


def build_ts(data, siminfo):
    precip = numpy.array(data["prec"].get("data")) * convert.MM_TO_INCH
    if "petinp" in data:  # pragma: no cover
        petinp = build_petinp(siminfo, data)
    else:
        petinp = pet.build_evap_ts(siminfo).to_numpy()

    input_ts: InputTS = {"PREC": precip, "PETINP": petinp}

    return input_ts


def run_one_datafile(data, siminfo, hrus: list[str] | None = None):
    input_ts: InputTS = build_ts(data, siminfo)
    return run_hrus(input_ts, siminfo, hrus)


def build_results_table_for_one_hru(res, run_id, siminfo, metadata) -> pandas.DataFrame:
    table = pandas.DataFrame(res)
    table[["SURO", "AGWO", "IFWO"]] *= convert.INCH_TO_MM
    runoff_units = "depth (mm)"

    zeros = numpy.zeros(siminfo["steps"])
    table["id"] = pandas.Series(zeros, dtype="category").cat.rename_categories(
        {0: run_id}
    )

    table["start_time"] = pandas.Series(zeros, dtype="category").cat.rename_categories(
        {0: siminfo["start"].isoformat()}
    )

    table["end_time"] = pandas.Series(zeros, dtype="category").cat.rename_categories(
        {0: siminfo["stop"].isoformat()}
    )

    metadata.update(
        {
            "start_time": siminfo["start"].isoformat(),
            "end_time": siminfo["stop"].isoformat(),
            "steps": str(siminfo["steps"]),
            "runoff_units": runoff_units,
        }
    )

    meta_str = orjson.dumps(metadata).decode()
    table["meta"] = pandas.Series(
        numpy.zeros(siminfo["steps"]), dtype="category"
    ).cat.rename_categories({0: meta_str})

    return table


def send_results_for_one_hru(
    *, hru: str, data: dict, siminfo: SimInfo, client=None
) -> tuple[str, str]:
    if client is None:  # pragma: no cover
        client = get_client()
    model, gridcell = siminfo["model"], siminfo["gridcell"]
    fname = f"{gridcell}-{hru}"
    id_ = model + f"/results/{fname.replace('-', '/')}"
    ext = "meta" if not data["exception"] else "error"
    if ext == "meta":  # pragma: no cover
        client.rm_blob(model + f"/meta/{fname}.error")

    res = data.pop("results", None)

    resname = ""
    if res:  # pragma: no branch
        metadata = {
            "model": str(model),
            "rc": str(gridcell),
            "hru": str(hru),
        }
        table = build_results_table_for_one_hru(
            res, id_, siminfo=siminfo, metadata=metadata
        )

        b = io.BytesIO()
        # compression makes no difference on uploaded size,
        # but measurably slows down the process
        table.to_parquet(b, index=False, compression=None)
        b.seek(0)

        parquet_path = id_ + ".parquet"
        resname = client.send_parquet(parquet_path, b.read())

    meta_path = model + f"/meta/{fname}.{ext}"
    meta_name = client.send_json(meta_path, data)

    return resname, meta_name


def send_results_for_one_inputfile(
    *, input_file, results, siminfo, max_workers=None, client=None
) -> tuple[str, float, list[tuple[str, str]]]:
    start = perf_counter()
    if client is None:  # pragma: no cover
        client = get_client()

    completed = []
    with ThreadPoolExecutor(max_workers) as executor:
        futures = [
            executor.submit(
                send_results_for_one_hru,
                hru=hru,
                data=deepcopy(data),
                siminfo=siminfo,
                client=client,
            )
            for hru, data in results.items()
        ]

        for future in as_completed(futures):
            success = future.result()
            completed.append(success)
    end = perf_counter()
    elapsed = end - start
    return input_file, elapsed, completed


def get_data_and_siminfo(input_file: str, client: ClimateTSBucket | None = None):
    if client is None:  # pragma: no cover
        client = get_client()
    data = client.get_json(input_file)
    start_time = pandas.to_datetime(data["start_time"])
    end_time = pandas.to_datetime(data["end_time"]) + pandas.Timedelta("23h")
    model, _, input_file_name = input_file.split("/")
    gridcell = input_file_name.split("-")[0]
    siminfo = get_TNC_siminfo(start_time, end_time, model, gridcell)

    return data, siminfo


def run_and_send_results_for_one_inputfile(
    *,
    input_file,
    max_workers=None,
    hrus: list[str] | None = None,
    client_factory: ClientFactory | None = None,
):
    start = perf_counter()
    if client_factory is None:  # pragma: no cover
        client_factory = get_client

    client = client_factory()

    data, siminfo = get_data_and_siminfo(input_file, client=client)

    start = perf_counter()
    results = run_one_datafile(data, siminfo, hrus=hrus)
    end = perf_counter()

    _, send_time, completed = send_results_for_one_inputfile(
        input_file=input_file,
        results=results,
        siminfo=siminfo,
        max_workers=max_workers,
        client=client,
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
    if not valid_models:
        return []

    args: list[dict[str, str]] = [
        {"input_file": input_file}
        for input_file in sorted(
            client.get_precip_files(model=list(valid_models), gridcell=gridcell)
        )
    ]

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
            client_factory=None,
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
    run("HIS", "R18C42", ["hru250"])
