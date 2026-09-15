# OCI Pool Controller POC — Reference Implementation

A sample code reference implementation for integrating a scheduler or control plane with
OCI instance pools. It demonstrates durable desired-capacity reconciliation,
per-pool coordination, and explicit retirement of drained workers. Adapt and
validate it for your platform; it is not a production-qualified service.

> **Public-release draft — not approved for external distribution.**
> This clean-history source snapshot is prepared for release review only.
> Complete the [release checklist](RELEASE_CHECKLIST.md) before publishing,
> pushing to an external repository, or distributing source or images.

[![Deploy to Oracle Cloud](https://oci-resourcemanager-plugin.plugins.oci.oraclecloud.com/latest/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https%3A%2F%2Fgithub.com%2FPerseus1237%2Foci-pool-controller%2Farchive%2Frefs%2Fheads%2Fmain.zip&workingDirectory=oci-pool-controller-main%2Fdeploy%2Freference)

**One-click Resource Manager launch:** the button downloads the public `main`
branch archive and opens the OCI Resource Manager **Create stack** form. The
complete Terraform working-directory path in that GitHub archive is exactly
**`oci-pool-controller-main/deploy/reference`**. That directory contains the
Terraform configuration and `schema.yaml`; it is why Resource Manager renders
the deployment inputs instead of treating the repository root as a stack.

The form asks for the controller, pool, network, and OCIR compartments; the
Function VCN and subnet; an OCIR username and auth token; the existing-pool
allowlist; safety limits; IAM options; and the optional dedicated Object Storage
ledger-bucket name. During **Apply**, the stack creates a private OCIR repository,
builds the included Function source, pushes its image, and deploys the Function.
You do not need to build an image or create a repository before clicking the
button. Opening the button only opens the form; it does not deploy resources.

## Sample Code Disclaimer

**Unsupported sample code—not an Oracle-supported product or service.**

**Sample Code Disclaimer**: This script is provided as a sample. Please ensure thorough testing and modify the code as necessary to meet your specific requirements.

You are responsible for security review, testing, adaptation, deployment,
operation and resulting cloud costs. No support, maintenance, update or
security-fix commitment is made unless separately agreed in writing. This code
can permanently terminate instances. Read [DISCLAIMER.md](DISCLAIMER.md) and [NOTICE.md](NOTICE.md) before use or distribution.


## Start here

Keep your existing scheduler, demand calculation and worker runtime. Replace
the pool's existing capacity writer with OCI IAM-signed direct Function calls
from your control plane, hosted in OCI, another cloud or your own environment.
Run a durable retry/maintenance loop at your chosen interval. The deployment
stack references existing pools and networking and creates the controller,
private image repository, ledger/logging and optionally reviewed IAM.

Read these guides in order:

1. [Architecture and request contract](PRODUCT_ARCHITECTURE.md): demand,
   permanent retirement, ownership, request bodies and returning demand.
2. [Reference deployment](deploy/reference/README.md): pool enrollment, image
   build, IAM/network prerequisites and reviewed Terraform deployment.
3. [Signed client integration](examples/README.md): OCI signer configuration,
   persistent outbox, demand/retirement calls and maintenance ticks.
4. [Staging acceptance and operations](docs/RUNBOOK.md): operator decisions,
   ordered canary tests, failure recovery, exact cleanup and promotion gates.

The [implementation notes](docs/implementation-notes.md) provide a practical
engineering guide to the controller API, durable caller state, scale-out,
irreversible retirement, response handling and current safety boundaries.

## Platform integration responsibilities

- Publish absolute desired **non-retiring** capacity. Persist a UUID, payload
  and increasing generation per pool before sending; retry the same request.
- Stop assignment and complete jobs, result publication and worker cleanup
  before committing an exact worker with `set_pool_protection(tag_value="0")`.
  Retirement is permanent. New workers start protected with `"1"`; the string
  `"false"` is not equivalent to `"0"`. Approve any tag-convention migration.
- Accept retire-first/no surge and its possible capacity gap. Returning demand
  requires different workers after committed retirements finish.
- Own continued retries and periodic replay of the latest demand, including
  after completion. Status reads do not advance work. Adapt the illustrative
  single-host SQLite outbox to shared transactional control-plane state for
  multiple replicas, with one generation/replay owner per pool.
- Decode the signed invoke application's `status_code`/`body` envelope;
  transport HTTP success alone is insufficient. Use your worker registration
  and application-specific dispatchability checks to establish readiness.
- Assign platform/security owners for existing pools, scope tags, IAM, signing
  credentials, networking, images and protected state; runtime owners for the
  drain barrier; and operations owners for budgets, retries, alerts, recovery
  and rollback. Agree on actual pool count, request rate and latency targets.

Invocation permission grants authority over every pool in that controller's
allowlist. Signed invocation does not establish private network connectivity.
Each migrated pool must have one scaling writer and no attached OCI autoscaling
configuration, even a disabled one.

## Included

- Controller-only image context and commented source.
- Terraform referencing existing operator pools and networking; no demo fleet.
- Signed OCI invocation client with an illustrative durable local outbox.
- Architecture, implementation notes, operations and staging acceptance guides.
- Deployment helper and packaging regression tests (`python3 -m unittest discover -s tests -v`).
- `RELEASE_MANIFEST.json` with the SHA-256 of every included content file.

Historical controller tests, lab assets and historical evidence are not included
in this public-source snapshot. The controller Dockerfile copies only Function source and
requirements. Terraform state, plans, populated variables, credentials, outboxes
and local attachments are not packaged.

## Deploy to Oracle Cloud with Resource Manager

See Oracle's [Using the Deploy to Oracle Cloud Button](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/deploybutton.htm)
for instructions on linking a Terraform configuration ZIP to the OCI Resource
Manager **Create stack** page.

### One-click deployment from this repository

Click the **Deploy to Oracle Cloud** button above. Its complete launch URL is:

```text
https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https%3A%2F%2Fgithub.com%2FPerseus1237%2Foci-pool-controller%2Farchive%2Frefs%2Fheads%2Fmain.zip&workingDirectory=oci-pool-controller-main%2Fdeploy%2Freference
```

GitHub puts the source under a top-level
`oci-pool-controller-main/` directory in `main.zip`. Therefore the direct
GitHub launch must use the full working directory
**`oci-pool-controller-main/deploy/reference`**. `schema.yaml` is located at
that path and renders the Resource Manager variable form. On the **Stack
information** page, explicitly select Terraform **1.5.x** before selecting
**Next**. The module constrains Terraform to Resource Manager's supported
1.5.x runtime (CLI 1.5.7); selecting a blank or retired version causes the
`Invalid Terraform version` error.

### Build and deploy the Function in Resource Manager

Keep `build_function_image = true` (the default) to build from source.
The stack creates an immutable private repository in the selected OCIR
compartment, builds `function/Dockerfile` for `linux/amd64` on the Resource Manager
host, pushes the image, and deploys a `GENERIC_X86` Function. OCI resolves the
image's SHA-256 digest during Function creation. The image address and digest
are deployment outputs, not values you need to look up. The Function's
architecture is independent of the enrolled workers' architecture.

Select the compartments and existing Function VCN/subnets, then enter your
**OCIR username** (for example, `Default/user`; the stack adds the tenancy
namespace) and **OCIR auth token**. Generate a token from your OCI user profile
under **Tokens and keys → Auth Tokens** if you do not already have one. The
token's user needs permission to push images into the selected registry
compartment. [Oracle auth-token instructions](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrygettingauthtoken.htm)

Docker is included on the [Resource Manager Terraform host](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Concepts/terraformhost.htm).
No local Docker/Podman installation, separate build pipeline, or generated ZIP is
needed for this path. Apply rebuilds when the included Function source or build
helper changes. Base-image tags and downloaded dependencies can change between
builds; use the existing-image option below when deploying a previously built
artifact is required.

The auth token is a sensitive stack input used for registry login. Terraform
1.5 can retain sensitive inputs in state and saved plans; protect Resource
Manager stack access and never commit the token, populated variables, or state.
IAM creation defaults to off: the required FaaS policies must already exist, or
an authorized administrator can enable `create_iam_resources`. See the
[deployment prerequisites](deploy/reference/README.md#1-prerequisites-and-ownership).

### Optional: deploy an existing image

Set `build_function_image = false`, then set `function_image` to an existing
private OCIR image with a tag to skip the stack's image build and repository creation. Set
`function_shape` to match that image (`GENERIC_ARM` remains the default for this
mode). Supply `function_image_digest` to pin a previously reviewed artifact, or
leave it blank for OCI to resolve the tag during deployment. Registry build
credentials are not required in this mode.

Choose the image mode when creating the stack. The automatically created
repository is protected against destruction: switching an existing source-build
stack to manual mode requires a deliberate repository-ownership migration, not
just unchecking the box. Leaving source-build mode enabled does not rebuild an
unchanged image on every Apply.

For a package prefilled with an existing image and digest, the optional helper
below builds and publishes from an authenticated workstation or CI runner:

```sh
export POOL_IMAGE="iad.ocir.io/OCIR_NAMESPACE/OCIR_REPOSITORY:release-2026-09-15"
python3 scripts/build-publish-function-image.py --image "$POOL_IMAGE" --output-dir dist
```

The command builds `function/Dockerfile` for `linux/arm64`, pushes it, captures
the digest returned by OCIR, and creates a
`*-resource-manager-<digest-prefix>.zip` plus a non-secret image-values JSON
sidecar. The ZIP sets `build_function_image = false`, pre-fills the image address,
digest, and `GENERIC_ARM` in the Resource Manager form, and includes
`IMAGE_PROVENANCE.json` for review. It does
not create a stack, upload an artifact, accept terms, or run Terraform apply.
Use `--architecture amd64` only when the reviewed image is built for that
architecture; it pre-fills `GENERIC_X86`.

Host that generated ZIP behind an approved read-only Object Storage PAR and
open it with `workingDirectory=deploy%2Freference`, as documented below. The
image fields identify the artifact to deploy. This optional package is not
needed for the public button's default source build.

### Packaged release ZIP

Build the source archive and Resource Manager ZIP from the verified manifest:

```sh
python3 scripts/package-reference.py
```

The `*-resource-manager.zip` preserves the source layout. Its full Terraform
working directory is **`deploy/reference`** (without the GitHub archive-root
prefix). This directory contains the Terraform files and `schema.yaml` that
render the deployment form. The form uses OCI selectors for compartments, the
Function VCN and Function subnets, with subnets filtered to the selected VCN.
For each pool it asks only for the pool OCID, worker type and approved maximum
size; Terraform reads the existing pool/configuration to verify tags and derive
its name, shape, OCPUs and memory. The dedicated Object Storage ledger bucket
is created automatically. The full source `.tar.gz` is for review, not Resource
Manager. Follow the [deployment guide](deploy/reference/README.md) first:
existing pools/networking, an OCIR username/auth token for the default build,
IAM permissions, and deployment variables are still required. The generic
package supports the same source-build path as the public GitHub button.

To host a version-pinned package privately, use an approved read-only,
single-object Object Storage pre-authenticated request (PAR) for the deployment
ZIP. Its launch URL must use the ZIP-specific working directory:

```text
https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=<URL-encoded-PAR>&workingDirectory=deploy%2Freference
```

Treat a PAR as a bearer link; do not commit it to this repository. An expired
PAR will no longer work for new stack creation.

When creating the stack, deselect **Run apply**, review the variables, and run
and review a plan before applying. Keep `dry_run = true` and
`enable_termination = false` for initial validation. A deploy button does not
replace release approval or the staging checks in the runbook.

## Configuration and upgrade boundary

Profiles use `worker_type` in Terraform and `workerType` in Function profile
JSON/status output. These are descriptive worker-class labels, not OCI shape
identifiers; Terraform derives shape, OCPUs and memory from the attached
immutable instance configuration and validates them at plan time.
Invoke the example as `examples/pool_controller.py`. The release archive and
default deployment prefix are `oci-pool-controller`.

This is not an unattended in-place upgrade of a prior customized deployment.
Adapt profile mappings and status consumers to the new metadata names and
review the Terraform plan. Existing deployments must explicitly retain their
resource naming, pool keys/OCIDs, scope ID and ledger ownership where needed;
changing defaults can rename or replace resources. Never reset retirement
records or generation counters to adopt the new naming. See the
[deployment guide](deploy/reference/README.md) before migration.

The source still supports only its documented Intel Flex profiles. Generic
naming does not add support for arbitrary shapes, regions, scheduler products
or fleet sizes. Your scheduler decides worker demand and proves all work on a
worker has drained before committing retirement.

## Verify before using

Verify source content against `RELEASE_MANIFEST.json`; it records file
integrity, not release approval. Review the source, dependencies and image
build before staging. From the source root:

```sh
terraform -chdir=deploy/reference init -backend=false
terraform -chdir=deploy/reference fmt -check
terraform -chdir=deploy/reference validate
```

Terraform init downloads the locked provider if not cached; validation does
not deploy resources. Regression/fault tests are maintained and run in the
development repository; request their version-specific results from the release
owner. Follow the deployment guide and runbook before planning live changes.

Pattern scanning and an explicit inclusion list reduce accidental disclosure;
they do not replace manual security review. **Confirm sharing/license terms in
[NOTICE.md](NOTICE.md) before external distribution or incorporation.**

Known limitations include caller-driven reconciliation, no cancellation of
service-limit-stalled `SCALING`, and no managed `STOPPED`-worker cleanup. Shape
caps, the 100-instance exclusion limit, bounded inline registry, ledger growth
and unqualified fleet throughput require operator planning. Read the
[architecture limits](PRODUCT_ARCHITECTURE.md#7-limits-and-failure-boundaries)
and [production promotion gates](docs/RUNBOOK.md#9-production-promotion-gates).

## POC SAMPLE CODE
ORACLE AND ITS AFFILIATES DO NOT PROVIDE ANY WARRANTY WHATSOEVER, EXPRESS OR IMPLIED, FOR ANY SOFTWARE, MATERIAL OR CONTENT OF ANY KIND CONTAINED OR PRODUCED WITHIN THIS REPOSITORY, AND IN PARTICULAR SPECIFICALLY DISCLAIM ANY AND ALL IMPLIED WARRANTIES OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY, AND FITNESS FOR A PARTICULAR PURPOSE. FURTHERMORE, ORACLE AND ITS AFFILIATES DO NOT REPRESENT THAT ANY CUSTOMARY SECURITY REVIEW HAS BEEN PERFORMED WITH RESPECT TO ANY SOFTWARE, MATERIAL OR CONTENT CONTAINED OR PRODUCED WITHIN THIS REPOSITORY. IN ADDITION, AND WITHOUT LIMITING THE FOREGOING, THIRD PARTIES MAY HAVE POSTED SOFTWARE, MATERIAL OR CONTENT TO THIS REPOSITORY WITHOUT ANY REVIEW. USE AT YOUR OWN RISK.
