TAG?=0.3.30
VERSION:=0.3.30
NAME:=dify-api
DOCKER_REPOSITORY:=harbor.pandadagames.net/qaq
DOCKER_IMAGE_NAME:=$(DOCKER_REPOSITORY)/$(NAME)
# GIT_COMMIT:=$(shell git describe --dirty --always)
EXTRA_RUN_ARGS?=
PYTHON=`command -v python3.11 || command -v python3.10 || command -v python3.9 || command -v python3.8`

venv:
	# Create a virtual environment and activate it (recommended)
	if ! [ -x "${PYTHON}" ]; then echo "You need Python 3.8, 3.9, 3.10 or 3.11 installed"; exit 1; fi
	test -d venv || ${PYTHON} -m venv venv # setup a python3 virtualenv
	. venv/bin/activate

activate:
	. venv/bin/activate

fmt:
	pre-commit run --all-files

build:
	docker build --platform=linux/amd64 -f Dockerfile.yh -t $(DOCKER_IMAGE_NAME):$(VERSION) .

build-base:
	docker build --platform=linux/amd64 -f Dockerfile.base -t $(DOCKER_IMAGE_NAME):base .

push-base:
	docker push $(DOCKER_IMAGE_NAME):base

test-container:
	@docker rm -f $(NAME) || true
	@docker run -dp 10002:10002 --name=$(NAME) $(DOCKER_IMAGE_NAME):$(VERSION)
	@docker ps | grep $(NAME)
	# @curl -s http://127.0.0.1:10002

push:
	docker tag $(DOCKER_IMAGE_NAME):$(VERSION) $(DOCKER_IMAGE_NAME):latest
	docker push $(DOCKER_IMAGE_NAME):$(VERSION)
	docker push $(DOCKER_IMAGE_NAME):latest

run:
	export FLASK_APP=app.py
	flask run --host 0.0.0.0 --port=5001 --debug

version-set:
	next="$(TAG)" && \
	current="$(VERSION)" && \
	sed -i "s/$(NAME):$$current/$(NAME):$$next/g" kustomize/deployment.yaml && \
	echo "Version $$next set in code, deployment and kustomize"

deploy:
	kubectl apply -k kustomize

release:
	git tag $(VERSION)
	git push origin $(VERSION)