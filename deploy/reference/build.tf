resource "oci_ons_notification_topic" "build" {
  count          = var.build_function_image ? 1 : 0
  compartment_id = var.controller_compartment_ocid
  name           = "${var.name_prefix}-build-${local.suffix}"
  description    = "Controller build project events; no subscriptions created"
  freeform_tags  = local.tags
}

resource "oci_devops_project" "function" {
  count          = var.build_function_image ? 1 : 0
  compartment_id = var.controller_compartment_ocid
  name           = "${var.name_prefix}-build-${local.suffix}"
  description    = "Native x86 controller image builds only"
  notification_config { topic_id = oci_ons_notification_topic.build[0].id }
  freeform_tags = local.tags
}

resource "oci_devops_repository" "function" {
  count           = var.build_function_image ? 1 : 0
  project_id      = oci_devops_project.function[0].id
  name            = "controller-source"
  repository_type = "HOSTED"
  default_branch  = "main"
  description     = "Allowlisted Function and build files from the applied stack"
  freeform_tags   = local.tags
}

resource "oci_devops_build_pipeline" "function" {
  count         = var.build_function_image ? 1 : 0
  project_id    = oci_devops_project.function[0].id
  display_name  = "controller-native-x86"
  freeform_tags = local.tags
  build_pipeline_parameters {
    items {
      name          = "POOL_SOURCE_SHA256"
      default_value = jsonencode(local.function_source_checksums)
      description   = "Exact Function source checksums from the Terraform package"
    }
  }
}

resource "oci_devops_deploy_artifact" "function" {
  count                      = var.build_function_image ? 1 : 0
  project_id                 = oci_devops_project.function[0].id
  display_name               = "controller-image"
  deploy_artifact_type       = "DOCKER_IMAGE"
  argument_substitution_mode = "SUBSTITUTE_PLACEHOLDERS"
  deploy_artifact_source {
    deploy_artifact_source_type = "OCIR"
    image_uri                   = "${local.image_repository_url}:$${CONTROLLER_IMAGE_TAG}"
  }
  freeform_tags = local.tags
}

resource "oci_logging_log" "build" {
  count         = var.build_function_image ? 1 : 0
  display_name  = "${var.name_prefix}-build"
  log_group_id  = oci_logging_log_group.controller.id
  log_type      = "SERVICE"
  is_enabled    = true
  freeform_tags = local.tags
  configuration {
    compartment_id = var.controller_compartment_ocid
    source {
      category    = "all"
      resource    = oci_devops_project.function[0].id
      service     = "devops"
      source_type = "OCISERVICE"
    }
  }
}

resource "oci_identity_dynamic_group" "build" {
  provider       = oci.home
  count          = var.build_function_image && var.create_build_iam_resources ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-build-${local.suffix}"
  description    = "Only this controller image build pipeline"
  matching_rule  = "ALL {resource.type = 'devopsbuildpipeline', resource.id = '${oci_devops_build_pipeline.function[0].id}'}"
}

locals {
  build_policy_statements = var.build_function_image ? [
    "Allow dynamic-group ${var.name_prefix}-build-${local.suffix} to read devops-repository in compartment id ${var.controller_compartment_ocid} where target.repository.id = '${oci_devops_repository.function[0].id}'",
    "Allow dynamic-group ${var.name_prefix}-build-${local.suffix} to read devops-deploy-artifact in compartment id ${var.controller_compartment_ocid} where target.artifact.id = '${oci_devops_deploy_artifact.function[0].id}'",
    "Allow dynamic-group ${var.name_prefix}-build-${local.suffix} to manage repos in compartment id ${var.registry_compartment_ocid} where all {target.repo.name = '${oci_artifacts_container_repository.function[0].display_name}', any {request.permission = 'REPOSITORY_READ', request.permission = 'REPOSITORY_UPDATE'}}",
  ] : []
}

resource "oci_identity_policy" "build" {
  provider       = oci.home
  count          = var.build_function_image && var.create_build_iam_resources ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = "${var.name_prefix}-build-${local.suffix}"
  description    = "Build reads its source/artifact and pushes to its private repository; no Compute, Functions or secrets access"
  statements     = local.build_policy_statements
  depends_on     = [oci_identity_dynamic_group.build]
}

resource "oci_devops_build_pipeline_stage" "iam_propagation" {
  count                     = var.build_function_image ? 1 : 0
  build_pipeline_id         = oci_devops_build_pipeline.function[0].id
  build_pipeline_stage_type = "WAIT"
  display_name              = "Allow scoped IAM propagation"
  build_pipeline_stage_predecessor_collection {
    items { id = oci_devops_build_pipeline.function[0].id }
  }
  wait_criteria {
    wait_type     = "ABSOLUTE_WAIT"
    wait_duration = "PT120S"
  }
  freeform_tags = local.tags
}

resource "oci_devops_build_pipeline_stage" "build" {
  count                              = var.build_function_image ? 1 : 0
  build_pipeline_id                  = oci_devops_build_pipeline.function[0].id
  build_pipeline_stage_type          = "BUILD"
  display_name                       = "Build and verify native x86 controller"
  image                              = "OL8_X86_64_STANDARD_10"
  primary_build_source               = "controller"
  build_spec_file                    = "build_spec.yaml"
  stage_execution_timeout_in_seconds = 1800
  build_runner_shape_config { build_runner_type = "DEFAULT" }
  build_pipeline_stage_predecessor_collection {
    items { id = oci_devops_build_pipeline_stage.iam_propagation[0].id }
  }
  build_source_collection {
    items {
      connection_type = "DEVOPS_CODE_REPOSITORY"
      name            = "controller"
      repository_id   = oci_devops_repository.function[0].id
      repository_url  = oci_devops_repository.function[0].http_url
      branch          = "build-${terraform_data.function_image_build[0].id}"
    }
  }
  freeform_tags = local.tags
}

resource "oci_devops_build_pipeline_stage" "deliver" {
  count                     = var.build_function_image ? 1 : 0
  build_pipeline_id         = oci_devops_build_pipeline.function[0].id
  build_pipeline_stage_type = "DELIVER_ARTIFACT"
  display_name              = "Deliver verified x86 image to private OCIR"
  build_pipeline_stage_predecessor_collection {
    items { id = oci_devops_build_pipeline_stage.build[0].id }
  }
  deliver_artifact_collection {
    items {
      artifact_id   = oci_devops_deploy_artifact.function[0].id
      artifact_name = "controller-image"
    }
  }
  freeform_tags = local.tags
}

resource "oci_devops_build_run" "function" {
  count             = var.build_function_image ? 1 : 0
  build_pipeline_id = oci_devops_build_pipeline.function[0].id
  display_name      = "controller-${substr(local.function_source_hash, 0, 12)}"
  build_run_arguments {
    items {
      name  = "POOL_SOURCE_SHA256"
      value = jsonencode(local.function_source_checksums)
    }
  }
  freeform_tags = local.tags
  lifecycle {
    replace_triggered_by = [terraform_data.function_image_build]
    postcondition {
      condition     = self.state == "SUCCEEDED"
      error_message = "The x86 image build/delivery did not succeed. Review its DevOps log before retrying; no Function may use a failed build."
    }
  }
  timeouts { create = "45m" }
  depends_on = [oci_devops_build_pipeline_stage.deliver, oci_identity_policy.build, oci_logging_log.build]
}
