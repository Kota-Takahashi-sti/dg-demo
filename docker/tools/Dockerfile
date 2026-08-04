# ツール実行用イメージ。
# 領域ごとに venv を分離して依存衝突を避ける(plan.md §2)。
# フェーズ1では quality(Soda Core / Great Expectations)のみ。
# lineage / catalog の venv はフェーズ2・3で追加する。
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-quality.txt /opt/requirements-quality.txt

RUN python -m venv /opt/venv/quality \
    && /opt/venv/quality/bin/pip install --no-cache-dir -r /opt/requirements-quality.txt

WORKDIR /workspace
CMD ["bash"]
