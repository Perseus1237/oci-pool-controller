# OCI Pool Controller — Reference Implementation

A reference implementation for integrating a scheduler or control plane with
OCI instance pools. It demonstrates durable desired-capacity reconciliation,
per-pool coordination, and explicit retirement of drained workers. Adapt and
validate it for your platform; it is not a production-qualified service.

> **Public-release draft — not approved for external distribution.**
> This clean-history source snapshot is prepared for release review only.
> Complete the [release checklist](RELEASE_CHECKLIST.md) before publishing,
> pushing to an external repository, or distributing source or images.

## Sample Code Disclaimer

**Unsupported sample code—not an Oracle-supported product or service.**

**Sample Code Disclaimer**: This script is provided as a sample. Please ensure thorough testing and modify the code as necessary to meet your specific requirements.

You are responsible for security review, testing, adaptation, deployment,
operation and resulting cloud costs. No support, maintenance, update or
security-fix commitment is made unless separately agreed in writing. This code
can permanently terminate instances. Read [DISCLAIMER.md](DISCLAIMER.md),
[LICENSE.txt](LICENSE.txt) and [NOTICE.md](NOTICE.md) before use or distribution.

This draft is based on **0.12.0-rc.1**, a review and staging sample, not a
production-qualified release. This revision introduces generic naming and
`workerType` profile metadata; scaling and retirement safeguards are retained. The image,
signed transport, IAM, networking and real worker runtime require an operator
staging canary. Packaging does not deploy resources or authorize cloud spending.

## Start here

Keep your existing scheduler, demand calculation and worker runtime. Replace
the pool's existing capacity writer with OCI IAM-signed direct Function calls
from your control plane, hosted in OCI, another cloud or your own environment.
Run a durable retry/maintenance loop at your chosen interval. The deployment
stack references existing pools and networking and creates the controller,
ledger/logging and optionally reviewed IAM.

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
- `RELEASE_MANIFEST.json` with the SHA-256 of every included content file.

Tests, lab assets and historical evidence are not included
in this public-source snapshot. The controller Dockerfile copies only Function source and
requirements. Terraform state, plans, populated variables, credentials, outboxes
and local attachments are not packaged.

## Deploy to Oracle Cloud with Resource Manager

See Oracle's [Using the Deploy to Oracle Cloud Button](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/deploybutton.htm)
for instructions on linking a Terraform configuration ZIP to the OCI Resource
Manager **Create stack** page.

Build the source archive and Resource Manager ZIP from the verified manifest:

```sh
python3 scripts/package-reference.py
```

The `*-resource-manager.zip` includes root Terraform files and a `schema.yaml`
deployment form; original source paths remain available for the linked guides.
The full source `.tar.gz` is for review, not Resource Manager. Follow the [deployment guide](deploy/reference/README.md)
first: existing pools/networking, a built private Function image and digest,
IAM permissions, and deployment variables are still required.

For private distribution, use an approved read-only, single-object Object
Storage pre-authenticated request (PAR) for the deployment ZIP. Open
`https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=<URL-encoded-PAR>`
or place that URL behind Oracle's deploy-button image in a privately shared
launch page. Treat a PAR as a bearer link; do not commit it to this repository.
An expired PAR will no longer work for new stack creation. The repository does
not embed a permanent public download or credentials.

When creating the stack, deselect **Run apply**, review the variables, and run
and review a plan before applying. Keep `dry_run = true` and
`enable_termination = false` for initial validation. A deploy button does not
replace release approval or the staging checks in the runbook.

## Configuration and upgrade boundary

Profiles use `worker_type` in Terraform and `workerType` in Function profile
JSON/status output. These are descriptive worker-class labels, not OCI shape
identifiers; `oci_shape`, OCPU and memory settings remain separately validated.
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

## License

Copyright (c) 2024 Oracle and/or its affiliates.

Licensed under the Universal Permissive License (UPL), Version 1.0.

See [LICENSE.txt](LICENSE.txt) for the complete standard license and
[NOTICE.md](NOTICE.md) for release-owner approval requirements.

ORACLE AND ITS AFFILIATES DO NOT PROVIDE ANY WARRANTY WHATSOEVER, EXPRESS OR IMPLIED, FOR ANY SOFTWARE, MATERIAL OR CONTENT OF ANY KIND CONTAINED OR PRODUCED WITHIN THIS REPOSITORY, AND IN PARTICULAR SPECIFICALLY DISCLAIM ANY AND ALL IMPLIED WARRANTIES OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY, AND FITNESS FOR A PARTICULAR PURPOSE. FURTHERMORE, ORACLE AND ITS AFFILIATES DO NOT REPRESENT THAT ANY CUSTOMARY SECURITY REVIEW HAS BEEN PERFORMED WITH RESPECT TO ANY SOFTWARE, MATERIAL OR CONTENT CONTAINED OR PRODUCED WITHIN THIS REPOSITORY. IN ADDITION, AND WITHOUT LIMITING THE FOREGOING, THIRD PARTIES MAY HAVE POSTED SOFTWARE, MATERIAL OR CONTENT TO THIS REPOSITORY WITHOUT ANY REVIEW. USE AT YOUR OWN RISK.
