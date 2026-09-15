"""Verify image-build boundaries without contacting Docker or an OCI tenancy."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "deploy/reference/build_function_image.py"
SPEC = importlib.util.spec_from_file_location("resource_manager_image_build", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ImageBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name)
        for filename in builder.SOURCE_FILES:
            (self.source / filename).write_text("test fixture\n", encoding="utf-8")
        (self.source / ".env").write_text("DO_NOT_COPY=secret\n", encoding="utf-8")
        (self.source / "untracked.txt").write_text("not Function source\n", encoding="utf-8")
        self.token = "unit-test-registry-token"
        self.environment = {
            "POOL_IMAGE": "iad.ocir.io/testnamespace/controller:source-123",
            "POOL_REGISTRY": "iad.ocir.io",
            "POOL_OCIR_USERNAME": "testnamespace/default/operator@example.com",
            "POOL_OCIR_AUTH_TOKEN": self.token,
            "POOL_FUNCTION_SOURCE_DIR": str(self.source),
            "PATH": "/usr/bin:/bin",
            "TF_VAR_ocir_auth_token": self.token,
            "OCI_CLI_KEY_CONTENT": "another-secret",
            "DOCKER_CONFIG": "/operator/existing/docker-config",
        }
        self.calls = []
        self.temporary_paths = set()

    def fake_docker(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.assertEqual(command[:2], ["docker", "--config"])
        config = Path(command[2])
        self.temporary_paths.add(config.parent)
        self.assertTrue(config.is_dir())
        self.assertEqual(config.stat().st_mode & 0o777, 0o700)
        step = command[3]
        if step == "build":
            context = Path(command[-1])
            self.assertEqual(set(path.name for path in context.iterdir()), set(builder.SOURCE_FILES))
            for filename in builder.SOURCE_FILES:
                self.assertEqual((context / filename).read_bytes(), (self.source / filename).read_bytes())
            self.assertNotIn("--platform", command)
            self.assertNotIn("buildx", command)
        if step == "login":
            (config / "config.json").write_text(self.token, encoding="utf-8")
        output = {"info": "linux/x86_64\n", "image": "linux/amd64\n", "push": "digest: sha256:test\n"}.get(step, "")
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    def run_build(self, side_effect=None):
        with mock.patch.object(builder.subprocess, "run", side_effect=side_effect or self.fake_docker):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                builder.build_and_push(self.environment)

    def assert_cleaned_up(self):
        self.assertTrue(self.temporary_paths)
        for path in self.temporary_paths:
            self.assertFalse(path.exists())

    def test_credentials_are_stdin_only_and_context_is_allowlisted(self):
        self.run_build()
        self.assertEqual([command[3] for command, _ in self.calls], ["info", "build", "image", "login", "push"])
        for command, kwargs in self.calls:
            self.assertNotIn(self.token, " ".join(command))
            self.assertEqual(kwargs["env"], {"PATH": "/usr/bin:/bin"})
            self.assertNotIn("shell", kwargs)
            self.assertIs(kwargs["universal_newlines"], True)
            self.assertEqual(kwargs["stdout"], subprocess.PIPE)
            self.assertEqual(kwargs["stderr"], subprocess.PIPE)
            self.assertEqual(kwargs["input"], self.token + "\n" if command[3] == "login" else None)
        self.assert_cleaned_up()

    def test_non_x86_daemon_fails_before_build_or_login(self):
        def arm_daemon(command, **kwargs):
            result = self.fake_docker(command, **kwargs)
            result.stdout = "linux/aarch64\n"
            return result
        with self.assertRaisesRegex(builder.BuildError, "native linux/amd64"):
            self.run_build(arm_daemon)
        self.assertEqual([command[3] for command, _ in self.calls], ["info"])
        self.assert_cleaned_up()

    def test_wrong_image_architecture_prevents_login_and_push(self):
        def wrong_image(command, **kwargs):
            result = self.fake_docker(command, **kwargs)
            if command[3] == "image":
                result.stdout = "linux/arm64\n"
            return result
        with self.assertRaisesRegex(builder.BuildError, "not linux/amd64"):
            self.run_build(wrong_image)
        self.assertEqual([command[3] for command, _ in self.calls], ["info", "build", "image"])
        self.assert_cleaned_up()

    def test_push_failure_cleans_credentials_and_redacts_output(self):
        def failed_push(command, **kwargs):
            result = self.fake_docker(command, **kwargs)
            if command[3] == "push":
                result.returncode = 1
                result.stderr = "registry rejected " + self.token
            return result
        with self.assertRaises(builder.BuildError) as raised:
            self.run_build(failed_push)
        self.assertIn("Docker push failed", str(raised.exception))
        self.assertNotIn(self.token, str(raised.exception))
        self.assertIn("[redacted]", str(raised.exception))
        self.assert_cleaned_up()

    def test_failed_build_prevents_login_and_push(self):
        def failed_build(command, **kwargs):
            result = self.fake_docker(command, **kwargs)
            if command[3] == "build":
                result.returncode = 1
                result.stderr = "Dockerfile failed"
            return result
        with self.assertRaisesRegex(builder.BuildError, "Docker build failed"):
            self.run_build(failed_build)
        self.assertEqual([command[3] for command, _ in self.calls], ["info", "build"])
        self.assert_cleaned_up()

    def test_image_and_registry_reject_options_or_unmatched_targets(self):
        invalid = (
            ("POOL_IMAGE", "--help"),
            ("POOL_IMAGE", "other.ocir.io/testnamespace/controller:tag"),
            ("POOL_IMAGE", "iad.ocir.io/testnamespace/controller"),
            ("POOL_IMAGE", "iad.ocir.io/testnamespace/controller:tag\n"),
            ("POOL_REGISTRY", "https://iad.ocir.io"),
            ("POOL_REGISTRY", "--help"),
            ("POOL_OCIR_USERNAME", "--help"),
        )
        for name, value in invalid:
            with self.subTest(name=name, value=value):
                environment = dict(self.environment, **{name: value})
                with mock.patch.object(builder.subprocess, "run") as run:
                    with self.assertRaises(builder.BuildError):
                        builder.build_and_push(environment)
                    run.assert_not_called()

    def test_missing_credentials_fail_before_docker(self):
        del self.environment["POOL_OCIR_AUTH_TOKEN"]
        with mock.patch.object(builder.subprocess, "run") as run:
            with self.assertRaisesRegex(builder.BuildError, "POOL_OCIR_AUTH_TOKEN"):
                builder.build_and_push(self.environment)
            run.assert_not_called()

    def test_source_symlink_is_rejected(self):
        (self.source / "func.py").unlink()
        (self.source / "func.py").symlink_to(self.source / ".env")
        with mock.patch.object(builder.subprocess, "run") as run:
            with self.assertRaisesRegex(builder.BuildError, "regular func.py"):
                builder.build_and_push(self.environment)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
