"""Regression coverage for automatic and prebuilt Resource Manager packages.

These tests use only the standard library and local source files. Package
prefilling runs against an in-memory fixture, independently of release refreshes.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
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


def group_lines(schema, title):
    groups = schema.split("\nvariableGroups:\n", 1)[1].split("\nvariables:", 1)[0]
    lines = groups.splitlines()
    start = lines.index("  - title: {}".format(title)) + 1
    result = []
    for line in lines[start:]:
        if line.startswith("  - title:"):
            break
        result.append(line)
    return result


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

    def test_normal_pool_enrollment_defaults_to_discovery_without_a_required_map(self):
        schema = (ROOT / SCHEMA_PATH).read_text(encoding="utf-8")
        self.assertEqual(group_lines(schema, "Pool enrollment"), [
            "    variables: [auto_discover_pools, default_pool_max_size, scope_id]",
        ])
        self.assertIs(default_value(schema, "auto_discover_pools"), True)
        self.assertEqual(default_value(schema, "default_pool_max_size"), 3)
        self.assertIn("    visible: ${auto_discover_pools}", variable_lines(schema, "default_pool_max_size"))
        self.assertEqual(default_value(schema, "scope_id"), "")
        self.assertIn("    required: false", variable_lines(schema, "scope_id"))

    def test_advanced_pool_groups_follow_mode_and_overrides_start_empty(self):
        schema = (ROOT / SCHEMA_PATH).read_text(encoding="utf-8")
        manual = group_lines(schema, "Advanced manual enrollment")
        self.assertIn("    visible:", manual)
        self.assertIn('      not: ["${auto_discover_pools}"]', manual)
        self.assertIn("    variables: [pools]", manual)
        self.assertIn("    required: true", variable_lines(schema, "pools"))
        overrides = group_lines(schema, "Advanced discovery overrides")
        self.assertIn("    visible: ${auto_discover_pools}", overrides)
        self.assertIn("    variables: [pool_overrides]", overrides)
        self.assertEqual(default_value(schema, "pool_overrides"), {})
        self.assertIn("    required: false", variable_lines(schema, "pool_overrides"))

    def test_form_variables_match_terraform_and_override_attributes_remain_optional(self):
        schema = (ROOT / SCHEMA_PATH).read_text(encoding="utf-8")
        terraform = (ROOT / "deploy/reference/variables.tf").read_text(encoding="utf-8")
        declared = set(re.findall(r'^variable "([A-Za-z0-9_]+)"', terraform, re.MULTILINE))
        groups = schema.split("\nvariableGroups:\n", 1)[1].split("\nvariables:", 1)[0]
        for line in groups.splitlines():
            if line.startswith("    variables: ["):
                for name in line.split("[", 1)[1].rstrip("]").split(", "):
                    self.assertIn(name, declared)
                    self.assertTrue(variable_lines(schema, name))
        self.assertIn("    valueType: pool_override_entry", variable_lines(schema, "pool_overrides"))
        self.assertIn("    attributes: [pool_override_worker_type, pool_override_max_size]",
                      variable_lines(schema, "pool_override_entry"))
        for schema_name, actual_name, field_type in (
            ("pool_override_worker_type", "worker_type", "string"),
            ("pool_override_max_size", "max_size", "number"),
        ):
            lines = variable_lines(schema, schema_name)
            self.assertIn("    actualName: " + actual_name, lines)
            self.assertIn("    type: " + field_type, lines)
            self.assertIn("    required: false", lines)
            self.assertIn("    visible: false", lines)
            self.assertRegex(terraform, actual_name + r"\s*=\s*optional\(" + field_type + r"\)")

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
