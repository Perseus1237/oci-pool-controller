#!/usr/bin/env python3
"""Build and push the Function during an OCI Resource Manager apply.

The Terraform caller supplies POOL_IMAGE, POOL_REGISTRY, POOL_OCIR_USERNAME,
POOL_OCIR_AUTH_TOKEN and POOL_FUNCTION_SOURCE_DIR in the environment. Registry
credentials go only to Docker login's standard input and temporary config.
This uses Docker 19-compatible commands and the native x86 Resource Manager
worker; no Docker Buildx plugin or emulation is required.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


SOURCE_FILES = ("Dockerfile", "func.py", "requirements.txt")
# Preserve only what Docker needs to find its daemon and reach registries.
# In particular, Terraform variables and OCI credentials must not reach builds.
DOCKER_ENV_KEYS = (
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_API_VERSION",
)


class BuildError(Exception):
    """An input, build, or registry operation prevented deployment."""


def required(environment, name):
    value = environment.get(name, "")
    if not value or any(character in value for character in "\x00\r\n"):
        raise BuildError("{} must be provided without control characters".format(name))
    return value


def configuration(environment):
    registry = required(environment, "POOL_REGISTRY")
    image = required(environment, "POOL_IMAGE")
    username = required(environment, "POOL_OCIR_USERNAME")
    token = required(environment, "POOL_OCIR_AUTH_TOKEN")
    source_value = required(environment, "POOL_FUNCTION_SOURCE_DIR")
    hostname = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    if not re.fullmatch(hostname + r"(?:\." + hostname + r")+", registry):
        raise BuildError("POOL_REGISTRY must be a registry hostname without a URL scheme")
    component = r"[a-z0-9][a-z0-9._-]*"
    tagged_path = component + r"(?:/" + component + r")+:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"
    if not image.startswith(registry + "/") or not re.fullmatch(
        tagged_path, image[len(registry) + 1:]
    ):
        raise BuildError("POOL_IMAGE must name this registry, namespace, repository and tag")
    if username.startswith("-") or any(character.isspace() for character in username):
        raise BuildError("POOL_OCIR_USERNAME must be a complete OCIR username without whitespace")
    try:
        source = Path(source_value).resolve(strict=True)
    except (OSError, RuntimeError):
        raise BuildError("POOL_FUNCTION_SOURCE_DIR does not resolve to an existing directory")
    if not source.is_dir():
        raise BuildError("POOL_FUNCTION_SOURCE_DIR must be a directory")
    for filename in SOURCE_FILES:
        path = source / filename
        if path.is_symlink() or not path.is_file():
            raise BuildError("Function source must contain a regular {} file".format(filename))
    return registry, image, username, token, source


def build_and_push(environment=None):
    environment = os.environ if environment is None else environment
    registry, image, username, token, source = configuration(environment)
    docker_environment = {
        key: environment[key] for key in DOCKER_ENV_KEYS
        if key in environment and token not in environment[key]
    }

    with tempfile.TemporaryDirectory(prefix="oci-pool-function-build-") as temporary:
        root = Path(temporary)
        config = root / "docker-config"
        context = root / "context"
        config.mkdir(mode=0o700)
        context.mkdir(mode=0o700)
        for filename in SOURCE_FILES:
            shutil.copyfile(source / filename, context / filename)

        def docker(arguments, stdin=None, display=True):
            command = ["docker", "--config", str(config)] + arguments
            try:
                result = subprocess.run(
                    command, input=stdin, universal_newlines=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=docker_environment, check=False,
                )
            except OSError as error:
                raise BuildError("Unable to start Docker: {}".format(str(error).replace(token, "[redacted]")))
            stdout = (result.stdout or "").replace(token, "[redacted]")
            stderr = (result.stderr or "").replace(token, "[redacted]")
            if result.returncode:
                raise BuildError("Docker {} failed (exit {}): {}".format(
                    arguments[0], result.returncode, (stderr or stdout).strip()
                ))
            if display:
                if stdout:
                    print(stdout, end="" if stdout.endswith("\n") else "\n")
                if stderr:
                    print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
            return stdout.strip()

        daemon_platform = docker(["info", "--format", "{{.OSType}}/{{.Architecture}}"], display=False)
        if daemon_platform not in ("linux/amd64", "linux/x86_64"):
            raise BuildError("The automatic Function build requires a native linux/amd64 Docker daemon")
        print("Building Function image for linux/amd64.", flush=True)
        # Docker 19 gates --platform behind experimental/BuildKit support.
        # The native daemon check above and image check below enforce x86
        # without requiring those optional features on the RM worker.
        docker([
            "build", "--file", str(context / "Dockerfile"), "--tag", image, str(context),
        ])
        image_platform = docker([
            "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", image,
        ], display=False)
        if image_platform != "linux/amd64":
            raise BuildError("Built Function image is not linux/amd64; registry push was cancelled")
        docker(["login", "--username", username, "--password-stdin", registry], stdin=token + "\n")
        docker(["push", image])
        print("Function image pushed successfully; OCI Functions will resolve its immutable digest.")


def main():
    try:
        build_and_push()
    except (BuildError, OSError) as error:
        # Also redact errors originating from filesystem operations.
        message = str(error)
        token = os.environ.get("POOL_OCIR_AUTH_TOKEN")
        if token:
            message = message.replace(token, "[redacted]")
        print("Function image build failed: {}".format(message), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
