import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from time import perf_counter
from typing import Optional

import typer
from tqdm import tqdm
from typing_extensions import Annotated

from . import main, wwhm
from .bucket import get_client

N_WORKERS = max(math.ceil((os.cpu_count() or 1) * 0.5), 2)

app = typer.Typer(rich_markup_mode="rich", add_completion=False, no_args_is_help=True)

Model = Annotated[
    Optional[list[str]],
    typer.Option(
        "-m",
        "--model",
        help=" name of the model to process.",
    ),
]

GridCell = Annotated[
    Optional[list[str]],
    typer.Option(
        "-g",
        "--gridcell",
        help="name of the gridcell to process. "
        "Defaults to all gridcells in the bucket.",
    ),
]

HRUs = Annotated[
    Optional[list[str]],
    typer.Option(
        "-h",
        "--hru",
        help="name of the HRU to process. "
        "Defaults to all 30 HRUs in the input files.",
    ),
]

NCores = Annotated[
    int,
    typer.Option(
        "-n",
        "--n-cores",
        help="number of cores to use in parallel. "
        f"Default 'None' uses {N_WORKERS} cores.",
    ),
]

DryRun = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="collects the models that would be run and displays them.",
    ),
]


@app.command()
def find(model: Model = None, gridcell: GridCell = None):
    args = main.gather_args(model, gridcell)
    nargs = len(args)

    if nargs > 0:
        typer.echo(f"found {nargs} files...")
    for dct in args:
        typer.echo(dct["input_file"])


@app.command()
def run(
    model: Model,
    gridcell: GridCell = None,
    hrus: HRUs = None,
    ncores: NCores = N_WORKERS,
):
    """
    Run the HSPF IWater and PWater routines for the selected Precip & PET files
    and upload the result to Google Cloud Storage.

    EXAMPLES:
    >>> tnc run -m HIS

    >>> tnc run -m HIS -m NARR -g R17 -g C42

    >>> tnc run -m HIS -g R17C42 -h hru250
    """
    client = get_client()
    args = main.gather_args(model, gridcell, client=client)
    if hrus is None:
        hrus = list(wwhm.wwhm_hru_params().keys())

    # fully prime the numba cache by running a perv and imp hru
    main.run_one_inputfile(**args[0], hrus=["hru000", "hru252"], client=client)

    nargs = len(args)
    ncores = min(ncores, nargs)

    timings = []
    start = perf_counter()

    with ProcessPoolExecutor(ncores) as exe:
        typer.echo(f"starting {ncores} parallel workers to do {nargs} jobs...")

        with tqdm(total=nargs) as progress:
            # submit tasks and collect futures
            futures = []

            for kwargs in args:
                future = exe.submit(
                    main.run_and_send_results_for_one_inputfile,
                    **kwargs,
                    hrus=hrus,
                    max_workers=ncores,
                    client=None,
                )

                future.add_done_callback(lambda p: progress.update())
                futures.append(future)

            # process task results as they are available
            for future in as_completed(futures):
                _, seconds, send_time, completed = future.result()
                timings.append((seconds, send_time))

    end_all = perf_counter()

    tot_time = end_all - start
    time_per_cell = tot_time / len(args)
    avg_time = sum([a + b for a, b in timings]) / len(timings)
    avg_compute_time = sum([a for a, _ in timings]) / len(timings)
    avg_send_time = sum([b for _, b in timings]) / len(timings)

    typer.echo(f"full job [N={nargs}] took {tot_time: 0.1f} seconds (wall)")
    typer.echo(f"avg gridcell took {avg_time: 0.2f} seconds (per core)")
    typer.echo(f"each gridcell took {time_per_cell: 0.3f} seconds (wall)")
    typer.echo(f"avg hru took {avg_time / len(hrus): 0.3f} seconds (per core)")
    typer.echo(f"each hru took {time_per_cell / len(hrus): 0.3f} seconds (wall)")
    typer.echo(f"avg gridcell compute time {avg_compute_time: 0.3f} seconds (wall)")
    typer.echo(f"avg gridcell upload time {avg_send_time: 0.3f} seconds (wall)")
    # typer.echo([(round(a, 3), round(b, 3)) for a, b in timings])


if __name__ == "__main__":
    app()
