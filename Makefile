#!/usr/bin/make -f

PACKAGE = openscadq
MAKEINCL ?= $(shell python3 -mmoat src path)/make/py

ifneq ($(wildcard $(MAKEINCL)),)
include $(MAKEINCL)
# availabe via http://github.com/M-o-a-T/moat-src

else
%:
	@echo "Please fix 'python3 -mmoat src path'."
	@exit 1
endif

