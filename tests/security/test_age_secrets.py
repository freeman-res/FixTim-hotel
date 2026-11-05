"""The encrypted launcher accepts only the two weather keys it is meant to load."""
import pytest

from scripts.run_with_secrets import parse_secret_lines


def test_parse_weather_secrets_without_shell_evaluation():
    parsed = parse_secret_lines("# weather\nWEATHERBIT_KEY=abc123\nWEATHERAPI_KEY=x=y\n")
    assert parsed == {"WEATHERBIT_KEY": "abc123", "WEATHERAPI_KEY": "x=y"}


@pytest.mark.parametrize("text", [
    "PATH=/tmp/unsafe", "WEATHERBIT_KEY=$(whoami)",
    "WEATHERBIT_KEY=first\nWEATHERBIT_KEY=second",
    "WEATHERAPI_KEY=", "export WEATHERBIT_KEY=abc",
])
def test_reject_unexpected_or_ambiguous_secret_lines(text):
    with pytest.raises(ValueError):
        parse_secret_lines(text)
