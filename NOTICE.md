# Unsupported sample and licensing notice

This package is a reusable reference implementation for engineering review and
staging evaluation, not a supported production service or an OCI capacity SLA.

## Sample Code Disclaimer

This script is provided as a sample. Please ensure thorough testing and modify the code as necessary to meet your specific requirements.

The sample carries no support, maintenance, update, security-fix or service-level
commitment unless separately agreed in writing. See [DISCLAIMER.md](DISCLAIMER.md)
for the full unsupported-sample notice and [LICENSE.txt](LICENSE.txt) for the complete
UPL 1.0 license and its warranty/liability terms.

ORACLE AND ITS AFFILIATES DO NOT PROVIDE ANY WARRANTY WHATSOEVER, EXPRESS OR IMPLIED, FOR ANY SOFTWARE, MATERIAL OR CONTENT OF ANY KIND CONTAINED OR PRODUCED WITHIN THIS REPOSITORY, AND IN PARTICULAR SPECIFICALLY DISCLAIM ANY AND ALL IMPLIED WARRANTIES OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY, AND FITNESS FOR A PARTICULAR PURPOSE. FURTHERMORE, ORACLE AND ITS AFFILIATES DO NOT REPRESENT THAT ANY CUSTOMARY SECURITY REVIEW HAS BEEN PERFORMED WITH RESPECT TO ANY SOFTWARE, MATERIAL OR CONTENT CONTAINED OR PRODUCED WITHIN THIS REPOSITORY. IN ADDITION, AND WITHOUT LIMITING THE FOREGOING, THIRD PARTIES MAY HAVE POSTED SOFTWARE, MATERIAL OR CONTENT TO THIS REPOSITORY WITHOUT ANY REVIEW. USE AT YOUR OWN RISK.

## Release-owner approval

The copyright line and UPL designation were supplied for this package:
Copyright (c) 2024 Oracle and/or its affiliates.

The standard license body follows the
[OCI Core Landing Zone UPL 1.0 example](https://github.com/oci-landing-zones/terraform-oci-core-landingzone/blob/main/LICENSE.txt).
Its project-specific copyright years were not copied; the supplied 2024 line
above still requires approval for this repository. The additional sample-code
disclaimer is separate from, and does not modify, the standard license text.

Before external distribution or incorporation, the repository owner and
appropriate Oracle legal reviewer must confirm copyright ownership, the correct
copyright year(s), contributor provenance, the right to license all included
material under the stated terms, and any required third-party notices. Adding
this notice does not establish those facts or record legal approval. Disclaimers
do not guarantee immunity from claims or liability; separate signed agreements
and applicable law must be considered by the legal reviewer.

## Third-party material and release scope

The project originated from the OCI instance-pool scaler
(https://github.com/vdeolali/oci-ipa-scaler). Confirm upstream
provenance, authorship, and applicable notices during the release review.

The OCI Python SDK, Fn Python FDK, and container base images retain their own
licenses and notices. Review their pinned dependencies and image contents in
the operator build pipeline; source packaging does not redistribute an image.

`0.12.0-rc.1` is a generic integration package with provider-neutral worker-class
labels (`workerType`), reusable examples and generic artifact/resource naming.
Scaling and retirement safeguards are retained. Tests, optional generic lab
assets and release-building tools are not included in the installation archive.

This revision includes implementation notes revised for the controller API,
caller-owned state and retries, retirement semantics and current limitations.
Naming and metadata changes require migration review for existing deployments;
they do not establish production qualification.

Packaging does not deploy or qualify the controller. An operator-owned review,
image build/security scan, signed-invocation staging canary and production
approval are still required. Historical lab evidence must not be described as
validation of the complete platform integration.
