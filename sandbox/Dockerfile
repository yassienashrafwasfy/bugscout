FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PIP_RETRIES=10 PIP_DEFAULT_TIMEOUT=60 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm procps curl \
    && npm install -g jscpd@4 && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    pytest pytest-cov pytest-json-report pytest-repeat pytest-randomly pytest-rerunfailures pytest-timeout \
    pytest-benchmark hypothesis schemathesis coverage mutmut \
    ruff mypy bandit radon vulture pylint big_O pyinstrument memray py-spy \
    httpx jsonschema fastapi "uvicorn[standard]" pydantic

RUN useradd -m -u 1000 tester && mkdir -p /work && chown tester /work
COPY shims/ /opt/bugscout/
ENV PATH="/opt/bugscout:${PATH}" PYTHONPATH="/opt/bugscout"
ARG BUGSCOUT_HASH=dev
LABEL bugscout.hash=$BUGSCOUT_HASH
USER tester
WORKDIR /work
CMD ["sleep", "infinity"]
