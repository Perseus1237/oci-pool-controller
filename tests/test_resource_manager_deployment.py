"""Regression coverage for automatic and prebuilt Resource Manager packages.

These tests use only the standard library and local source files. Package
prefilling runs against an in-memory fixture, independently of release refreshes.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_reference", ROOT / "scripts/package-reference.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)
SCHEMA_PATH = "deploy/reference/schema.yaml"


def variable_lines(schema, name):
    """Read one variable block from the repository's two-space YAML layout."""
    variables = schema.split("\nvariables:\n", 1)[1].split("\noutputs:", 1)[0]
    lines = variables.splitlines()
    start = lines.index("  {}:".format(name)) + 1
    result = []
    for line in lines[start:]:
        if line.startswith("  ") and not line.startswith("   "):
            break
        result.append(line)
    return result


def default_value(schema, name):
    defaults = [line[len("    default: "):] for line in variable_lines(schema, name)
                if line.startswith("    default: ")]
    if len(defaults) != 1:
        raise AssertionError("Expected exactly one default for {}".format(name))
    return json.loads(defaults[0])


class ResourceManagerDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "function_image": "iad.ocir.io/testnamespace/controller:release-1",
            "function_image_digest": "sha256:" + "a" * 64,
            "function_shape": "GENERIC_X86",
        }
        schema = b"""schemaVersion: 1.1.0
variables:
  build_function_image:
    type: boolean
    default: true
  function_image:
    type: string
    title: Existing image
  function_image_digest:
    type: string
    required: false
  function_shape:
    type: enum
    default: GENERIC_ARM
outputs:
  function_image:
    type: string
"""
        self.files = {
            SCHEMA_PATH: schema,
            "function/func.py": b"# unchanged source fixture\n",
        }
        manifest = {
            "release": "test-1.0",
            "files": [
                {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in self.files.items()
            ],
        }
        self.files["RELEASE_MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")

    def test_generic_stack_builds_automatically_and_hides_manual_image_fields(self):
        schema = (ROOT / SCHEMA_PATH).read_text(encoding="utf-8")
        self.assertIs(default_value(schema, "build_function_image"), True)
        for name in ("function_image", "function_image_digest", "function_shape"):
            with self.subTest(variable=name):
                lines = variable_lines(schema, name)
                self.assertIn("    visible:", lines)
                self.assertIn('      not: ["${build_function_image}"]', lines)
        self.assertIn("    required: false", variable_lines(schema, "function_image_digest"))
        for name in ("ocir_username", "ocir_auth_token"):
            self.assertIn("    visible: ${build_function_image}", variable_lines(schema, name))
        self.assertIn("    type: password", variable_lines(schema, "ocir_auth_token"))

    def test_prefilled_package_selects_existing_image_and_preserves_immutable_pin(self):
        result = package.prefilled_resource_manager_files(self.files, self.values)
        schema = result[SCHEMA_PATH].decode("utf-8")
        self.assertIs(default_value(schema, "build_function_image"), False)
        for name, value in self.values.items():
            self.assertEqual(default_value(schema, name), value)
        self.assertIn("    title: Existing image", variable_lines(schema, "function_image"))
        self.assertIn("    required: false", variable_lines(schema, "function_image_digest"))
        self.assertTrue(schema.endswith("outputs:\n  function_image:\n    type: string\n"))

    def test_prefilled_package_updates_embedded_integrity_and_leaves_source_untouched(self):
        original = dict(self.files)
        result = package.prefilled_resource_manager_files(self.files, self.values)
        self.assertEqual(self.files, original)
        self.assertNotEqual(result[SCHEMA_PATH], original[SCHEMA_PATH])
        self.assertEqual(result["function/func.py"], original["function/func.py"])
        manifest = json.loads(result["RELEASE_MANIFEST.json"])
        for entry in manifest["files"]:
            data = result[entry["path"]]
            self.assertEqual(entry["bytes"], len(data))
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        provenance = json.loads(result["IMAGE_PROVENANCE.json"])
        for name, value in self.values.items():
            self.assertEqual(provenance[name], value)
        self.assertEqual(provenance["source_release"], "test-1.0")

    def test_repeated_prefill_is_stable_and_does_not_duplicate_defaults(self):
        once = package.prefilled_resource_manager_files(self.files, self.values)
        twice = package.prefilled_resource_manager_files(once, self.values)
        self.assertEqual(twice, once)
        schema = twice[SCHEMA_PATH].decode("utf-8")
        self.assertIs(default_value(schema, "build_function_image"), False)
        for name, value in self.values.items():
            self.assertEqual(default_value(schema, name), value)

    def test_prefill_requires_complete_valid_image_pins(self):
        self.assertEqual(package.image_prefill(argparse.Namespace(**self.values)), self.values)
        for replacement in (
            {"function_image_digest": None},
            {"function_image_digest": "sha256:abc"},
            {"function_image": "iad.ocir.io/testnamespace/controller"},
            {"function_shape": "GENERIC_UNKNOWN"},
        ):
            with self.subTest(replacement=replacement):
                values = dict(self.values, **replacement)
                with self.assertRaises(SystemExit):
                    package.image_prefill(argparse.Namespace(**values))

    def test_no_image_prefill_keeps_generic_build_mode(self):
        values = argparse.Namespace(function_image=None, function_image_digest=None, function_shape=None)
        self.assertIsNone(package.image_prefill(values))


if __name__ == "__main__":
    unittest.main()
