# Coq build for CKB-VM verification
# Requires: coq >= 9.0, coq-sail-stdpp

COQMAKEFILE := Makefile.coq

.PHONY: all clean

all: $(COQMAKEFILE)
	$(MAKE) -f $(COQMAKEFILE)

$(COQMAKEFILE): _CoqProject $(wildcard *.v) $(wildcard generated/*.v)
	coq_makefile -f _CoqProject -o $@

clean:
	rm -f $(COQMAKEFILE) $(COQMAKEFILE).conf
	rm -f *.vo *.vok *.vos *.glob .*.aux
	rm -f generated/*.vo generated/*.vok generated/*.vos generated/*.glob generated/.*.aux
