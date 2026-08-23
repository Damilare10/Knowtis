"""
Training / ops-only code.

Nothing under here is on the message-processing critical path. The runtime
pipeline classifies via Agnes (``app.services.agnes_service``) and drops junk
via ``app.services.prefilter``.

``setfit_classifier_service`` lives here because the only remaining consumer is
``app.services.model_verification_service``, which verifies a trained SetFit
package for the CI gate. It moved out of ``app/services/`` in step 4C so that
importing a service can no longer pull the SetFit stack into a request path.
"""
