import io
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from typing import Any, Union

import requests


class URL(Enum):
    FIAS = (
        "https://apps.bea.gov/national/FixedAssets/Release/TXT/FixedAssets.txt"
    )
    NIPA = "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt"

    def get_kwargs(self) -> dict[str, Any]:

        NAMES = ["series_ids", "period", "value"]

        kwargs = {
            "header": 0,
            "names": NAMES,
            "index_col": 1,
            "thousands": ",",
        }
        if requests.head(self.value).status_code == HTTPStatus.OK:
            kwargs["filepath_or_buffer"] = io.BytesIO(
                requests.get(self.value).content
            )
        else:
            kwargs["filepath_or_buffer"] = self.value.split("/")[-1]
        return kwargs


@dataclass(frozen=True, eq=True)
class SeriesID:
    series_id: str
    source: Union[URL]
