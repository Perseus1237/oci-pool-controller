# Resource Manager includes Docker. Building during Apply keeps the generic
# GitHub Deploy button self-contained; no local image build or DevOps project.
locals {
  function_source_dir = abspath("${path.module}/../../function")
  function_source_hash = sha256(join("", concat(
    [for name in ["Dockerfile", "func.py", "requirements.txt"] : filesha256("${local.function_source_dir}/${name}")],
    [filesha256("${path.module}/build_function_image.py")]
  )))
  # OCI commercial-region registry endpoint; Functions and OCIR share a region.
  registry_endpoint = "ocir.${var.region}.oci.oraclecloud.com"
  image_repository_url = var.build_function_image ? join("/", [
    local.registry_endpoint,
    data.oci_objectstorage_namespace.current.namespace,
    oci_artifacts_container_repository.function[0].display_name
  ]) : ""
  effective_function_image = var.build_function_image ? "${local.image_repository_url}:build-${terraform_data.function_image_build[0].id}" : trimspace(var.function_image)
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

resource "terraform_data" "function_image_build" {
  count = var.build_function_image ? 1 : 0
  triggers_replace = {
    source_hash   = local.function_source_hash
    repository_id = oci_artifacts_container_repository.function[0].id
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.ocir_username)) > 0 && length(trimspace(var.ocir_auth_token)) > 0
      error_message = "Automatic image builds require an OCI registry username and auth token. No prebuilt image or existing repository is needed."
    }
  }

  provisioner "local-exec" {
    command = "python3 \"${path.module}/build_function_image.py\""
    environment = {
      # A fresh resource ID gives each build attempt a unique tag,
      # including retries after a failed provisioner. No shared digest files.
      POOL_IMAGE               = "${local.image_repository_url}:build-${self.id}"
      POOL_REGISTRY            = local.registry_endpoint
      POOL_OCIR_USERNAME       = "${data.oci_objectstorage_namespace.current.namespace}/${trimspace(var.ocir_username)}"
      POOL_OCIR_AUTH_TOKEN     = var.ocir_auth_token
      POOL_FUNCTION_SOURCE_DIR = local.function_source_dir
    }
  }
}
