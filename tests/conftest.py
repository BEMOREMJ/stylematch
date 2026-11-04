import json
from pathlib import Path

import pytest

from stylematch.contracts import Dataset, Run

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def data():
    return json.loads((FIXTURES / "dataset.json").read_text(encoding="utf-8"))


@pytest.fixture
def run_data():
    return json.loads((FIXTURES / "run.json").read_text(encoding="utf-8"))


@pytest.fixture
def dataset(data):
    return Dataset.model_validate(data)


@pytest.fixture
def run(run_data):
    return Run.model_validate(run_data)
