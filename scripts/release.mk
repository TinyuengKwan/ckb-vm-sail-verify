# Release acceptance entry points (docs/RELEASE.md). Kept out of the main
# Makefile, which the Lean proof policy pins by hash.
#
#   make -f scripts/release.mk public-claims
#   make -f scripts/release.mk audit CANDIDATE=<commit> RUNTIME=... LEAN=... ROCQ=... CLEAN_ROOM=... [RELEASE=...] [THIRD_PARTY=...] OUT=<new dir>
#   make -f scripts/release.mk release-package CANDIDATE=<commit> INPUTS=<dir> EVIDENCE=<dir> OUT=<new dir>
#   make -f scripts/release.mk restore ARCHIVE=... SIGNATURE=... TOOL=... CANDIDATE=<commit> OUT=<new dir> [MODE=staging|canonical]
.PHONY: public-claims audit release-package restore

public-claims:
	python3 scripts/public_claims.py

audit:
	@test -n "$(CANDIDATE)" -a -n "$(OUT)" || (echo 'CANDIDATE and OUT are required'; exit 2)
	python3 scripts/audit_release.py --candidate "$(CANDIDATE)" --out "$(OUT)" \
	  $(if $(RUNTIME),--runtime "$(RUNTIME)") $(if $(LEAN),--lean "$(LEAN)") $(if $(ROCQ),--rocq "$(ROCQ)") \
	  $(if $(CLEAN_ROOM),--clean-room "$(CLEAN_ROOM)") $(if $(RELEASE),--release "$(RELEASE)") \
	  $(if $(THIRD_PARTY),--third-party "$(THIRD_PARTY)")

release-package:
	@test -n "$(CANDIDATE)" -a -n "$(INPUTS)" -a -n "$(EVIDENCE)" -a -n "$(OUT)" || (echo 'CANDIDATE, INPUTS, EVIDENCE and OUT are required'; exit 2)
	python3 scripts/release_package.py build --candidate "$(CANDIDATE)" --inputs "$(INPUTS)" --evidence "$(EVIDENCE)" --out "$(OUT)"

restore:
	@test -n "$(ARCHIVE)" -a -n "$(SIGNATURE)" -a -n "$(TOOL)" -a -n "$(CANDIDATE)" -a -n "$(OUT)" || (echo 'ARCHIVE, SIGNATURE, TOOL, CANDIDATE and OUT are required'; exit 2)
	python3 scripts/release_package.py restore --archive "$(ARCHIVE)" --signature "$(SIGNATURE)" --tool-archive "$(TOOL)" \
	  --candidate "$(CANDIDATE)" --out "$(OUT)" --mode "$(or $(MODE),staging)"
