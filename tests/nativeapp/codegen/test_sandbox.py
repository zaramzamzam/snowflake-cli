import subprocess
from pathlib import Path
from unittest import mock

import pytest
import snowflake.cli.plugins.nativeapp.codegen.sandbox as sandbox

PYTHON_SCRIPT = """
import sys

print(sys.version)
"""

SCRIPT_OUT = "stdout"
SCRIPT_ERR = "stderr"
SCRIPT_ARGS = ["arg1", "arg2"]
CONDA_ENV_NAME_FROM_ENVIRON = "conda_from_env_var"
VIRTUAL_ENV_ROOT_FROM_ENVIRON = "/path/to/env_from_env_var"
CONDA_ONLY_ENVIRON = {"CONDA_DEFAULT_ENV": CONDA_ENV_NAME_FROM_ENVIRON}
VENV_ONLY_ENVIRON = {"VIRTUAL_ENV": VIRTUAL_ENV_ROOT_FROM_ENVIRON}
TIMEOUT = 60
NEW_CWD = "/path/to/cwd"


@pytest.fixture
def mock_environ():
    with mock.patch("os.environ.get") as mock_env:
        mock_env.side_effect = {}.get
        yield mock_env


@pytest.fixture
def fake_venv_root(temp_dir):
    venv_root = Path(temp_dir) / "venv"
    venv_root.mkdir()

    bin_dir = venv_root / "bin"
    bin_dir.mkdir(parents=True)

    interpreter = bin_dir / "python3"
    interpreter.touch(mode=0o755, exist_ok=True)

    yield venv_root


@pytest.fixture
def fake_venv_root_win32(temp_dir):
    venv_root = Path(temp_dir) / "venv"
    venv_root.mkdir()

    bin_dir = venv_root / "Scripts"
    bin_dir.mkdir(parents=True)

    interpreter = bin_dir / "python.exe"
    interpreter.touch(mode=0o755, exist_ok=True)

    yield venv_root


@pytest.mark.parametrize(
    "expected_timeout, expected_cwd",
    [
        (None, None),
        (TIMEOUT, None),
        (None, NEW_CWD),
        (None, Path(NEW_CWD)),
        (TIMEOUT, NEW_CWD),
    ],
)
@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_in_named_conda_env(
    mock_which, mock_run, mock_environ, expected_timeout, expected_cwd
):
    mock_which.side_effect = (
        lambda executable: "/path/to/conda" if executable == "conda" else None
    )
    mock_environ.side_effect = CONDA_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT,
        sandbox.ExecutionEnvironmentType.CONDA,
        name="foo",
        timeout=expected_timeout,
        cwd=expected_cwd,
    )

    mock_run.assert_called_once_with(
        ["/path/to/conda", "run", "-n", "foo", "--no-capture-output", "python", "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=expected_cwd,
        timeout=expected_timeout,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_in_conda_env_falls_back_to_activated_one(
    mock_which, mock_run, mock_environ
):
    mock_which.side_effect = (
        lambda executable: "/path/to/conda" if executable == "conda" else None
    )
    mock_environ.side_effect = CONDA_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.CONDA
    )

    mock_run.assert_called_once_with(
        [
            "/path/to/conda",
            "run",
            "-n",
            CONDA_ENV_NAME_FROM_ENVIRON,
            "--no-capture-output",
            "python",
            "-",
        ],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_in_conda_env_fails_when_conda_not_found(
    mock_which, mock_run, mock_environ
):
    mock_which.return_value = None

    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.CONDA, name="foo"
        )

    assert mock_which.called_once_with("conda")
    assert not mock_run.called


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_in_conda_env_fails_when_conda_env_cannot_be_determined(
    mock_which, mock_run, mock_environ
):
    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.CONDA
        )

    assert not mock_which.called
    assert not mock_run.called


@pytest.mark.parametrize(
    "expected_timeout, expected_cwd",
    [
        (None, None),
        (TIMEOUT, None),
        (None, NEW_CWD),
        (None, Path(NEW_CWD)),
        (TIMEOUT, NEW_CWD),
    ],
)
@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_specified_venv_root_unix(
    mock_run, mock_environ, fake_venv_root, expected_timeout, expected_cwd
):
    mock_environ.side_effect = VENV_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT,
        sandbox.ExecutionEnvironmentType.VENV,
        path=fake_venv_root,
        timeout=expected_timeout,
        cwd=expected_cwd,
    )

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=expected_cwd,
        timeout=expected_timeout,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_specified_venv_root_as_string(
    mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = VENV_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT,
        sandbox.ExecutionEnvironmentType.VENV,
        path=str(fake_venv_root.resolve()),
    )

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("sys.platform", "win32")
@mock.patch("subprocess.run")
def test_execute_in_specified_venv_root_windows(
    mock_run, mock_environ, fake_venv_root_win32
):
    mock_environ.side_effect = VENV_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.VENV, path=fake_venv_root_win32
    )

    expected_interpreter = fake_venv_root_win32 / "Scripts" / "python.exe"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_venv_falls_back_to_activated_one(
    mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = {"VIRTUAL_ENV": str(fake_venv_root)}.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.VENV
    )

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_venv_fails_when_no_root_specified(mock_run, mock_environ):
    mock_environ.side_effect = {}.get

    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.VENV
        )

    assert not mock_run.called


@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_venv_fails_when_root_not_found(mock_run, mock_environ):
    mock_environ.side_effect = {}.get

    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT,
            sandbox.ExecutionEnvironmentType.VENV,
            path=Path("/path/to/non-existent/root"),
        )

    assert not mock_run.called


@mock.patch("sys.platform", "darwin")
@mock.patch("subprocess.run")
def test_execute_in_venv_fails_when_interpreter_not_found(
    mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = {}.get

    expected_interpreter = fake_venv_root / "bin" / "python3"
    expected_interpreter.unlink()

    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.VENV, path=fake_venv_root
        )

    assert not mock_run.called


@pytest.mark.parametrize(
    "expected_timeout, expected_cwd",
    [
        (None, None),
        (TIMEOUT, None),
        (None, NEW_CWD),
        (None, Path(NEW_CWD)),
        (TIMEOUT, NEW_CWD),
    ],
)
@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_system_python_looks_for_python3(
    mock_which, mock_run, mock_environ, expected_timeout, expected_cwd
):
    expected_interpreter = Path("/path/to/python3")
    mock_which.side_effect = (
        lambda executable: expected_interpreter if executable == "python3" else None
    )

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT,
        sandbox.ExecutionEnvironmentType.SYSTEM_PATH,
        cwd=expected_cwd,
        timeout=expected_timeout,
    )

    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=expected_cwd,
        timeout=expected_timeout,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_system_python_falls_back_to_python(mock_which, mock_run, mock_environ):
    expected_interpreter = Path("/path/to/python")
    mock_which.side_effect = (
        lambda executable: expected_interpreter if executable == "python" else None
    )

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.SYSTEM_PATH
    )

    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert mock_which.called_once_with("python3")
    assert mock_which.called_once_with("python")


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
@mock.patch("sys.executable", "/path/to/python")
def test_execute_system_python_falls_back_to_current_interpreter(
    mock_which, mock_run, mock_environ
):
    expected_interpreter = "/path/to/python"
    mock_which.return_value = None

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.SYSTEM_PATH
    )

    mock_run.assert_called_once_with(
        [expected_interpreter, "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert mock_which.called_once_with("python3")
    assert mock_which.called_once_with("python")


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
@mock.patch("sys.executable", None)
def test_execute_system_python_fails_when_no_interpreter_available(
    mock_which, mock_run, mock_environ
):
    mock_which.return_value = None

    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.execute_script_in_sandbox(
            PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.SYSTEM_PATH
        )

    assert not mock_run.called
    assert mock_which.called_once_with("python3")
    assert mock_which.called_once_with("python")


@pytest.mark.parametrize(
    "expected_timeout, expected_cwd",
    [
        (None, None),
        (TIMEOUT, None),
        (None, NEW_CWD),
        (None, Path(NEW_CWD)),
        (TIMEOUT, NEW_CWD),
    ],
)
@mock.patch("subprocess.run")
@mock.patch("shutil.which")
@mock.patch("sys.executable", "/path/to/python")
def test_execute_in_current_interpreter(
    mock_which, mock_run, mock_environ, expected_timeout, expected_cwd
):
    expected_interpreter = "/path/to/python"
    mock_which.return_value = "/path/to/ignored/python"

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT,
        sandbox.ExecutionEnvironmentType.CURRENT,
        timeout=expected_timeout,
        cwd=expected_cwd,
    )

    mock_run.assert_called_once_with(
        [expected_interpreter, "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=expected_cwd,
        timeout=expected_timeout,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert not mock_which.called


@mock.patch("subprocess.run")
def test_execute_auto_detects_venv(mock_run, mock_environ, fake_venv_root):
    mock_environ.side_effect = {"VIRTUAL_ENV": str(fake_venv_root)}.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.AUTO_DETECT
    )

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_auto_detects_conda(mock_which, mock_run, mock_environ):
    mock_which.side_effect = (
        lambda executable: "/path/to/conda" if executable == "conda" else None
    )
    mock_environ.side_effect = CONDA_ONLY_ENVIRON.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.AUTO_DETECT
    )

    mock_run.assert_called_once_with(
        [
            "/path/to/conda",
            "run",
            "-n",
            CONDA_ENV_NAME_FROM_ENVIRON,
            "--no-capture-output",
            "python",
            "-",
        ],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_auto_detect_falls_back_to_system_python(
    mock_which, mock_run, mock_environ
):
    expected_interpreter = Path("/path/to/python3")
    mock_which.side_effect = (
        lambda executable: expected_interpreter if executable == "python3" else None
    )

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.AUTO_DETECT
    )

    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert mock_run.called_once_with("python3")


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_auto_detect_chooses_venv_over_conda(
    mock_which, mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = {
        "VIRTUAL_ENV": str(fake_venv_root),
        "CONDA_DEFAULT_ENV": CONDA_ENV_NAME_FROM_ENVIRON,
    }.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(
        PYTHON_SCRIPT, sandbox.ExecutionEnvironmentType.AUTO_DETECT
    )

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert not mock_which.called


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_auto_detect_is_default(
    mock_which, mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = {
        "VIRTUAL_ENV": str(fake_venv_root),
        "CONDA_DEFAULT_ENV": CONDA_ENV_NAME_FROM_ENVIRON,
    }.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=0, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(PYTHON_SCRIPT)

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 0
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert not mock_which.called


@mock.patch("subprocess.run")
@mock.patch("shutil.which")
def test_execute_does_not_interpret_return_codes(
    mock_which, mock_run, mock_environ, fake_venv_root
):
    mock_environ.side_effect = {
        "VIRTUAL_ENV": str(fake_venv_root),
        "CONDA_DEFAULT_ENV": CONDA_ENV_NAME_FROM_ENVIRON,
    }.get

    expected = subprocess.CompletedProcess(
        args=SCRIPT_ARGS, returncode=1, stdout=SCRIPT_OUT, stderr=SCRIPT_ERR
    )
    mock_run.return_value = expected

    actual = sandbox.execute_script_in_sandbox(PYTHON_SCRIPT)

    expected_interpreter = fake_venv_root / "bin" / "python3"
    mock_run.assert_called_once_with(
        [expected_interpreter.resolve(), "-"],
        capture_output=True,
        text=True,
        input=PYTHON_SCRIPT,
        cwd=None,
        timeout=None,
    )

    assert actual.args == SCRIPT_ARGS
    assert actual.returncode == 1
    assert actual.stdout == SCRIPT_OUT
    assert actual.stderr == SCRIPT_ERR

    assert not mock_which.called
