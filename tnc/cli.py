import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from time import perf_counter
from typing import Optional

import typer
from tqdm import tqdm
from typing_extensions import Annotated

from .main import gather_args, run_and_send_results_for_one_inputfile

N_WORKERS = max(math.ceil((os.cpu_count() or 1) * 0.5), 2)

app = typer.Typer(rich_markup_mode="rich", add_completion=False, no_args_is_help=True)

Model = Annotated[
    Optional[list[str]],
    typer.Option(
        "-m",
        "--model",
        help="name of the model to process. Defaults to all models in the bucket.",
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
def main(
    model: Model = None,
    gridcell: GridCell = None,
    ncores: NCores = N_WORKERS,
    dry_run: DryRun = False,
):
    """
    Run the HSPF IWater and PWater routines for the selected Precip & PET files
    and upload the result to Google Cloud Storage.

    EXAMPLES:
    >>> run-tnc

    >>> run-tnc -m HIS -m NARR -g R17 -g C42

    >>> run-tnc -m HIS -g R17C42
    """
    args = gather_args(model, gridcell)
    nargs = len(args)
    ncores = min(ncores, nargs)

    if dry_run:
        if nargs > 0:
            typer.echo(f"found {nargs} files...")
        for dct in args:
            typer.echo(dct["input_file"])

        return

    timings = []
    start = perf_counter()

    with ProcessPoolExecutor(ncores) as exe:
        typer.echo(f"starting {ncores} parallel workers to do {nargs} jobs...")

        with tqdm(total=len(args)) as progress:
            # submit tasks and collect futures
            futures = []

            for kwargs in args:
                future = exe.submit(
                    run_and_send_results_for_one_inputfile,
                    **kwargs,
                    max_workers=ncores,
                )

                future.add_done_callback(lambda p: progress.update())
                futures.append(future)

            # process task results as they are available
            for future in as_completed(futures):
                _, seconds, send_time = future.result()
                timings.append((seconds, send_time))

    end_all = perf_counter()

    tot_time = end_all - start
    time_per_cell = tot_time / nargs
    avg_time = sum([a + b for a, b in timings]) / len(timings)

    typer.echo(f"full job [N={nargs}] took {tot_time: 0.1f} seconds (wall)")
    typer.echo(f"avg gridcell took {avg_time: 0.2f} seconds (per core)")
    typer.echo(f"each gridcell took {time_per_cell: 0.3f} seconds (wall)")
    typer.echo(f"avg hru took {avg_time / 30: 0.3f} seconds (per core)")
    typer.echo(f"each hru took {time_per_cell / 30: 0.3f} seconds (wall)")
    typer.echo([(round(a, 3), round(b, 3)) for a, b in timings])


if __name__ == "__main__":
    app()
