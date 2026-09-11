# Control-plane adapter example

This is a staging integration example, not a production scheduler. Keep your
existing scheduler and invoke the OCI controller directly using the OCI SDK.
The SDK signs requests; OCI Functions verifies IAM authorization before
execution. No demo UI, browser token or API Gateway is required. The caller
may run in any environment with approved connectivity and an OCI signer.

Use the **controller-only** Terraform deployment with `AUTH_MODE=oci_iam`.
Only approved machine principals should have invoke permission for its dedicated
Function/application. The handler's response envelope is
`{"status_code": <business HTTP status>, "body": <controller response>}`;
an HTTP 200 invocation alone is not proof that the operation succeeded.

## Install and configure

```sh
python3 -m venv .venv-client
.venv-client/bin/python -m pip install -r examples/requirements.txt
```

Configure an operator-owned OCI machine identity/profile using your approved
credential distribution and rotation mechanism. Restrict config/private-key
permissions; never commit credentials or enable SDK HTTP debug logging in
production. The CLI reads the standard OCI config/profile. `OCITransport` also
accepts a preconfigured `FunctionsInvokeClient` for an approved alternate signer.

Use reference deployment outputs for `--function-id` and the **Functions invoke
base endpoint**, not the UI/gateway URL. These commands contain placeholders;
replace them before execution. Keep one persistent outbox per environment and
Function registry in an access-controlled directory. Do not reset it on restart.

```sh
.venv-client/bin/python examples/pool_controller.py \
  --function-id '<controller-function-ocid>' \
  --endpoint 'https://<application-endpoint>.functions.oci.oraclecloud.com' \
  --profile POOL_STAGING --outbox /secure/state/controller-outbox.sqlite \
  pools
```

All commands below use those same connection/outbox arguments before the command.

## Scheduler integration

1. Retain your scheduler's queue/job accounting. Calculate an **absolute non-retiring
   target**, and atomically allocate a strictly increasing per-pool generation
   in the authoritative scheduler database. Publish:

   ```text
   demand --pool intel-small --target 3 --generation 101
   ```

   `Outbox.demand()` stores a UUID and the complete immutable payload before the
   first send. Repeating the same local generation and target returns that UUID.
   A new decision gets a new UUID and generation. Never increment the generation
   just because a request timed out. At migration, seed the counter above the
   controller's observed `latestDesiredGeneration`; do not assume it is zero.

2. When a worker is permanently retiring, stop dispatch to it and verify its
   job has completed/results are durable. Commit retirement of that exact OCID:

   ```text
   retire --pool intel-small --instance-id <worker-ocid> --confirmed-idle-and-dispatch-disabled
   ```

   This writes the exact string `"0"` through `set_pool_protection`; it never
   cancels retirement and does not change demand. Publish a lower absolute target
   only if scheduler demand actually decreased. If demand is unchanged, keep the
   current target; maintenance will finish retirement and request replacements.
   A CLI confirmation flag is an operator assertion, not proof a job is idle.

3. On your periodic per-pool maintenance loop, run:

   ```text
   tick --pool intel-small
   ```

   A tick advances pending retirement writes and replays the latest desired
   request **even if it previously completed**. Each tick makes at most one
   attempt per pending record. It does not run a background loop. The caller owns
   continued ticks, timeouts, monitoring, and alerts for stuck progress.
   Different pools can have independent scheduler loops.

4. Inspect without advancing reconciliation:

   ```text
   status --request-id <persisted-request-uuid>
   pools
   ```

   Status polling alone will not finish a queued/submitted request. Pool
   completion means controller capacity convergence, not job dispatchability.
   `bootstrapReady` is the demo bootstrap marker, **not your platform registration**.
   Use your actual worker registration and application dispatch checks.

## Retry and persistence contract

- SDK automatic retries are disabled. `Controller.send(..., max_attempts=4)` is
  available for bounded in-process retry; the CLI defaults to one attempt, with
  subsequent attempts owned by the scheduler timer. Backoff uses exponential
  jitter capped at 30 seconds (maximum eight attempts per call). A pending
  response remains in the outbox when that bound is reached.
- Honor the controller's `retryable` field. In particular, **do not retry every
  409**: retirement/provenance/safety rejection can be permanent. Transport
  timeouts, 429, and transient 5xx replay the same UUID and entire payload.
- `superseded` is terminal for that request; it cannot regain authority. Do not
  automatically invent a higher generation to override another writer.
- Nonretryable failed records stop automatic maintenance for that demand. Alert,
  diagnose, and authorize a new generation only after the cause is resolved.
  A retirement write with an uncertain timeout followed by `instance_not_member`
  requires inspecting authoritative retirement/instance state; do not assume
  failure, re-protect the worker, or return it to scheduling.
- Interrupted processes resume from the outbox. Persist it before acknowledging
  a scheduler event. The Function has its own durable request/retirement ledgers;
  the caller outbox retains the exact instructions required to replay them.
- Only the scheduler knows the right target. This adapter never derives it from
  observed pool size or guesses `count - 1` after a worker notification.

The SQLite outbox is deliberately a **single-host example**. Before production,
implement its operations in your platform's existing shared transactional database:
one ordered desired-state writer per pool, atomic generation allocation and
outbox insertion, durable job-to-retirement commitment, replay ownership, and
bounded fleet-wide API concurrency. Multiple hosts with independent SQLite
copies can issue conflicting generations; this example does not solve that.
Maintain a backlog/progress deadline and operator escalation; an endless series
of bounded timer ticks is not a service-limit recovery mechanism. Retain failed
retirement records for review instead of treating them as reclaimed workers.

## Verification before integration

The development repository retains the offline regression tests; they are not
included in this installation archive. Adapt their coverage to your platform's CI
when replacing the illustrative outbox: stable retry payloads, persisted
generations across restart, supersession, completed-demand maintenance replay,
fail-closed errors, irreversible retirement and IAM response envelopes.

Run the operator-owned [staging acceptance checks](../docs/RUNBOOK.md) with the
reviewed image and credentials. Source tests do not establish real invocation,
Your platform registration, or application job readiness.

The transport follows Oracle's documented
[FunctionsInvokeClient](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/functions/client/oci.functions.FunctionsInvokeClient.html)
and [signed Function invocation](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsinvokingfunctions.htm).
