terraform {
  # OCI Resource Manager currently runs Terraform 1.5.7. Keep this module in
  # the supported 1.5.x line rather than accepting an unselectable newer CLI.
  required_version = ">= 1.5.0, < 1.6.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "= 8.29.0"
    }
  }
}

# Authentication comes from the operator's OCI profile or workload identity.
# Never put OCI API private keys in Terraform variables. The optional registry
# auth token is a sensitive stack input, passed only to the image-build helper.
provider "oci" {
  region = var.region
}
