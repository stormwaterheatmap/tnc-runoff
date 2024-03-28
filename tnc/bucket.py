import base64
import json
from functools import cached_property
from io import BytesIO

import orjson
import pandas
from google.cloud import storage

from .config import settings
from .hspf_runner import get_TNC_siminfo


class ClimateTSBucket(storage.Client):
    _bucket_name = "climate_ts"
    _datetime_cache = {}

    @cached_property
    def models(self):
        return ["WRF-NARR_HIS"]

    @cached_property
    def gridcells(self):
        return [
            f.name.split("/")[1]
            for f in self.bucket.list_blobs(match_glob=f"{self.models[0]}/**input*")
        ]

    @cached_property
    def hrus(self):
        return [
            f.name.split("/")[-1].split(".")[0]
            for f in self.bucket.list_blobs(match_glob=f"{self.models[0]}/**hru*")
        ]

    @property
    def bucket(self):
        return self.get_bucket(self._bucket_name)

    def get_precip_files(self, model: str):
        precips = self.list_blobs(self._bucket_name, match_glob=f"**{model}**input**")
        return [file.name for file in precips]

    def get_datetime_file(self, model: str):
        file = next(
            self.list_blobs(self._bucket_name, match_glob=f"**{model}**datetime**"),
            None,
        )
        return file.name if file else None

    def _get_dt_info(self, model: str):
        if model not in self._datetime_cache:
            dtstr = self.bucket.get_blob(
                self.get_datetime_file(model)
            ).download_as_string()

            df = pandas.read_csv(BytesIO(dtstr))
            start = pandas.to_datetime(
                df.iloc[0]["datetime"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
            stop = pandas.to_datetime(
                df.iloc[-1]["datetime"].replace("Z", "+00:00")
            ).replace(tzinfo=None)

            self._datetime_cache[model] = {"datetime": df, "start": start, "stop": stop}

        return self._datetime_cache[model]

    def get_TNC_siminfo(self, model: str):
        dt_info = self._get_dt_info(model)

        return get_TNC_siminfo(dt_info["start"], dt_info["stop"])

    def get_json(self, path: str):
        if not path.endswith("json"):
            raise ValueError("not a json file.")
        blob = self.bucket.get_blob(path)
        blob_data = blob.download_as_string()
        return orjson.loads(blob_data)

    def send_json(self, destination_filename, data):
        blob = self.bucket.blob(destination_filename)
        blob.upload_from_string(
            orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY).replace(
                b"0.0,", b"0,"
            ),
            content_type="application/json",
        )


def get_client():
    sa_info = json.loads(
        base64.b64decode(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON).decode()
    )

    return ClimateTSBucket.from_service_account_info(sa_info)
