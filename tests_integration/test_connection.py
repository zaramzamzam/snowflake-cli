import pytest
from tests_integration.snowflake_connector import (
    setup_test_database,
    setup_test_schema,
    add_uuid_to_name,
    mock_single_env_var,
    SCHEMA_ENV_PARAMETER,
)


@pytest.mark.integration
def test_connection_test_simple(runner):
    result = runner.invoke_with_connection_json(["connection", "test"])
    assert result.exit_code == 0, result.output
    assert result.json["Status"] == "OK"


@pytest.mark.integration
def test_connection_dashed_database(runner, snowflake_session):
    database = add_uuid_to_name("dashed-database")
    with setup_test_database(snowflake_session, database):
        result = runner.invoke_with_connection_json(["connection", "test"])
        assert result.exit_code == 0, result.output
        assert result.json["Database"] == database


@pytest.mark.integration
def test_connection_dashed_schema(
    runner, test_database, snowflake_session, snowflake_home
):
    schema = "dashed-schema-name"
    with setup_test_schema(snowflake_session, schema):
        result = runner.invoke_with_connection(["connection", "test", "--debug"])
        assert result.exit_code == 0, result.output
        assert f'use schema "{schema}"' in result.output


@pytest.mark.integration
def test_connection_not_existing_schema(
    runner, test_database, snowflake_session, snowflake_home
):
    schema = "schema_which_does_not_exist"
    with mock_single_env_var(SCHEMA_ENV_PARAMETER, value=schema):
        result = runner.invoke_with_connection(["connection", "test"])
        assert result.exit_code == 1, result.output
        assert (
            f'Could not use schema "{schema.upper()}". Object does not exist'
            in result.output
        )
