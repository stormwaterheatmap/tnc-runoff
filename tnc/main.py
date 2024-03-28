from concurrent.futures import ProcessPoolExecutor, as_completed

from .bucket import get_client
from .hspf_runner import get_input_ts, run_hrus


def run_one_inputfile(input_file, siminfo, client=None):
    if client is None:
        client = get_client()
    data = client.get_json(input_file)
    input_ts = get_input_ts(data, siminfo)

    return run_hrus(input_ts, siminfo)


def send_results_for_one_inputfile(input_file, results, client=None):
    if client is None:
        client = get_client()
    for hru, data in results.items():
        ext = "json" if not data["exception"] else "error"
        path = "/".join(input_file.split("/")[:-1]) + f"/results/{hru}.{ext}"
        client.send_json(path, data)


def run_and_send_results_for_one_inputfile(input_file, siminfo, client=None):
    if client is None:
        client = get_client()
    results = run_one_inputfile(input_file, siminfo, client)
    send_results_for_one_inputfile(input_file, results, client)
    return input_file


def gather_args(models=None):
    args = []
    client = get_client()
    if models is None:
        models = client.models
    for model in models:
        siminfo = client.get_TNC_siminfo(model)
        gridcells_precip = client.get_precip_files(model)
        for input_file in sorted(gridcells_precip):
            args.append((input_file, siminfo))
    return args


def main():
    from time import perf_counter

    args = gather_args()

    timings = []
    with ProcessPoolExecutor(10) as exe:
        start = perf_counter()
        # submit tasks and collect futures
        futures = [exe.submit(run_and_send_results_for_one_inputfile, *i) for i in args]

        # process task results as they are available
        for future in as_completed(futures):
            end = perf_counter()
            result = future.result()

            elapsed = f"{end - start: 0.3f}"
            print(f"{result} completed in {elapsed} seconds")
            timings.append(end - start)

    end_all = perf_counter()
    tot_time = end_all - start
    time_per_cell = tot_time / len(args)

    avg_time = sum(timings) / len(timings)

    print(f"\navg iteration took {avg_time: 0.3f} seconds (process/user)")
    print(f"full job took {tot_time: 0.3f} seconds (wall)")
    print(f"job took {time_per_cell: 0.3f} seconds per gridcell (wall)")
    print(f"job took {time_per_cell / 30: 0.3f} seconds per hru (wall)")


if __name__ == "__main__":
    main()
