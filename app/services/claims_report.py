"""Claims reporting: totals by status, and a CSV export for the finance team."""
import csv
import os

from app.repositories.claims_repository import ClaimsRepository
import logging
logger = logging.getLogger(__name__)


class ClaimsReport:
    def __init__(self, repository=None):
        logger.debug(">>> Entering __init__(repository=%s)", repository, extra={"event.action": "__init__", "logrite.repository": repository})
        self.repo = repository or ClaimsRepository()
        logger.debug("<<< Exiting __init__(repository=%s)", repository, extra={"event.action": "__init__", "logrite.repository": repository})
        logger.debug("__init__(repository=%s): self.repo → %s", repository, self.repo, extra={"event.action": "__init__", "logrite.repository": repository})

    def totals_by_status(self, provider_id=None):
        logger.debug(">>> Entering totals_by_status(provider_id=<redacted>)", extra={"event.action": "totals_by_status"})
        claims = self.repo.list_claims()
        logger.debug("totals_by_status(provider_id=<redacted>): claims → %s", claims, extra={"event.action": "totals_by_status"})
        if provider_id:
            claims = [c for c in claims if c["provider_id"] == provider_id]
        totals = {}
        for claim in claims:
            status = claim["status"]
            logger.debug("totals_by_status(provider_id=<redacted>): status → %s", status, extra={"event.action": "totals_by_status"})
            count, amount = totals.get(status, (0, 0.0))
            totals[status] = (count + 1, amount + float(claim["amount"]))
        logger.debug("<<< Exiting totals_by_status(provider_id=<redacted>)", extra={"event.action": "totals_by_status"})
        return totals

    def export_csv(self, path, provider_id=None):
        logger.debug(">>> Entering export_csv(path=%s,provider_id=<redacted>)", path, extra={"event.action": "export_csv", "logrite.path": path})
        totals = self.totals_by_status(provider_id)
        logger.debug("export_csv(path=%s,provider_id=<redacted>): totals → %s", path, totals, extra={"event.action": "export_csv", "logrite.path": path})
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", newline="") as handle:
                writer = csv.writer(handle)
                logger.debug("export_csv(path=%s,provider_id=<redacted>): writer → %s", path, writer, extra={"event.action": "export_csv", "logrite.path": path})
                writer.writerow(["status", "claims", "amount"])
                for status in sorted(totals):
                    count, amount = totals[status]
                    writer.writerow([status, count, "%.2f" % amount])
            os.replace(tmp, path)
        except OSError as exc:
            logger.error("Exception in export_csv(path=%s,provider_id=<redacted>): %s", path, str(exc), exc_info=True, extra={"event.action": "export_csv", "event.category": "process", "logrite.path": path})
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError("could not write the claims report to %s: %s" % (path, exc))
        logger.debug("<<< Exiting export_csv(path=%s,provider_id=<redacted>)", path, extra={"event.action": "export_csv", "logrite.path": path})
        return len(totals)
