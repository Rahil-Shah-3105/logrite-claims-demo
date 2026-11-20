"""Claims reporting: totals by status, and a CSV export for the finance team."""
import csv
import os

from app.repositories.claims_repository import ClaimsRepository


class ClaimsReport:
    def __init__(self, repository=None):
        self.repo = repository or ClaimsRepository()

    def totals_by_status(self, provider_id=None):
        claims = self.repo.list_claims()
        if provider_id:
            claims = [c for c in claims if c["provider_id"] == provider_id]
        totals = {}
        for claim in claims:
            status = claim["status"]
            count, amount = totals.get(status, (0, 0.0))
            totals[status] = (count + 1, amount + float(claim["amount"]))
        return totals

    def export_csv(self, path, provider_id=None):
        totals = self.totals_by_status(provider_id)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["status", "claims", "amount"])
                for status in sorted(totals):
                    count, amount = totals[status]
                    writer.writerow([status, count, "%.2f" % amount])
            os.replace(tmp, path)
        except OSError as exc:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError("could not write the claims report to %s: %s" % (path, exc))
        return len(totals)
