# Existing-pool reference deployment

This staging module deploys the **0.12.0-rc.1 controller**, not the demo tenancy. It creates one OCI Function/application, a dedicated private versioned Object Storage ledger, the initial aggregate lease object, invocation logging, and optionally narrowly scoped IAM resources. It does **not** create, import, resize or retag any instance pool, worker, instance configuration, network, registry, API Gateway, UI, worker terminator or readiness Function.

This is unsupported sample code; see [DISCLAIMER.md](../../DISCLAIMER.md),
[LICENSE.txt](../../LICENSE.txt), and [NOTICE.md](../../NOTICE.md). `0.12.0-rc.1` introduces
generic naming and `workerType` metadata while retaining scaling/retirement safeguards.

### Existing deployment migration

The Terraform pool map now uses `worker_type`, which is serialized as
`workerType` in `SCALE_TEST_PROFILES_JSON` and returned by pool status. Update
your input mapping and status consumers together; the previous customized
metadata field is not accepted as a substitute. Scale requests and retirement
actions retain their existing fields.

The default `name_prefix` is now `oci-pool-controller`. For an existing
deployment, explicitly retain its current prefix, `scope_id`, pool keys/OCIDs
and ledger configuration when required to avoid resource replacement or lost
ownership. Never reset generations or retirement records for a naming change.
Review the exact Terraform plan and test a compatible upgrade in staging.
This module is not an automatic migration of existing lab infrastructure.

Build the accompanying Function source using the controller Dockerfile; do not substitute a historical demo image. Deploy and test this candidate in operator staging before promotion. Worker readiness in this package remains a diagnostic bootstrap proxy. Your platform retains its own registration and dispatch readiness authority.

## 1. Prerequisites and ownership

- Review the [integration overview](../../README.md), [client example](../../examples/README.md), and [operations runbook](../../docs/RUNBOOK.md) before deployment.
- Provide an existing OCI compartment containing the enrolled pools, their immutable instance configurations and workers, plus an existing Function subnet. One controller targets one pool compartment and region. Use a dedicated staging worker compartment where practical.
- Provide a private operator-owned OCIR repository and reviewed image digest. The Functions application architecture must match the image (`GENERIC_ARM` / `linux/arm64` by default). Intel **worker** architecture is independent of the Function runtime architecture.
- The existing Function subnet must have DNS and outbound connectivity to the regional OCI APIs and Object Storage. Its routing, service/NAT gateways, security lists/NSGs and available IPs are the operator's responsibility. This module does not make an invocation endpoint private merely by using a private subnet.
- Have the tenancy administrator review FaaS image/network access, controller resource-principal permissions, caller permissions, and OCI service limits. Cross-compartment images, volumes, VNICs, subnets, encryption keys or other custom launch dependencies may require additional **reviewed** permissions not inferred by this module.
- Store Terraform state and plans in the operator's access-controlled, encrypted backend with locking and backups. No backend is assumed here; the default is local state. Never send populated `.tfvars`, state, plan files or credentials back with the source.

## 2. Enroll an existing staging pool

Terraform deliberately leaves enrollment to your platform's existing infrastructure owner. For every `pools` entry, review all of the following before sending a mutation:

| Resource | Required contract |
| --- | --- |
| Pool | Exact configured `pool_id`, `pool_name`, region and pool compartment; `HarnessId = scope_id` and `ScaleTestProfile = map key`. |
| Instance configuration | Same compartment and both enrollment tags; its launch details must match the registered Intel shape, OCPUs and memory. |
| Launch details | Both enrollment tags and exact free-form `InstanceTerminationProtectionEnabled = "1"` so new workers are protected. |
| Existing worker | Same compartment, correct membership and enrollment tags; protected unless your platform has irrevocably finished retirement preparation. |

Pool OCIDs are pinned in the Function-owned registry. Client input cannot expand the allowlist. Do not reuse a profile key for a different pool with an existing ledger; migration requires review of historical retirement and request records.

Instance configurations are immutable: if the existing launch template is missing required tags or shape settings, your platform creates a replacement configuration through its normal infrastructure workflow and associates it with the staging pool. The controller does not modify operator launch templates. Verify new workers inherit tags. Audit free-form tag capacity for the two enrollment tags and protection flag. Do not silently remove unrelated operator tags.

The inherited enrollment names `HarnessId` and `ScaleTestProfile` are retained for compatibility; they do not require running the demo. `OriginPoolId`, `DrainOperationId` and `DrainRequestedAt` belong to the legacy contrast flow and are not required by the managed retirement path, which records commitments in the ledger. Exact `"0"` commits irrevocable retirement. Boolean `false`, the string `"false"`, missing or malformed protection tags are not equivalent. There is no controller-enforced post-tag grace interval: your platform must stop scheduling and finish any required drain **before** committing `"0"`.

## 3. Build an operator-owned image

From the release root, after security/dependency review:

```sh
export POOL_IMAGE="iad.ocir.io/OCIR_NAMESPACE/OCIR_REPOSITORY:0.12.0-rc.1"
podman build --platform linux/arm64 -f function/Dockerfile -t "$POOL_IMAGE" function
```

Authenticate and push using the operator's approved CI/registry-secret workflow; never copy a demo auth token or pass credentials on a command line. Record the pushed immutable `sha256:` digest and set both `function_image` and `function_image_digest`. Use `linux/amd64` and `GENERIC_X86` together if that is the reviewed runtime choice. Building/pushing an image is not performed by this Terraform module.

## 4. Review configuration and IAM

Copy `terraform.tfvars.example` to local `terraform.tfvars` and replace every placeholder. Keep `dry_run = true` and `enable_termination = false` initially. Choose operator-owned pool/profile and aggregate OCPU ceilings from staging budget and service-limit review; raising ceilings does not demonstrate that the controller can sustain that fleet size. Capacity guards remain enabled and include retiring capacity.

The pool registry is currently inline Function configuration. [OCI limits combined Function/application configuration to 4 KB](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionspassingconfigparams-about.htm); this module conservatively rejects serialized configuration at approximately 4,000 bytes, including UTF-8 metadata. Raising `max_profiles` cannot override that service limit. Long pool identifiers/names reduce how many profiles fit. An external registry is not implemented. Separately reviewed, non-overlapping controller shards are an option, but each needs its own scope, ledger and budget allocation—there is no cross-controller aggregate guard. Do not add unreviewed application-level configuration outside Terraform.

IAM creation defaults to **off** (`create_iam_resources = false`). With that setting:

1. The administrator preinstalls the two FaaS statements shown in `main.tf`, replacing the network/registry compartment placeholders. They must exist before creating the Function application/image.
2. Deploy the Function with both safety switches unchanged.
3. Read `terraform output -json iam_review`. Have the administrator create the named dynamic group with the exact Function-OCID matching rule, controller statements and approved caller statements. Allow IAM propagation before testing.
4. If the administrator chooses a different dynamic-group name, set `dynamic_group_name` to that exact name and regenerate the statements. Never attach another resource to the controller's dynamic group.

Alternatively, an authorized tenancy administrator may set `create_iam_resources = true` to create this module's dynamic group and policies. The module does not create caller users, groups, API keys or passwords. Supply only existing approved `invoker_group_ocids`. With no configured groups it creates no caller invocation policy; an administrator can instead provide a reviewed workload-principal policy for the exact Function.

Permissions are bounded to specified compartments, with Object Storage writes limited to this bucket and without object-list/delete authority. Runtime Compute rights are **not individually IAM-bound to each pool OCID**; the code's pinned allowlist is an additional safety boundary. The controller needs pool updates and launch dependencies for scale-out. Targeted detach/delete dependencies are added only when `enable_termination = true`; centrally managed IAM must be updated manually at that point. Custom image/network/volume placement must be reviewed rather than broadening to tenancy-wide `manage all-resources`.

## 5. Deploy dry-run and perform signed checks

### Resource Manager option

Run `python3 scripts/package-reference.py` from the repository root. Upload the
generated `*-resource-manager.zip` to Resource Manager, or use a private deploy
link for the same ZIP. Choose Terraform **1.5.x** and leave the working directory
at the ZIP root. The included schema groups the required variables, pool map,
image configuration and safety controls. No real tenancy values are bundled.

Provide an existing private image and matching digest/architecture, along with
the reviewed infrastructure values. The Resource Manager execution identity
needs permission to create the defined resources; runtime Function IAM is a
separate requirement. Do not put signing keys or registry tokens in variables.

Deselect **Run apply**, create the stack, run a **Plan**, and review it before
applying. A successful plan is not a runtime test. After apply, perform signed
status and dry-run checks below. Do not enroll a pool into a second live writer.
The packaged root configuration is identical to this module; do not manage the
same deployed resources from both local Terraform state and a Resource Manager
stack.

### Local Terraform option

From `deploy/reference`, after configuring the approved Terraform backend and OCI deployer credentials:

```sh
terraform init
terraform fmt -check
terraform validate
terraform plan -out=reference-staging.tfplan
terraform show reference-staging.tfplan
terraform apply reference-staging.tfplan
terraform output function_ocid
terraform output invoke_endpoint
terraform output -json iam_review
```

Review the saved plan: only the Function/application, dedicated ledger/lease, logs and explicitly enabled IAM should be created. There must be **no** worker/pool/network mutation. Protect and dispose of saved plans according to operator policy.

Use the accompanying integration client with the Function OCID and OCI signer. This deployment sets `CONTROLLER_ONLY=true` and `AUTH_MODE=oci_iam`: the OCI InvokeFunction front door verifies the signed caller before dispatch. The application does not trust a caller-supplied `Authorization` header as evidence of OCI identity and requires no shared demo bearer token. A signed direct invocation returns a JSON `{status_code, body}` envelope over successful Function transport; inspect the **business** `status_code`, `body.retryable`, and outcome, not just transport HTTP 200.

Treat any permission to invoke this Function as full controller-operation authority across its enrolled pools. Do not put an unauthenticated gateway or other broadly authorized trigger in front of it, do not grant worker identities invocation rights, and do not expose the raw FDK server. API Gateway/service invocation would act with that service's authority, not automatically the end user's identity. The controller-only mode disables the browser frontend, legacy contrast mutations/reset, worker reclaim, and benchmark readiness mutation routes. Managed protection `"1"` is permitted only before commitment; re-protecting a committed worker is rejected. A control plane hosted outside OCI still needs an approved OCI signing identity and credential lifecycle; its host-platform identity alone does not establish OCI invocation authority.

For IAM syntax and the signed service invocation boundary, see [Oracle's Function access-control documentation](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsrestrictinguseraccess.htm) and [invocation documentation](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsinvokingfunctions.htm). Invocation logs use the OCI Functions `invoke` category as described in [Oracle's logging example](https://docs.oracle.com/en-us/iaas/Content/Logging/Task/functions_eg.htm).

## 6. Controlled cutover

1. Start with one disposable, enrolled staging pool at target zero. Read pool status through the signed client; verify pool identity, immutable template, protected launch tags and configured limits.
2. Submit and inspect a dry-run scale-out request. Dry-run prevents Compute/tag mutations but may create request/coordination ledger records. Use a **new generation and request ID** when making a later live demand change; do not assume a previously completed dry-run request will execute live.
3. Pause the legacy policy writer and, with operator approval, export and remove its attached OCI Autoscaling configuration **for this pool**, then verify absence. A configuration that remains attached is rejected even when disabled. The scheduler remains authoritative for demand; only this controller may mutate pool capacity. Do not leave two resize writers active.
4. Set `dry_run = false` while retaining `enable_termination = false`, review/apply the Function configuration, and test small protected scale-out. Confirm actual platform registration/dispatchability independently.
5. After drain integration acceptance, enable targeted termination through both configuration and IAM, review/apply, then execute the [ordered staging checks](../../docs/RUNBOOK.md). A worker committed for retirement must never receive another job.
6. Use your periodic maintenance loop: send new monotonic generations only for changed demand; retry/replay the identical latest request as needed. Status reads do not advance reconciliation. Request IDs and generations must survive the caller's restart. Scale-out while old workers retire is deliberately retire-first, not surge replacement.

## Stop and rollback

Stop scheduler writes first, set `dry_run=true` and `enable_termination=false`, and apply the reviewed safety-only change. These switches do not cancel an OCI operation already accepted. With centrally managed IAM, revoke detach/delete authority separately when required by the incident procedure. Preserve all ledger versions, desired generations and retirement commitments.

Before switching back to another scaler, reconcile actual OCI membership, committed retirements and latest demand with your platform; never re-protect or reuse committed workers. Do not run two writers during rollback. Pin any rollback image digest and verify that version understands the existing ledger schema and retirement semantics; old demo versions are not a safe generic downgrade.

`terraform destroy` is **not worker drain or safe rollback**: this module does not own workers, and the ledger/lease have `prevent_destroy` guards. Removing those guards, deleting state, recreating the ledger or importing another environment's state requires an explicit retention/migration review. Retain operator operational records; no automated history pruning is supplied.
