# Separate from the frozen production Makefile; no theorem-policy migration.
# Usage: make -f scripts/release.mk audit-release MANIFEST=path/to/manifest.json
.PHONY: audit-release
audit-release:
	@test -n "$(MANIFEST)" || (echo 'MANIFEST is required'; exit 1)
	python3 scripts/audit_release.py --manifest "$(MANIFEST)"
