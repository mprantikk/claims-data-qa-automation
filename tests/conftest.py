import pytest

from claimsqa.generate import generate_extract


@pytest.fixture(scope="session")
def raw_extract():
    return generate_extract(n=1000, seed=1).astype(str)
