# Fresh Resource Manager deployment test — September 22, 2026

## Outcome

**Native x86 image build passed; delivery is blocked by OCIR upload authorization.** The original Resource
Manager-local build was blocked before image build/push and Function deployment.
This is not yet a successful one-click qualification. No ARM Function was deployed: the requested
Function architecture remained `GENERIC_X86`, and the target image `linux/amd64`.

## Scope and observed results

- Created a new stack through the public GitHub Deploy button in the operator's
  currently signed-in Ashburn tenancy, using its existing staging VCN/subnet.
  This was not recovery of the customer's failed stack in another tenancy.
- Source revision: `1b1ef7d`. The form and initial Plan succeeded. Plan showed
  ten additions, no changes/deletions, an x86 Functions application, no Compute
  worker resources and no IAM grants.
- First Apply created the private repository, ledger, application and logs but
  failed at the native-x86 builder check. It did not build/push an image or
  create the Function. Registry credentials therefore remain unvalidated.
- A source-only diagnostic update preserved every stack variable and the exact
  Terraform state bytes. Its reviewed recovery Plan changed only the build
  provisioner and missing Function, leaving infrastructure untouched.
- The diagnostic Apply reported: `Detected podman via docker reports platform
  linux/arm64`. This establishes that the managed **build host**, not the target
  Function, was ARM. It is separate from the earlier Docker `OSType` template
  failure.
- A possible existing-emulation test was prepared but **not applied**. It was
  withdrawn when the operator selected the native-x86 implementation. No
  emulator was installed or used, no ARM fallback occurred, no worker launched,
  no termination was enabled and no IAM grants were added.
- All partial test resources and state were retained. No cleanup/destroy was
  run, and the older validation stack was untouched.

The test date above uses America/Los_Angeles; the OCI jobs ran on September 23
in UTC. Private stack/job identifiers and credentials are intentionally omitted.

## Native x86 correction and live retry

The operator subsequently approved native OCI DevOps build resources and scoped
build IAM, plus publication of five allowlisted source/build files to a private
OCI code repository using the existing auth token. The token is not delivered
to the build runner. Runtime IAM remains disabled and no pools are enrolled.

- Source publication succeeded, validating the token for the private code
  repository (not a direct OCIR password login).
- The first DevOps run failed when fetching `build_spec.yaml`, before entering
  any stage. An in-pipeline WAIT cannot cover this first authorization check.
- The retry succeeded at source authorization with the **same permissions**.
  This supports IAM propagation as the cause of the first failure. The correction
  delays build-run submission for 180 seconds after creating/changing build IAM;
  this is a propagation allowance, not a guarantee of convergence.
- OCI selected `VM.Standard.E5.Flex`, 2 OCPUs / 8 GB, for the explicit
  `OL8_X86_64_STANDARD_10` build stage. Source download, checksum verification,
  native Podman `linux/amd64` check, image build and output-architecture check
  succeeded. The image-build command completed in approximately 159 seconds.
- The delivery stage failed reading the DevOps deploy artifact with
  `NotAuthorizedOrNotFound`. Read-only verification confirmed the active artifact
  ID and compartment exactly matched the policy. The cause of rejection of that
  exact-artifact conditional read remains unresolved. No image was delivered and
  no Function was created or invoked. The service's broad tenancy-wide policy
  suggestion was not applied. The operator approved compartment-scoped artifact
  metadata read and OCIR repository inspect; registry writes remain exact-repo.
- The final candidate removes the redundant in-pipeline WAIT and lets OCI retain
  its canonical repository default-branch value; builds pin a separate source
  branch. Build outputs tolerate missing failed-run data. The redundant build-run
  postcondition was removed because Terraform 1.5 still emitted `Invalid index`
  after failed resource creation; the OCI provider already waits for SUCCEEDED.
  Explicit stage descriptions address a separate `Invalid description` update
  failure observed on the existing WAIT stage. Subsequent retries passed these
  migration/error-reporting checks, but still failed at registry delivery.
- The metadata-update Apply changed IAM, then stopped with `409 Conflict` because
  Terraform attempted to delete the legacy WAIT stage before rewiring BUILD. The
  exact planned BUILD predecessor/description correction was applied through the
  API. A new Plan was reviewed before continuing; the following Apply removed
  the obsolete WAIT stage successfully. This migration issue does not exist in
  a new stack, which has no legacy WAIT stage.
- The subsequent retry successfully read the artifact and attempted OCIR upload,
  confirming progress past the previous artifact-read failure. Native image build
  again succeeded (approximately 168 seconds). OCIR denied initiation of layer
  upload for the pipeline resource principal; the repository remained empty.
  Its name, compartment, namespace and privacy were verified against the policy.
  The next candidate split the same exact-repository READ/UPDATE grant into
  two flat conditions, without adding permissions or broadening repository scope.
  That retry also failed at the same OCIR layer-upload authorization check.
  Its native image build and output verification succeeded a third time
  (approximately 168 seconds); the build run ended FAILED at 07:24:38 UTC on
  September 23. No artifact digest was delivered and no Function was deployed
  or invoked. Splitting the conditions was not a successful fix. The underlying
  authorization cause is not yet conclusively isolated; further blind retries
  or broader registry write grants are not justified by this evidence.
- All 160 offline tests and Terraform validation pass. These do not establish
  live success or a clean-deployment result.
- An isolated retry changed only the artifact endpoint to the documented
  region-key form (`iad.ocir.io`), addressing the same private repository.
  Native build passed; upload failed with the same authorization denial at
  07:43:23 UTC. The endpoint change did not resolve the failure. A bounded Audit
  lookup confirmed artifact read succeeded, but did not expose the registry
  authorization decision. With explicit administrator approval, the next
  candidate tests the standard registry-management role constrained to that
  one repository, instead of filtering individual READ/UPDATE permissions.
  This includes repository lifecycle permissions; it is not tenancy-admin or
  access to other repositories. Its live result is still pending.

## Remaining qualification

Complete the native x86 OCI DevOps managed build. Build/push the controller image,
verify `linux/amd64`, then deploy the Function using that exact artifact and
record the resolved digest. This avoids relying on the architecture of Resource
Manager's execution host.

After integration, repeat a **new** GitHub-button deployment from empty stack
state, then verify successful build, push, x86 Function creation and signed
standby invocation. A recovered stack or offline engine mocks alone cannot
establish that clean-deployment result. Standby invocation also does not qualify
pool-operation permissions or controller scaling behavior.
