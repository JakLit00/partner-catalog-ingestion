from unittest.mock import Mock

import pytest

import extract


@pytest.mark.parametrize(
    ("variable", "value", "expected_message"),
    [
        (
            "API_TIMEOUT_SECONDS",
            value,
            "API_TIMEOUT_SECONDS must be a positive finite number.",
        )
        for value in ["abc", "0", "-1", "nan", "inf", "-inf"]
    ]
    + [
        (
            "POSTGRES_PORT",
            value,
            "POSTGRES_PORT must be an integer between 1 and 65535.",
        )
        for value in ["abc", "5432.5", "0", "-1", "65536"]
    ],
)
def test_main_rejects_invalid_configuration_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    expected_message: str,
) -> None:
    configuration = {
        "API_BASE_URL": "http://catalog.test",
        "API_TIMEOUT_SECONDS": "10",
        "POSTGRES_HOST": "database.test",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_catalog",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
    }
    configuration[variable] = value

    for name, setting in configuration.items():
        monkeypatch.setenv(name, setting)

    monkeypatch.setattr(extract, "load_dotenv", Mock())

    session_factory = Mock()
    connect = Mock()

    monkeypatch.setattr(extract.requests, "Session", session_factory)
    monkeypatch.setattr(extract.psycopg, "connect", connect)

    with pytest.raises(ValueError) as error:
        extract.main()

    assert str(error.value) == expected_message
    session_factory.assert_not_called()
    connect.assert_not_called()