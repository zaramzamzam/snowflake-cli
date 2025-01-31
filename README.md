[![Code quality checks](https://github.com/snowflakedb/snowflake-cli/actions/workflows/lint.yaml/badge.svg)](https://github.com/snowflakedb/snowflake-cli/actions/workflows/lint.yaml)
[![Integration testing](https://github.com/snowflakedb/snowflake-cli/actions/workflows/integration_test.yaml/badge.svg)](https://github.com/snowflakedb/snowflake-cli/actions/workflows/integration_test.yaml)
[![CLI Action testing](https://github.com/snowflakedb/snowflake-cli/actions/workflows/test_cli_action.yaml/badge.svg?branch=main)](https://github.com/snowflakedb/snowflake-cli/actions/workflows/test_cli_action.yaml)

[//]: # ([![Python 3.11]&#40;https://img.shields.io/badge/python-3.11-blue.svg&#41;]&#40;https://www.python.org/downloads/release/python-311/&#41;)

# Snowflake CLI

Snowflake CLI is an open-source command-line tool explicitly designed for developer-centric workloads in addition to SQL operations. It is a flexible and extensible tool that can accommodate modern development practices and technologies.

With Snowflake CLI, developers can create, manage, update, and view apps running on Snowflake across workloads such as Streamlit in Snowflake, the Snowflake Native App Framework, Snowpark Container Services, and Snowpark. It supports a range of Snowflake features, including user-defined functions, stored procedures, Streamlit in Snowflake, and SQL execution.


**Note**: Snowflake CLI is in Public Preview (PuPr). Docs at https://docs.snowflake.com/en/developer-guide/snowflake-cli-v2/index


## Install Snowflake CLI

### Install with pip (PyPi)

Requires Python >= 3.8

```bash
pip install snowflake-cli-labs
snow --help
```

### Install with Homebrew (Mac only)

Requires [Homebrew](https://brew.sh/).

```bash
brew tap Snowflake-Labs/snowflake-cli
brew install snowflake-cli
snow --help
```

### Install from source

Requires Python >= 3.8 and git

```bash
git clone https://github.com/snowflakedb/snowflake-cli
cd snowflake-cli
# you can also do the below in an active virtual environment:
# python -m venv .venv
# source .venv/bin/activate
hatch build && pip install .
snow --version
```

You should now be able to run `snow` and get the CLI message.

## Get involved

Have a feature idea? Running into a bug? Want to contribute? We'd love to hear from you!
Please open or review issues, open pull requests, or reach out to us on developers@snowflake.com
