from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from tests_integration.testing_utils import (
    SnowparkTestSteps,
)
from tests_integration.testing_utils.snowpark_utils import (
    SnowparkTestSetup,
)
from typing import List
from zipfile import ZipFile


STAGE_NAME = "dev_deployment"


@pytest.mark.integration
def test_snowpark_flow(
    _test_steps, project_directory, alter_snowflake_yml, test_database
):
    database = test_database.upper()
    with project_directory("snowpark") as tmp_dir:
        _test_steps.snowpark_build_should_zip_files()

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{database}.PUBLIC.HELLO_PROCEDURE(name string)",
                    "status": "created",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.TEST()",
                    "status": "created",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.HELLO_FUNCTION(name string)",
                    "status": "created",
                    "type": "function",
                },
            ]
        )

        _test_steps.assert_those_procedures_are_in_snowflake(
            "HELLO_PROCEDURE(VARCHAR) RETURN VARCHAR"
        )
        _test_steps.assert_those_functions_are_in_snowflake(
            "HELLO_FUNCTION(VARCHAR) RETURN VARCHAR"
        )

        expected_files = [
            f"{STAGE_NAME}/my_snowpark_project/app.zip",
        ]
        _test_steps.assert_that_only_these_files_are_staged_in_test_db(
            *expected_files, stage_name=STAGE_NAME
        )

        # Listing procedures or functions shows created objects
        _test_steps.object_show_includes_given_identifiers(
            object_type="procedure",
            identifier=("hello_procedure", "(VARCHAR) RETURN VARCHAR"),
        )
        _test_steps.object_show_includes_given_identifiers(
            object_type="function",
            identifier=("hello_function", "(VARCHAR) RETURN VARCHAR"),
        )

        # Created objects can be described
        _test_steps.object_describe_should_return_entity_description(
            object_type="procedure",
            identifier="HELLO_PROCEDURE(VARCHAR)",
            signature="(NAME VARCHAR)",
            returns="VARCHAR(16777216)",
        )

        _test_steps.object_describe_should_return_entity_description(
            object_type="function",
            identifier="HELLO_FUNCTION(VARCHAR)",
            signature="(NAME VARCHAR)",
            returns="VARCHAR(16777216)",
        )

        # Created objects can be executed
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="procedure",
            identifier="hello_procedure('foo')",
            expected_value="Hello foo",
        )

        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="hello_function('foo')",
            expected_value="Hello foo!",
        )

        # Subsequent deploy of same object should fail
        _test_steps.snowpark_deploy_should_return_error_with_message_contains(
            "Following objects already exists"
        )

        # Apply changes to project objects
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.procedures.0.returns",
            value="variant",
        )
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.0.returns",
            value="variant",
        )

        # Now we deploy with replace flag, it should update existing objects
        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            additional_arguments=["--replace"],
            expected_result=[
                {
                    "object": f"{database}.PUBLIC.HELLO_PROCEDURE(name string)",
                    "status": "definition updated",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.TEST()",
                    "status": "packages updated",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.HELLO_FUNCTION(name string)",
                    "status": "definition updated",
                    "type": "function",
                },
            ],
        )

        # Check if objects were updated
        _test_steps.assert_those_procedures_are_in_snowflake(
            "HELLO_PROCEDURE(VARCHAR) RETURN VARIANT"
        )
        _test_steps.assert_those_functions_are_in_snowflake(
            "HELLO_FUNCTION(VARCHAR) RETURN VARIANT"
        )

        _test_steps.assert_that_only_these_files_are_staged_in_test_db(
            *expected_files, stage_name=STAGE_NAME
        )

        # Listing procedures or functions shows updated objects
        _test_steps.object_show_includes_given_identifiers(
            object_type="procedure",
            identifier=("hello_procedure", "(VARCHAR) RETURN VARIANT"),
        )
        _test_steps.object_show_includes_given_identifiers(
            object_type="function",
            identifier=("hello_function", "(VARCHAR) RETURN VARIANT"),
        )

        # Updated objects can be executed
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="procedure",
            identifier="hello_procedure('foo')",
            expected_value='"Hello foo"',
        )

        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="hello_function('foo')",
            expected_value='"Hello foo!"',
        )

        # Check if adding import triggers replace
        _test_steps.package_should_build_proper_artifact(
            "dummy_pkg_for_tests", "dummy_pkg_for_tests/shrubbery.py"
        )
        _test_steps.package_should_upload_artifact_to_stage(
            "dummy_pkg_for_tests.zip", STAGE_NAME
        )

        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.0.imports",
            value=["@dev_deployment/dummy_pkg_for_tests.zip"],
        )

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            additional_arguments=["--replace"],
            expected_result=[
                {
                    "object": f"{database}.PUBLIC.HELLO_PROCEDURE(name string)",
                    "status": "packages updated",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.TEST()",
                    "status": "packages updated",
                    "type": "procedure",
                },
                {
                    "object": f"{database}.PUBLIC.HELLO_FUNCTION(name string)",
                    "status": "definition updated",
                    "type": "function",
                },
            ],
        )

        # Same file should be present, with addition of uploaded package
        expected_files.append(f"{STAGE_NAME}/dummy_pkg_for_tests.zip")

        _test_steps.assert_that_only_these_files_are_staged_in_test_db(
            *expected_files, stage_name=STAGE_NAME
        )

        # Check if objects can be dropped
        _test_steps.object_drop_should_finish_successfully(
            object_type="procedure", identifier="hello_procedure(varchar)"
        )
        _test_steps.object_drop_should_finish_successfully(
            object_type="function", identifier="hello_function(varchar)"
        )

        _test_steps.object_show_should_return_no_data(
            object_type="function", object_prefix="hello"
        )
        _test_steps.object_show_should_return_no_data(
            object_type="procedure", object_prefix="hello"
        )

        _test_steps.assert_that_only_these_files_are_staged_in_test_db(
            *expected_files, stage_name=STAGE_NAME
        )


@pytest.mark.integration
def test_snowpark_with_separately_created_package(
    _test_steps, project_directory, alter_snowflake_yml, test_database
):
    _test_steps.package_should_build_proper_artifact(
        "dummy_pkg_for_tests", "dummy_pkg_for_tests/shrubbery.py"
    )
    _test_steps.package_should_upload_artifact_to_stage(
        "dummy_pkg_for_tests.zip", STAGE_NAME
    )

    _test_steps.artifacts_left_after_package_creation_should_be_deleted(
        "dummy_pkg_for_tests.zip"
    )

    with project_directory("snowpark_with_import") as p_dir:

        _test_steps.snowpark_build_should_zip_files(additional_files=[Path("app.zip")])

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{test_database.upper()}.PUBLIC.TEST_FUNC(name string)",
                    "status": "created",
                    "type": "function",
                },
            ]
        )
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="test_func('foo')",
            expected_value="We want... a shrubbery!",
        )


@pytest.mark.integration
def test_snowpark_with_single_dependency_having_no_other_deps(
    runner, _test_steps, project_directory, alter_snowflake_yml, test_database
):
    with project_directory("snowpark_with_single_requirements_having_no_other_deps"):
        result = runner.invoke_json(
            [
                "snowpark",
                "build",
                "--check-anaconda-for-pypi-deps",
            ]
        )
        assert result.exit_code == 0

        assert "dummy_pkg_for_tests/shrubbery.py" in ZipFile("app.zip").namelist()

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{test_database.upper()}.PUBLIC.TEST_FUNC(name string)",
                    "type": "function",
                    "status": "created",
                }
            ]
        )

        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="test_func('foo')",
            expected_value="We want... a shrubbery!",
        )


@pytest.mark.integration
def test_snowpark_with_single_requirement_having_transient_deps(
    runner, _test_steps, project_directory, alter_snowflake_yml, test_database
):
    with project_directory("snowpark_with_single_requirements_having_transient_deps"):
        result = runner.invoke_json(
            [
                "snowpark",
                "build",
                "--check-anaconda-for-pypi-deps",
            ]
        )
        assert result.exit_code == 0

        files = ZipFile("app.zip").namelist()
        assert "dummy_pkg_for_tests_with_deps/shrubbery.py" in files
        assert "dummy_pkg_for_tests/shrubbery.py" in files  # as transient dep

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{test_database.upper()}.PUBLIC.TEST_FUNC(name string)",
                    "type": "function",
                    "status": "created",
                }
            ]
        )

        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="test_func('foo')",
            expected_value="['We want... a shrubbery!', 'fishy, fishy, fish!']",
        )


@pytest.mark.integration
def test_snowpark_commands_executed_outside_project_dir(
    runner, _test_steps, project_directory, alter_snowflake_yml, test_database
):
    project_subpath = "my_snowpark_project"
    with project_directory(
        "snowpark_with_single_requirements_having_transient_deps",
        subpath=project_subpath,
    ):
        result = runner.invoke_json(
            [
                "snowpark",
                "build",
                "--project",
                project_subpath,
                "--check-anaconda-for-pypi-deps",
            ]
        )
        assert result.exit_code == 0

        files = ZipFile(Path(project_subpath) / "app.zip").namelist()
        assert "dummy_pkg_for_tests_with_deps/shrubbery.py" in files
        assert "dummy_pkg_for_tests/shrubbery.py" in files  # as transient dep

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            additional_arguments=["--project", project_subpath],
            expected_result=[
                {
                    "object": f"{test_database.upper()}.PUBLIC.TEST_FUNC(name string)",
                    "type": "function",
                    "status": "created",
                }
            ],
        )

        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="test_func('foo')",
            expected_value="['We want... a shrubbery!', 'fishy, fishy, fish!']",
        )


@pytest.mark.integration
def test_snowpark_default_arguments(
    _test_steps, project_directory, alter_snowflake_yml, test_database
):
    database = test_database.upper()
    with project_directory("snowpark_with_default_values") as tmp_dir:
        _test_steps.snowpark_build_should_zip_files()

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{database}.PUBLIC.WHOLE_NEW_WORD_PROCEDURE(base varchar default 'word', "
                    "mult number default 2, suffix varchar default ', but a procedure')",
                    "type": "procedure",
                    "status": "created",
                },
                {
                    "object": f"{database}.PUBLIC.WHOLE_NEW_WORD(base string default 'word', "
                    "mult int default 2, suffix string default '!')",
                    "type": "function",
                    "status": "created",
                },
                {
                    "object": f"{database}.PUBLIC.CHECK_ALL_TYPES("
                    "s string default '<str>', "
                    "i int default 7, "
                    "b1 boolean default true, "
                    "b2 boolean default True, "
                    "f float default 1.5, "
                    "l array default [1, 2, 3])",
                    "status": "created",
                    "type": "function",
                },
            ]
        )

        _test_steps.object_show_includes_given_identifiers(
            object_type="function",
            identifier=(
                "WHOLE_NEW_WORD",
                "(DEFAULT VARCHAR, DEFAULT NUMBER, DEFAULT VARCHAR) RETURN VARCHAR",
            ),
        )
        _test_steps.object_show_includes_given_identifiers(
            object_type="procedure",
            identifier=(
                "WHOLE_NEW_WORD_PROCEDURE",
                "(DEFAULT VARCHAR, DEFAULT NUMBER, DEFAULT VARCHAR) RETURN VARCHAR",
            ),
        )

        # Created objects can be described
        _test_steps.object_describe_should_return_entity_description(
            object_type="function",
            identifier="WHOLE_NEW_WORD(VARCHAR, NUMBER, VARCHAR)",
            signature="(BASE VARCHAR, MULT NUMBER, SUFFIX VARCHAR)",
            returns="VARCHAR(16777216)",
        )
        _test_steps.object_describe_should_return_entity_description(
            object_type="procedure",
            identifier="WHOLE_NEW_WORD_PROCEDURE(VARCHAR, NUMBER, VARCHAR)",
            signature="(BASE VARCHAR, MULT NUMBER, SUFFIX VARCHAR)",
            returns="VARCHAR(16777216)",
        )

        # execute with default arguments
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="whole_new_word()",
            expected_value="wordword!",
        )
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="procedure",
            identifier="whole_new_word_procedure()",
            expected_value="wordword, but a procedure",
        )

        # execute naming arguments
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="whole_new_word(mult => 4, base => 'nii')",
            expected_value="niiniiniinii!",
        )
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="procedure",
            identifier="whole_new_word_procedure(mult => 4, base => 'nii')",
            expected_value="niiniiniinii, but a procedure",
        )

        # check default values for all types
        _test_steps.snowpark_execute_should_return_expected_value(
            object_type="function",
            identifier="check_all_types()",
            expected_value="s:<str>, i:7, b1:True, b2:True, f:1.5, l:[1, 2, 3]",
        )


@pytest.mark.integration
def test_snowpark_fully_qualified_name(
    _test_steps,
    runner,
    test_database,
    project_directory,
    alter_snowflake_yml,
):
    database = test_database.upper()
    default_schema = "PUBLIC"
    different_schema = "TOTALLY_DIFFERENT_SCHEMA"

    runner.invoke_with_connection(
        ["sql", "-q", f"create schema {database}.{different_schema}"]
    )
    with project_directory("snowpark_fully_qualified_name") as tmp_dir:
        _test_steps.snowpark_build_should_zip_files()

        # "default" database and schema provided by fully qualified name
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.0.name",
            value=f"{database}.{default_schema}.fqn_function",
        )
        # changed schema provided by fully qualified name
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.1.name",
            value=f"{database}.{different_schema}.fqn_function2",
        )
        # changed schema provided as argument
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.2.schema",
            value=different_schema,
        )
        # default database provided as argument
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.3.database",
            value=database,
        )
        # provide default database and changed schema as arguments
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.4.schema",
            value=different_schema,
        )
        alter_snowflake_yml(
            tmp_dir / "snowflake.yml",
            parameter_path="snowpark.functions.4.database",
            value=database,
        )

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{database}.{default_schema}.FQN_FUNCTION(name string)",
                    "status": "created",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.FQN_FUNCTION2(name string)",
                    "status": "created",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.SCHEMA_FUNCTION(name "
                    "string)",
                    "status": "created",
                    "type": "function",
                },
                {
                    "object": f"{database}.{default_schema}.DATABASE_FUNCTION(name string)",
                    "status": "created",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.DATABASE_SCHEMA_FUNCTION(name "
                    "string)",
                    "status": "created",
                    "type": "function",
                },
            ]
        )

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{database}.{default_schema}.FQN_FUNCTION(name string)",
                    "status": "packages updated",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.FQN_FUNCTION2(name string)",
                    "status": "packages updated",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.SCHEMA_FUNCTION(name "
                    "string)",
                    "status": "packages updated",
                    "type": "function",
                },
                {
                    "object": f"{database}.{default_schema}.DATABASE_FUNCTION(name string)",
                    "status": "packages updated",
                    "type": "function",
                },
                {
                    "object": f"{database}.{different_schema}.DATABASE_SCHEMA_FUNCTION(name "
                    "string)",
                    "status": "packages updated",
                    "type": "function",
                },
            ],
            additional_arguments=["--replace"],
        )


@pytest.mark.integration
def test_snowpark_vector_function(
    _test_steps,
    project_directory,
    alter_snowflake_yml,
    test_database,
    snowflake_session,
):
    database = test_database.upper()
    with project_directory("snowpark_vectorized") as tmp_dir:
        _test_steps.snowpark_build_should_zip_files()

        _test_steps.snowpark_deploy_should_finish_successfully_and_return(
            [
                {
                    "object": f"{database}.PUBLIC.VECTOR_FUNC(x number(10, 5), y number(10, 5))",
                    "status": "created",
                    "type": "function",
                },
            ]
        )

        result = snowflake_session.execute_string(
            dedent(
                f"""
            select {database}.PUBLIC.VECTOR_FUNC(x, y)
            from (
              select 1 as x, 3.14::float as y union all
              select 2, 1.59 union all
              select 3, -0.5
            );
        """
            )
        )
        assert [r for r in result[0]] == [(4.14,), (3.59,), (2.5,)]


@pytest.mark.integration
def test_build_skip_version_check(
    runner, project_directory, alter_requirements_txt, test_database
):
    # test case: package is available in Anaconda, but not in required version
    with project_directory("snowpark") as tmp_dir:
        alter_requirements_txt(tmp_dir / "requirements.txt", ["matplotlib>=1000"])
        result = runner.invoke_with_connection(["snowpark", "build"])
        assert result.exit_code == 1, result.output
        assert ("pip failed with return code") in result.output
        assert (" Most likely reasons:") in result.output
        assert (" * incorrect package name or version") in result.output

        result = runner.invoke_with_connection(
            ["snowpark", "build", "--skip-version-check"]
        )
        assert result.exit_code == 0, result.output
        assert "Build done. Artifact path: " in result.output


@pytest.mark.integration
@pytest.mark.parametrize(
    "flags",
    [
        ["--allow-shared-libraries"],
        ["--package-native-libraries", "yes"],
        ["--allow-shared-libraries", "--ignore-anaconda"],
    ],
)
def test_build_with_anaconda_dependencies(
    flags, runner, project_directory, alter_requirements_txt, test_database
):
    with project_directory("snowpark") as tmp_dir:
        alter_requirements_txt(tmp_dir / "requirements.txt", ["july", "snowflake.core"])
        result = runner.invoke_with_connection(["snowpark", "build", *flags])
        assert result.exit_code == 0, result.output
        assert "Build done. Artifact path:" in result.output

        requirements_snowflake = tmp_dir / "requirements.snowflake.txt"
        if "--ignore-anaconda" in flags:
            assert not requirements_snowflake.exists()
        else:
            assert requirements_snowflake.exists()
            assert "matplotlib" in requirements_snowflake.read_text()
            assert "numpy" in requirements_snowflake.read_text()
            assert "snowflake.core" in requirements_snowflake.read_text()


@pytest.mark.integration
def test_build_with_non_anaconda_dependencies(
    runner, project_directory, alter_requirements_txt, test_database
):
    with project_directory("snowpark") as tmp_dir:
        alter_requirements_txt(
            tmp_dir / "requirements.txt", ["dummy-pkg-for-tests-with-deps"]
        )
        result = runner.invoke_with_connection(["snowpark", "build"])
        assert result.exit_code == 0, result.output
        assert "Build done. Artifact path:" in result.output

        files = ZipFile(tmp_dir / "app.zip").namelist()
        assert "dummy_pkg_for_tests/shrubbery.py" in files
        assert "dummy_pkg_for_tests_with_deps/shrubbery.py" in files


@pytest.mark.integration
def test_build_shared_libraries_error(
    runner, project_directory, alter_requirements_txt, test_database
):
    with project_directory("snowpark") as tmp_dir:
        alter_requirements_txt(tmp_dir / "requirements.txt", ["numpy"])
        result = runner.invoke_with_connection(
            ["snowpark", "build", "--ignore-anaconda"]
        )
        assert result.exit_code == 1, result.output
        assert (
            "Some packages contain shared (.so/.dll) libraries. Try again with"
            in result.output
        )
        assert "--allow-shared-libraries." in result.output
        assert "Build done." not in result.output


@pytest.mark.integration
def test_build_package_from_github(
    runner, project_directory, alter_requirements_txt, test_database
):
    with project_directory("snowpark") as tmp_dir:
        alter_requirements_txt(
            tmp_dir / "requirements.txt",
            [
                "git+https://github.com/sfc-gh-turbaszek/dummy-pkg-for-tests-with-deps.git"
            ],
        )
        result = runner.invoke_with_connection(["snowpark", "build"])
        assert result.exit_code == 0, result.output
        assert "Build done. Artifact path:" in result.output

        assert (
            "dummy_pkg_for_tests/shrubbery.py"
            in ZipFile(tmp_dir / "app.zip").namelist()
        )


@pytest.mark.integration
@pytest.mark.parametrize("flag", ["--ignore-anaconda", ""])
def test_ignore_anaconda_uses_version_from_zip(
    flag, project_directory, runner, test_database
):
    with project_directory("snowpark_version_check"):
        command = ["snowpark", "build", "--allow-shared-libraries"]
        if flag:
            command.append(flag)
        result = runner.invoke_with_connection(command)
        assert result.exit_code == 0, result.output

        result = runner.invoke_with_connection(["snowpark", "deploy"])
        assert result.exit_code == 0, result.output

        result = runner.invoke_with_connection_json(
            ["snowpark", "execute", "function", "check_mypy_version()"]
        )
        assert result.exit_code == 0, result.output
        # earliest mypy 1.* version is 1.5
        assert result.json == {"CHECK_MYPY_VERSION()": "1.3.0"}


@pytest.fixture
def _test_setup(
    runner,
    sql_test_helper,
    test_database,
    temporary_working_directory,
    snapshot,
):
    snowpark_procedure_test_setup = SnowparkTestSetup(
        runner=runner,
        sql_test_helper=sql_test_helper,
        test_database=test_database,
        snapshot=snapshot,
    )
    yield snowpark_procedure_test_setup


@pytest.fixture
def _test_steps(_test_setup):
    yield SnowparkTestSteps(_test_setup)


@pytest.fixture
def alter_requirements_txt():
    def update(requirements_path: Path, requirements: List[str]):
        requirements.append("snowflake-snowpark-python")
        requirements_path.write_text("\n".join(requirements))

    yield update
