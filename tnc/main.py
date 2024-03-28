import math
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from time import perf_counter

from .bucket import get_client
from .hspf_runner import SimInfo, get_input_ts, run_hrus


def run_one_inputfile(input_file, siminfo, client=None):
    if client is None:
        client = get_client()
    data = client.get_json(input_file)
    input_ts = get_input_ts(data, siminfo)

    return run_hrus(input_ts, siminfo)


def send_json(client, path, data):
    client.send_json(path, data)
    return path


def send_results_for_one_inputfile(input_file, results, max_workers=None, client=None):
    start = perf_counter()
    if client is None:
        client = get_client()
    args = []
    for hru, data in results.items():
        ext = "json" if not data["exception"] else "error"
        path = "/".join(input_file.split("/")[:-1]) + f"/results/{hru}.{ext}"
        args.append((path, data))

    with ThreadPoolExecutor(max_workers) as executor:
        _ = [executor.submit(send_json, client, path, data) for path, data in args]
    end = perf_counter()
    elapsed = end - start
    return input_file, elapsed


def run_and_send_results_for_one_inputfile(
    input_file, siminfo, max_workers=None, client=None
):
    start = perf_counter()
    if client is None:
        client = get_client()

    start = perf_counter()
    results = run_one_inputfile(input_file, siminfo, client)
    end = perf_counter()

    _, send_time = send_results_for_one_inputfile(
        input_file, results, max_workers=max_workers, client=client
    )

    elapsed = end - start
    return input_file, elapsed, send_time


def gather_args(
    model: str | list[str] | None = None,
    gridcell: str | list[str] | None = None,
) -> list[dict[str, str | SimInfo]]:
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


def main(
    model: str | list[str] | None = None,
    gridcell: str | list[str] | None = None,
):
    raise DeprecationWarning("use cli")
    args = gather_args(model, gridcell) * 2

    N_WORKERS = max(math.ceil((os.cpu_count() or 1) * 0.5), 2)

    timings = []

    start = perf_counter()
    with ProcessPoolExecutor(N_WORKERS) as exe:
        print(f"starting {N_WORKERS} parallel workers to do {len(args)} jobs...")
        # submit tasks and collect futures
        futures = [
            exe.submit(
                run_and_send_results_for_one_inputfile,
                **i,
                max_workers=N_WORKERS,
            )
            for i in args
        ]

        # process task results as they are available
        for future in as_completed(futures):
            result, seconds, send_time = future.result()

            elapsed = f"{seconds: 0.3f}"
            print(
                f"{result} computed in {elapsed} seconds; "
                f"uploaded in {send_time:0.2f} seconds"
            )
            timings.append(seconds + send_time)

    end_all = perf_counter()
    tot_time = end_all - start
    time_per_cell = tot_time / len(args)

    avg_time = sum(timings) / len(timings)

    print("\n")
    print(f"full job [N={len(args)}] took {tot_time: 0.1f} seconds (wall)")
    print(f"avg gridcell took {avg_time: 0.2f} seconds (per core)")
    print(f"each gridcell took {time_per_cell: 0.3f} seconds (wall)")
    print(f"avg hru took {avg_time / 30: 0.3f} seconds (per core)")
    print(f"each hru took {time_per_cell / 30: 0.3f} seconds (wall)")


if __name__ == "__main__":
    main()
