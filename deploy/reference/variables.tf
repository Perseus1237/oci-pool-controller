variable "region" {
  description = "Region containing every enrolled pool and the controller."
  type        = string
}

variable "tenancy_ocid" {
  type = string
}

variable "controller_compartment_ocid" {
  description = "Compartment for the Function, ledger and logs. No worker resources are created."
  type        = string
}

variable "pool_compartment_ocid" {
  description = "Single existing compartment containing all enrolled pools, configurations and workers."
  type        = string
}

variable "network_compartment_ocid" {
  description = "Compartment containing existing Function and worker subnets; review IAM if these differ."
  type        = string
}

variable "function_vcn_ocid" {
  description = "Existing VCN containing the selected Function subnets."
  type        = string

  validation {
    condition     = startswith(var.function_vcn_ocid, "ocid1.vcn.")
    error_message = "function_vcn_ocid must be an OCI VCN OCID."
  }
}

variable "registry_compartment_ocid" {
  description = "Compartment containing the operator's existing private OCIR repository."
  type        = string
}

variable "subnet_ids" {
  description = "Existing Function subnet OCIDs with OCI-service connectivity. This module creates no network."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for id in var.subnet_ids : startswith(id, "ocid1.subnet.")])
    error_message = "Supply at least one existing OCI subnet OCID."
  }
}

variable "name_prefix" {
  type    = string
  default = "oci-pool-controller"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_-]{0,39}$", var.name_prefix))
    error_message = "name_prefix must start with a letter and contain at most 40 letters, digits, underscores or hyphens."
  }
}

variable "scope_id" {
  description = "Existing HarnessId enrollment tag; use a distinct ID per controller/environment."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$", var.scope_id))
    error_message = "scope_id must be a non-empty request-ID-compatible identifier."
  }
}

variable "function_image" {
  description = "Operator-owned private OCIR image including tag, built from the accompanying Function source."
  type        = string
}

variable "function_image_digest" {
  description = "Immutable SHA-256 digest of the exact reviewed Function image, not a demo-tenancy image."
  type        = string

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.function_image_digest))
    error_message = "Supply a sha256: digest with 64 lowercase hexadecimal characters."
  }
}

variable "function_shape" {
  description = "Function runtime CPU architecture; must match the image, independent of Intel worker shapes."
  type        = string
  default     = "GENERIC_ARM"

  validation {
    condition     = contains(["GENERIC_ARM", "GENERIC_X86"], var.function_shape)
    error_message = "Choose GENERIC_ARM or GENERIC_X86 to match the built image."
  }
}

variable "pools" {
  description = "Pinned existing-pool allowlist. Terraform reads each pool and immutable launch configuration to derive its name, Intel shape, OCPUs and memory; keys must match each pool/configuration/worker ScaleTestProfile tag."
  type = map(object({
    pool_id     = string
    worker_type = string
    max_size    = number
  }))

  validation {
    condition = length(var.pools) > 0 && alltrue([
      for key, pool in var.pools : can(regex("^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$", key)) &&
      startswith(pool.pool_id, "ocid1.instancepool.") && length(pool.worker_type) > 0 &&
      pool.max_size >= 1 && floor(pool.max_size) == pool.max_size
    ])
    error_message = "Each entry must pin an existing pool, include worker_type and use a positive integer max_size."
  }

  validation {
    condition     = length(distinct([for pool in values(var.pools) : pool.pool_id])) == length(var.pools)
    error_message = "A pool OCID may be enrolled only once."
  }
}

variable "max_profiles" {
  description = "Explicit controller registry ceiling; raising it is not a validated throughput claim."
  type        = number
  default     = 6

  validation {
    condition     = var.max_profiles >= 1 && floor(var.max_profiles) == var.max_profiles
    error_message = "max_profiles must be a positive integer."
  }
}

variable "max_pool_size" {
  description = "Maximum configured size for any enrolled profile. Start small in staging."
  type        = number
  default     = 50

  validation {
    condition     = var.max_pool_size >= 1 && floor(var.max_pool_size) == var.max_pool_size
    error_message = "max_pool_size must be a positive integer."
  }
}

variable "max_active_pools" {
  description = "Aggregate operational ceiling on simultaneously active enrolled pools."
  type        = number
  default     = 1

  validation {
    condition     = var.max_active_pools >= 1 && floor(var.max_active_pools) == var.max_active_pools
    error_message = "max_active_pools must be a positive integer."
  }
}

variable "max_total_ocpus" {
  description = "Aggregate operational OCPU ceiling, including retiring capacity; not an OCI quota reservation."
  type        = number
  default     = 16

  validation {
    condition     = var.max_total_ocpus >= 1 && floor(var.max_total_ocpus) == var.max_total_ocpus
    error_message = "max_total_ocpus must be a positive integer."
  }
}

variable "dry_run" {
  description = "Safe initial mode. Inspect proposed behavior without Compute mutation; ledger/status activity still occurs."
  type        = bool
  default     = true
}

variable "enable_termination" {
  description = "Separate targeted-termination kill switch. Enable only after worker-drain and IAM acceptance."
  type        = bool
  default     = false
}

variable "create_iam_resources" {
  description = "Opt in to tenancy-level group/policy creation; otherwise send IAM outputs to the operator's administrator."
  type        = bool
  default     = false
}

variable "dynamic_group_name" {
  description = "Optional administrator-chosen name for the controller-only dynamic group."
  type        = string
  default     = null

  validation {
    condition     = var.dynamic_group_name == null ? true : can(regex("^[A-Za-z][A-Za-z0-9_-]{0,99}$", var.dynamic_group_name))
    error_message = "Use a simple dynamic group name without whitespace or policy syntax."
  }
}

variable "invoker_group_ocids" {
  description = "Existing OCI groups permitted to invoke this exact Function. These callers have full controller authority."
  type        = set(string)
  default     = []

  validation {
    condition     = alltrue([for id in var.invoker_group_ocids : can(regex("^ocid1.group.[A-Za-z0-9._-]+$", id))])
    error_message = "invoker_group_ocids must contain OCI group OCIDs."
  }
}

variable "ledger_bucket_name" {
  description = "Optional dedicated private ledger bucket name; cannot be shared by unrelated controllers."
  type        = string
  default     = null

  validation {
    condition     = var.ledger_bucket_name == null ? true : can(regex("^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$", var.ledger_bucket_name))
    error_message = "Use a request-ID-compatible dedicated bucket name."
  }
}
