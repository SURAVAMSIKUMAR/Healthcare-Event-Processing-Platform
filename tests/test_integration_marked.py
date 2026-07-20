import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Integration tests require DATABASE_URL and running infrastructure",
)
def test_integration_env_available() -> None:
    # This acts as a smoke check that integration suite is intentionally environment-gated.
    assert bool(os.getenv("DATABASE_URL"))
