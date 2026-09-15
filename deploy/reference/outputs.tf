output "function_ocid" {
  value = oci_functions_function.controller.id
}

output "function_image" {
  description = "Deployed OCIR image address; automatically generated in source-build mode."
  value       = oci_functions_function.controller.image
}

output "function_image_digest" {
  description = "Immutable image digest resolved by OCI Functions for the deployed image."
  value       = oci_functions_function.controller.image_digest
}

output "invoke_endpoint" {
  description = "OCI-signed Functions endpoint, not a public unauthenticated application URL."
  value       = oci_functions_function.controller.invoke_endpoint
}

output "application_ocid" {
  value = oci_functions_application.controller.id
}

output "log_group_ocid" {
  value = oci_logging_log_group.controller.id
}

output "ledger" {
  value = {
    namespace = oci_objectstorage_bucket.ledger.namespace
    bucket    = oci_objectstorage_bucket.ledger.name
  }
}

output "iam_review" {
  description = "Have the central IAM team apply these when create_iam_resources=false; review dependencies before enabling writes."
  value = {
    dynamic_group_name           = local.dynamic_group_name
    dynamic_group_matching_rule  = local.dynamic_group_matching_rule
    faas_policy_statements       = local.faas_policy_statements
    controller_policy_statements = local.controller_policy_statements
    invoker_policy_statements    = local.invoker_policy_statements
  }
}

output "pool_registry" {
  description = "Exact pinned pool registry to review in every Plan. Terraform does not retag or resize these pools."
  value       = local.profiles
}

output "enrollment_review" {
  description = "Plan-time discovery/manual selection, controller group, included/excluded OCIDs and exact profile limits. New discovery results take effect only through a subsequent Apply."
  value       = merge(module.enrollment.review, { pools = local.profiles })
}
