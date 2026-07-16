from unittest.mock import patch, MagicMock
from autoclave.installation import backend_guard


def test_write_and_read_backend_pid_roundtrip(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(4242, path)
    assert backend_guard.read_backend_pid(path) == 4242


def test_read_backend_pid_missing_file_returns_none(tmp_path):
    path = tmp_path / "does_not_exist.pid"
    assert backend_guard.read_backend_pid(path) is None


def test_read_backend_pid_corrupt_content_returns_none(tmp_path):
    path = tmp_path / "backend.pid"
    path.write_text("not-a-pid", encoding="utf-8")
    assert backend_guard.read_backend_pid(path) is None


def test_is_stale_backend_running_true_when_cmdline_matches():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="C:\\Python\\python.exe -m autoclave.backend.main\r\n"
        )
        assert backend_guard.is_stale_backend_running(1234) is True


def test_is_stale_backend_running_false_when_cmdline_different():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="notepad.exe\r\n")
        assert backend_guard.is_stale_backend_running(1234) is False


def test_is_stale_backend_running_false_when_subprocess_raises():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("powershell no disponible")
        assert backend_guard.is_stale_backend_running(1234) is False


def test_kill_stale_backend_calls_taskkill_con_pid():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        backend_guard.kill_stale_backend(4321)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["taskkill", "/PID", "4321", "/F"]


def test_cleanup_stale_backend_mata_proceso_huerfano(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(9999, path)

    with patch("autoclave.installation.backend_guard.is_stale_backend_running", return_value=True) as mock_is_stale, \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_is_stale.assert_called_once_with(9999)
        mock_kill.assert_called_once_with(9999)


def test_cleanup_stale_backend_no_mata_si_no_esta_huerfano(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(9999, path)

    with patch("autoclave.installation.backend_guard.is_stale_backend_running", return_value=False), \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_kill.assert_not_called()


def test_cleanup_stale_backend_no_hace_nada_sin_pid_file(tmp_path):
    path = tmp_path / "no_existe.pid"

    with patch("autoclave.installation.backend_guard.is_stale_backend_running") as mock_is_stale, \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_is_stale.assert_not_called()
        mock_kill.assert_not_called()
