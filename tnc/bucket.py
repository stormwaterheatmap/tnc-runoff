import base64
import json
from functools import cached_property

import orjson
from google.cloud import storage

from .config import settings


class ClimateTSBucket(storage.Client):
    _bucket_name = "climate_ts"

    @cached_property
    def models(self):
        return [
            "WRF-NARR_HIS",
        ]

    @cached_property
    def gridcells(self):
        return [
            f.name.split("inputs/")[1].split("-")[0]
            for f in self.bucket.list_blobs(match_glob=f"{self.models[0]}/**input*")
            if "inputs/" in f.name
        ]

    @property
    def bucket(self):
        return self.get_bucket(self._bucket_name)

    @staticmethod
    def _process_list_arg(arg: str | list[str]):
        if isinstance(arg, str):
            arg = [arg]

        return "{" + ",".join(set(arg)) + "}"

    def get_precip_files(
        self,
        model: str | list[str] | None = None,
        gridcell: str | list[str] | None = None,
    ):
        model = model or "*"
        gridcell = gridcell or "*"

        modelq = self._process_list_arg(model)
        gridcellq = self._process_list_arg(gridcell)

        precips = self.bucket.list_blobs(
            match_glob=f"*{modelq}*/inputs/*{gridcellq}*input.json"
        )
        return [file.name for file in precips]

    def get_error_files(
        self,
        model: str | list[str] | None = None,
        gridcell: str | list[str] | None = None,
    ):  # pragma: no cover
        model = model or "*"
        gridcell = gridcell or "*"

        modelq = self._process_list_arg(model)
        gridcellq = self._process_list_arg(gridcell)

        errs = self.bucket.list_blobs(match_glob=f"*{modelq}**{gridcellq}*.error")
        return [file.name for file in errs]

    def get_json(self, path: str):
        if not path.endswith("json"):
            raise ValueError("not a json file.")
        blob = self.bucket.get_blob(path)
        if blob is None:
            raise ValueError(f"No blob at path {path}")
        blob_data = blob.download_as_bytes()
        return orjson.loads(blob_data)

    def rm_blob(self, path: str):  # pragma: no cover
        blob = self.bucket.get_blob(path)
        if blob is None:
            return

        generation_match_precondition = None

        blob.reload()  # Fetch blob metadata to use in generation_match_precondition.
        generation_match_precondition = blob.generation

        blob.delete(if_generation_match=generation_match_precondition)

    def send_parquet(self, destination_filename, data):  # pragma: no cover
        blob = self.bucket.blob(destination_filename)
        blob.upload_from_string(data, content_type="application/vnd.apache.parquet")
        return destination_filename

    def send_json(self, destination_filename, data):  # pragma: no cover
        blob = self.bucket.blob(destination_filename)
        blob.upload_from_string(
            orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY).replace(
                b"0.0,", b"0,"
            ),
            "application/json",
        )

        return destination_filename


def get_client():
    sa_info = json.loads(
        base64.b64decode(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON).decode()
    )

    return ClimateTSBucket.from_service_account_info(sa_info)
