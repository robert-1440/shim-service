DIST=dist/
UTIL=util/
BIN=bin/
CLI=lib/src/cli/
RESOURCES=resources/
OUTER_BIN=~/bin/

.PHONY: all tests compile build check-modtime mod-checker $(DIST)

all: compile

tests:
	@dart test test

$(DIST):
	@mkdir -p $(DIST)

$(DIST)find_latest: $(UTIL)find_latest.dart pubspec.yaml
	@dart compile exe -o $(DIST)find_latest $(UTIL)find_latest.dart

mod-checker: $(DIST) $(DIST)find_latest

check-modtime:
	@$(DIST)find_latest $(DIST)modtime

$(DIST)shim-test: $(DIST)/modtime pubspec.yaml
	@dart compile exe -o $(DIST)shim-test $(BIN)cli.dart

$(OUTER_BIN)shim-test: $(DIST)shim-test
	cp -p $(DIST)shim-test $(OUTER_BIN)shim-test


compile: mod-checker check-modtime $(OUTER_BIN)shim-test


