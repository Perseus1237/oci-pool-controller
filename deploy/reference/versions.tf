terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "= 8.29.0"
    }
  }
}

# Authentication comes from the operator's OCI profile or workload identity.
# Never put API private keys or registry passwords in Terraform variables.
provider "oci" {
  region = var.region
}
