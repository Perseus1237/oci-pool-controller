output "function_ocid" {
  value = oci_functions_function.controller.id
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
  description = "Reviewed server-owned registry. Terraform does not retag or resize these pools."
  value       = local.profiles
}
