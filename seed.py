"""Seeds a few claims and one deliberately bad audit row (SSN in free text)."""
from app.repositories.claims_repository import ClaimsRepository

repo = ClaimsRepository()
for provider, beneficiary, code, amount in [
    ("PRV-2201", "BEN-7731", "99214", 1250.00),
    ("PRV-2201", "BEN-8102", "27447", 18400.00),
    ("PRV-3390", "BEN-1044", "93000", 310.00),
]:
    claim = repo.create_claim(provider, beneficiary, code, amount)
    repo.write_audit("seed", "SUBMIT", claim["claim_id"], amount, "SUBMITTED")
repo.write_audit(
    "reviewer-1", "NOTE", "CLM-SEED01", None, None,
    "Beneficiary called to confirm identity, SSN 123-45-6789, DOB 04/12/1961. Documentation attached.")
print("seeded", len(repo.list_claims()), "claims and", len(repo.list_audit()), "audit rows")
