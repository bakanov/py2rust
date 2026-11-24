FROM rust:1.83.0-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/py2rust \
    HOME=/tmp
WORKDIR /opt/py2rust

COPY tools/build_frontend_wheel.py tools/build_frontend_wheel.py
COPY py2rust/compiler/frontend/mypy-source.json py2rust/compiler/frontend/mypy-source.json
RUN python tools/build_frontend_wheel.py --fetch --output /tmp/frontend-wheels
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY py2rust py2rust
RUN pip install --no-cache-dir --find-links /tmp/frontend-wheels . \
    && rm -rf /tmp/frontend-wheels
RUN cargo fetch --locked --manifest-path py2rust/compiler/service_runtime/Cargo.toml \
    && chmod -R a+rwX /usr/local/cargo
COPY examples/projects/access_log examples/projects/access_log
COPY benchmarks/access_log/native.rs benchmarks/access_log/native.rs
COPY tools/compare_access_log.py tools/compare_access_log.py
COPY docker/run_example.py docker/run_example.py

RUN rustup component add rustfmt

ENTRYPOINT ["python", "/opt/py2rust/docker/run_example.py"]
