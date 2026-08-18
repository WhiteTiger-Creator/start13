FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

# Least-volatile layers first: fix the working directory before the apt and
# dependency layers so a change to those never invalidates the WORKDIR layer.
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        golang-go \
    && rm -rf /var/lib/apt/lists/*

# /app/data/inventory_positions.json ships TRUNCATED exactly as the failed
# rollout left it; the pre-rollout snapshot and the movement journal beside it
# are the recovery sources the planner has to be rebuilt from. All values are
# synthetic.
COPY app/ /app/
RUN cp /app/workflow/plan_requirements.go /app/workflow/.plan_requirements.original.go \
    && chmod a-w /app/workflow/.plan_requirements.original.go
