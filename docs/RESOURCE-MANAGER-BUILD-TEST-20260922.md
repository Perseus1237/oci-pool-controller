# Fresh Resource Manager deployment test — September 22, 2026

## Outcome

**Blocked before image build/push and Function deployment.** This is not a
successful one-click qualification. No ARM Function was deployed: the requested
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

## Required next step

Use a native x86 build execution environment, such as an OCI DevOps managed build
with an explicitly selected x86 shape. Build/push the controller image there,
verify `linux/amd64`, then deploy the Function using that exact artifact and
record the resolved digest. This avoids relying on the architecture of Resource
Manager's execution host. Adding build resources and scoped IAM is a separate
authorization boundary from the approved no-new-IAM standby test.

After integration, repeat a **new** GitHub-button deployment from empty stack
state, then verify successful build, push, x86 Function creation and signed
standby invocation. A recovered stack or offline engine mocks alone cannot
establish that clean-deployment result. Standby invocation also does not qualify
pool-operation permissions or controller scaling behavior.
