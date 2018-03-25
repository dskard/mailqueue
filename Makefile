PWD := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

PYTESTOPTS=

test:
	docker run -it --rm \
	  --name=mailqueue-tests \
	  --user=$(shell id -u):$(shell id -g) \
	  --volume=${PWD}:/opt/shared/work \
	  --workdir=/opt/shared/work \
	  -e PYTHONPATH=/opt/shared/work \
	  dskard/tew:dev \
	  pytest ${PYTESTOPTS} /opt/shared/work


.PHONY: test
