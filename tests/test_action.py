import io
import os
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import action


class TestHumanSize:
    def test_bytes(self):
        assert action._human_size(0) == "0.00 B"
        assert action._human_size(1) == "1.00 B"
        assert action._human_size(512) == "512.00 B"
        assert action._human_size(1023) == "1023.00 B"

    def test_kilobytes(self):
        assert action._human_size(1024) == "1.00 KB"
        assert action._human_size(1536) == "1.50 KB"
        assert action._human_size(10240) == "10.00 KB"

    def test_megabytes(self):
        assert action._human_size(1048576) == "1.00 MB"
        assert action._human_size(5242880) == "5.00 MB"

    def test_gigabytes(self):
        assert action._human_size(1073741824) == "1.00 GB"

    def test_terabytes(self):
        assert action._human_size(1099511627776) == "1.00 TB"

    def test_petabytes(self):
        assert action._human_size(1125899906842624) == "1.00 PB"

    def test_cap_at_petabytes(self):
        # Should not exceed PB suffix
        assert action._human_size(1125899906842624 * 1024) == "1024.00 PB"


class TestFindFiles:
    def _setup_tmpdir(self, structure):
        """Create a temp directory with the given file structure.

        structure is a list of relative paths to create.
        Directories are created with mkdir; files with touch.
        """
        tmpdir = tempfile.mkdtemp()
        for rel in structure:
            p = Path(tmpdir) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith("/"):
                p.mkdir(exist_ok=True)
            else:
                p.touch()
        return tmpdir

    def test_single_file(self):
        tmpdir = self._setup_tmpdir(["foo.txt"])
        files = action._find_files(os.path.join(tmpdir, "foo.txt"))
        assert files == [os.path.join(tmpdir, "foo.txt")]

    def test_directory_wildcard(self):
        tmpdir = self._setup_tmpdir(["a.txt", "b.txt", "sub/c.txt"])
        files = action._find_files(tmpdir)
        assert sorted(files) == sorted(
            [
                os.path.join(tmpdir, "a.txt"),
                os.path.join(tmpdir, "b.txt"),
                os.path.join(tmpdir, "sub", "c.txt"),
            ]
        )

    def test_directory_explicit_path(self):
        tmpdir = self._setup_tmpdir(["a.txt", "b.txt"])
        files = action._find_files(tmpdir)
        assert sorted(files) == sorted(
            [
                os.path.join(tmpdir, "a.txt"),
                os.path.join(tmpdir, "b.txt"),
            ]
        )

    def test_skips_directories(self):
        tmpdir = self._setup_tmpdir(["a.txt", "sub/"])
        files = action._find_files(tmpdir)
        assert files == [os.path.join(tmpdir, "a.txt")]

    def test_skips_broken_symlink(self):
        tmpdir = self._setup_tmpdir(["a.txt"])
        link = os.path.join(tmpdir, "broken_link")
        os.symlink("/nonexistent/path", link)
        files = action._find_files(tmpdir)
        assert files == [os.path.join(tmpdir, "a.txt")]

    def test_hidden_files_excluded_by_glob_default(self):
        # glob.glob does not match hidden files by default
        tmpdir = self._setup_tmpdir(["a.txt", ".hidden"])
        files = action._find_files(tmpdir)
        assert os.path.join(tmpdir, ".hidden") not in files
        assert files == [os.path.join(tmpdir, "a.txt")]

    def test_nested_hidden_file_excluded(self):
        tmpdir = self._setup_tmpdir(["sub/", "sub/.hidden"])
        files = action._find_files(tmpdir)
        assert os.path.join(tmpdir, "sub", ".hidden") not in files

    def test_no_match(self):
        tmpdir = self._setup_tmpdir(["a.txt"])
        files = action._find_files(os.path.join(tmpdir, "nonexistent"))
        assert files == []

    def test_sorted_output(self):
        tmpdir = self._setup_tmpdir(["z.txt", "a.txt", "m.txt"])
        files = action._find_files(tmpdir)
        assert files == sorted(files)


class TestComputeRoot:
    def test_single_file_exact_match(self):
        # When search_path points directly to a single file,
        # root should be its parent directory
        root = action._compute_root("/tmp/foo.txt", ["/tmp/foo.txt"])
        assert root == "/tmp"

    def test_single_file_glob_pattern(self):
        # A glob pattern that matches a single file uses the file's parent
        # directory as the root, not the pattern itself
        root = action._compute_root("/tmp/*.txt", ["/tmp/foo.txt"])
        assert root == "/tmp"

    def test_multiple_files_glob_pattern(self):
        root = action._compute_root("/tmp/*.txt", ["/tmp/a.txt", "/tmp/b.txt"])
        assert root == "/tmp"

    def test_nested_glob_pattern(self):
        # The longest common ancestor of the matched parent directories
        # is used so relative paths never contain '..'
        root = action._compute_root("/tmp/**", ["/tmp/a/x.txt", "/tmp/b/y.txt"])
        assert root == "/tmp"

    def test_empty_files(self):
        root = action._compute_root("/tmp/*.txt", [])
        assert root == "/tmp/*.txt"

    def test_multiple_files(self):
        root = action._compute_root("/tmp", ["/tmp/a.txt", "/tmp/b.txt"])
        assert root == "/tmp"

    def test_single_non_matching_file(self):
        root = action._compute_root("/tmp", ["/tmp/foo.txt"])
        # os.path.normpath("/tmp") == "/tmp", os.path.normpath("/tmp/foo.txt") == "/tmp/foo.txt"
        # They differ, so root is search_path
        assert root == "/tmp"


class TestWriteDesktopFile:
    def test_creates_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bin", delete=False) as f:
            f.write("data")
            filepath = f.name

        try:
            action._write_desktop_file(filepath, "http://example.com/file.bin")
            desktop_path = filepath + ".desktop"
            assert os.path.exists(desktop_path)
            content = Path(desktop_path).read_text()
            assert content == "[Desktop Entry]\nType=Link\nURL=http://example.com/file.bin"
        finally:
            for p in (filepath, filepath + ".desktop"):
                if os.path.exists(p):
                    os.remove(p)


class TestRemoveFile:
    def test_removes_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = f.name
        assert os.path.exists(filepath)
        action._remove_file(filepath)
        assert not os.path.exists(filepath)


class TestUploadFile:
    @staticmethod
    def _mock_response(status: int, headers: dict):
        resp = MagicMock()
        resp.status = status
        resp.headers = headers
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_successful_upload(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello")
            filepath = f.name

        try:
            resp = self._mock_response(
                201, {"content-location": "http://example.com/file.bin"}
            )
            with patch("urllib.request.urlopen", return_value=resp) as mock_urlopen:
                url = action._upload_file("http://api", "my-artifact", filepath, "/tmp", "Bearer token")
            assert url == "http://example.com/file.bin"
            req = mock_urlopen.call_args[0][0]
            assert req.full_url == f"http://api/artifact/my-artifact/{os.path.basename(filepath)}"
            assert req.get_method() == "PUT"
            assert req.get_header("Authorization") == "Bearer token"
        finally:
            os.remove(filepath)

    def test_non_201_status_raises(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello")
            filepath = f.name

        try:
            http_error = urllib.error.HTTPError(
                "http://api/artifact/my-artifact/file.bin",
                500,
                "Internal Server Error",
                {},
                io.BytesIO(b"error"),
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                with pytest.raises(SystemExit) as exc_info:
                    action._upload_file("http://api", "my-artifact", filepath, "/tmp", "Bearer token")
            assert exc_info.value.code == 1
        finally:
            os.remove(filepath)

    def test_missing_content_location_raises(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello")
            filepath = f.name

        try:
            resp = self._mock_response(201, {})
            with patch("urllib.request.urlopen", return_value=resp):
                with pytest.raises(SystemExit) as exc_info:
                    action._upload_file("http://api", "my-artifact", filepath, "/tmp", "Bearer token")
            assert exc_info.value.code == 1
        finally:
            os.remove(filepath)

    def test_relative_path_computed_correctly(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"hello")
            filepath = f.name

        try:
            resp = self._mock_response(
                201, {"content-location": "http://example.com/file.bin"}
            )
            with patch("urllib.request.urlopen", return_value=resp) as mock_urlopen:
                action._upload_file("http://api", "my-artifact", filepath, "/tmp", "Bearer token")
            req = mock_urlopen.call_args[0][0]
            # URL should use the relative path of the file under /tmp
            assert os.path.basename(filepath) in req.full_url
        finally:
            os.remove(filepath)
