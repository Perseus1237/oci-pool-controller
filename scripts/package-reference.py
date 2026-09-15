#!/usr/bin/env python3
"""Build reviewed source and Resource Manager artifacts; never upload or deploy.

Only manifest-listed files are eligible. The Resource Manager ZIP preserves
the source layout, so its Terraform working directory is deploy/reference.
Original paths remain available for documentation and CLI usage.
"""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile


RESOURCE_MANAGER_WORKING_DIRECTORY = "deploy/reference"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    version = manifest["release"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]+", version):
        raise SystemExit("Invalid release name")
    files = {}
    for entry in manifest["files"]:
        name = entry["path"]
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise SystemExit(f"Unsafe source path: {name}")
        if name in files or name == "RELEASE_MANIFEST.json":
            raise SystemExit(f"Duplicate/self-referencing manifest entry: {name}")
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"Manifest mismatch: {name}")
        if re.search(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|/p/[A-Za-z0-9_-]{16,}/n/|ocid1\.[a-z]+\.oc1[^\s\"]{45,}", data):
            raise SystemExit(f"Possible credential, PAR or live identifier: {name}")
        files[name] = data
    files["RELEASE_MANIFEST.json"] = manifest_path.read_bytes()
    for name, data in files.items():
        if name.endswith(".md"):
            for link in re.findall(r"\]\(([^)]+)\)", data.decode()):
                if "://" in link or link.startswith("#"):
                    continue
                target = (root / Path(name).parent / link.split("#")[0]).resolve()
                if not target.is_relative_to(root) or target.relative_to(root).as_posix() not in files:
                    raise SystemExit(f"Unpackaged link in {name}: {link}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"oci-pool-controller-{version}"
    tar_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=tar_buffer, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(f"{prefix}/{name}")
                info.size = len(data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
    zip_files = dict(files)
    zip_files["RESOURCE_MANAGER_MANIFEST.json"] = (json.dumps({
        "release": version,
        "working_directory": RESOURCE_MANAGER_WORKING_DIRECTORY,
        "files": [{"path": n, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)} for n, b in sorted(zip_files.items())],
    }, indent=2) + "\n").encode()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(zip_files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    artifacts = {f"{prefix}.tar.gz": tar_buffer.getvalue(), f"{prefix}-resource-manager.zip": zip_buffer.getvalue()}
    for name, data in list(artifacts.items()):
        artifacts[name + ".sha256"] = (hashlib.sha256(data).hexdigest() + "  " + name + "\n").encode()
    for name, data in artifacts.items():
        path = args.output_dir / name
        if path.exists() and path.read_bytes() != data:
            raise SystemExit(f"Refusing to replace differing artifact: {path}; use a new release version")
    for name, data in artifacts.items():
        path = args.output_dir / name
        if not path.exists():
            with path.open("xb") as output:
                output.write(data)
        print(path)


if __name__ == "__main__":
    main()
