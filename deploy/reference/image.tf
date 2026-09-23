# Resource Manager orchestrates a native x86 DevOps build, never a local build.
locals {
  function_source_dir = abspath("${path.module}/../../function")
  function_source_checksums = {
    for name in ["Dockerfile", "func.py", "requirements.txt"] : name => filesha256("${local.function_source_dir}/${name}")
  }
  function_source_hash = sha256(join("", concat(
    [for name in sort(keys(local.function_source_checksums)) : local.function_source_checksums[name]],
    [for name in ["publish_build_source.py", "native_build.py", "build_spec.yaml"] : filesha256("${path.module}/${name}")]
  )))
  # OCI commercial-region registry endpoint; Functions and OCIR share a region.
  registry_endpoint = "ocir.${var.region}.oci.oraclecloud.com"
  image_repository_url = var.build_function_image ? join("/", [
    local.registry_endpoint,
    data.oci_objectstorage_namespace.current.namespace,
    oci_artifacts_container_repository.function[0].display_name
  ]) : ""
  delivered_image = var.build_function_image ? try(one([
    for artifact in oci_devops_build_run.function[0].build_outputs[0].delivered_artifacts[0].items : artifact
    if artifact.output_artifact_name == "controller-image"
  ]), null) : null
  effective_function_image = var.build_function_image ? try(local.delivered_image.image_uri, "") : trimspace(var.function_image)
  effective_image_digest   = var.build_function_image ? try(local.delivered_image.delivered_artifact_hash, null) : (var.function_image_digest == "" ? null : var.function_image_digest)
  effective_function_shape = var.build_function_image ? "GENERIC_X86" : var.function_shape
}

resource "oci_artifacts_container_repository" "function" {
  count          = var.build_function_image ? 1 : 0
  compartment_id = var.registry_compartment_ocid
  display_name   = "${lower(replace(var.name_prefix, "_", "-"))}-${local.suffix}/function"
  is_public      = false
  # Do not set is_immutable: OCIR can reject this optional API property even
  # though the provider exposes it. Privacy and deletion protection are separate.
  freeform_tags = local.tags

  # The deployed Function may still reference this repository when changing
  # deployment modes. Never delete its images as a side effect of that switch.
  lifecycle {
    prevent_destroy = true
  }
}

# Preserve this address for upgrades; it now publishes source, not an image.
resource "terraform_data" "function_image_build" {
  count = var.build_function_image ? 1 : 0
  triggers_replace = {
    source_hash       = local.function_source_hash
    repository_id     = oci_artifacts_container_repository.function[0].id
    source_repository = oci_devops_repository.function[0].id
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.ocir_username)) > 0 && length(trimspace(var.ocir_auth_token)) > 0
      error_message = "Automatic builds require an OCI username and auth token to publish source to the private OCI code repository. The build runner never receives this token."
    }
  }

  provisioner "local-exec" {
    command = "python3 \"${path.module}/publish_build_source.py\""
    environment = {
      POOL_SOURCE_REPOSITORY   = oci_devops_repository.function[0].http_url
      POOL_SOURCE_BRANCH       = "build-${self.id}"
      POOL_SOURCE_USERNAME     = "${data.oci_identity_tenancy.current.name}/${trimspace(var.ocir_username)}"
      POOL_SOURCE_AUTH_TOKEN   = var.ocir_auth_token
      POOL_FUNCTION_SOURCE_DIR = local.function_source_dir
    }
  }
}
