"""
One AIEvent row per AI request, written even when the request fails, so a future analytics
page sees fallbacks and refusals as well as successes.

    with telemetry.record("tutor", request.user) as ev:
        result = tutor.answer(...)
        ev.done(result["source"], result.get("model", ""))

Recording must never break the feature it measures: every write is wrapped, and a failure is
only logged.
"""

import logging
import time

logger = logging.getLogger(__name__)


class _Recorder:
    def __init__(self, feature, user):
        self.feature = feature
        self.user = user if getattr(user, "is_authenticated", False) else None
        self.source = "error"
        self.model_name = ""

    def done(self, source, model_name=""):
        self.source, self.model_name = source, model_name or ""
        return self


class record:
    def __init__(self, feature, user):
        self.rec = _Recorder(feature, user)

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self.rec

    def __exit__(self, exc_type, exc, tb):
        try:
            from ..models import AIEvent
            AIEvent.objects.create(
                user=self.rec.user, feature=self.rec.feature, source=self.rec.source,
                model_name=self.rec.model_name[:80],
                latency_ms=int((time.perf_counter() - self._t0) * 1000),
            )
        except Exception:
            logger.exception("AIEvent could not be written for feature=%s", self.rec.feature)
        return False  # never swallow the real error
