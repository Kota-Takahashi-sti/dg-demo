# ツール実行用イメージ。
# 領域ごとに venv を分離して依存衝突を避ける(plan.md §2)。
# フェーズ1: quality(Soda Core / Great Expectations)
# フェーズ2: lineage(openlineage-python)
# フェーズ3: catalog(openmetadata-ingestion)
FROM docker.io/library/python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-quality.txt /opt/requirements-quality.txt
COPY requirements-lineage.txt /opt/requirements-lineage.txt
COPY requirements-catalog.txt /opt/requirements-catalog.txt

RUN python -m venv /opt/venv/quality \
    && /opt/venv/quality/bin/pip install --no-cache-dir -r /opt/requirements-quality.txt

RUN python -m venv /opt/venv/lineage \
    && /opt/venv/lineage/bin/pip install --no-cache-dir -r /opt/requirements-lineage.txt

RUN python -m venv /opt/venv/catalog \
    && /opt/venv/catalog/bin/pip install --no-cache-dir -r /opt/requirements-catalog.txt

WORKDIR /workspace
CMD ["bash"]
