FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

# The task is Go-only, so the canonical Go image carries the toolchain rather
# than a Python base with golang-go bolted on. The image ships python3 but no
# pip, ensurepip or venv, so setup that installs its own tooling into this
# container dies here; those three and the cert bundle are added explicitly.
ENV GOCACHE=/tmp/gocache \
    GOPATH=/tmp/gopath \
    GO111MODULE=off

# Least-volatile layers first: fix the working directory before the apt layer so
# a change there never invalidates the WORKDIR layer.
WORKDIR /app

RUN set -eu; \
    delay=5; \
    for attempt in 1 2 3 4; do \
        if apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=20 \
                -o Acquire::https::Timeout=20 update \
            && apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=20 \
                -o Acquire::https::Timeout=20 install -y --no-install-recommends \
                tmux asciinema ca-certificates python3-pip python3-venv; then \
            rm -rf /var/lib/apt/lists/*; \
            exit 0; \
        fi; \
        echo "apt attempt ${attempt} failed, retrying in ${delay}s" >&2; \
        rm -rf /var/lib/apt/lists/*; \
        sleep "${delay}"; \
        delay=$((delay * 2)); \
    done; \
    exit 1

# /app/data/inventory_positions.json ships TRUNCATED exactly as the failed
# rollout left it; the pre-rollout snapshot and the movement journal beside it
# are the recovery sources the planner has to be rebuilt from. All values are
# synthetic.
COPY app/ /app/
RUN cp /app/workflow/plan_requirements.go /app/workflow/.plan_requirements.original.go \
    && chmod a-w /app/workflow/.plan_requirements.original.go
