FROM python:3.11-slim
WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# Git optional
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Wichtig: Code kommt via Mount nach /workspace
ENV PYTHONPATH=/workspace

ENTRYPOINT ["/bin/bash", "-lc", "tail -f /dev/null"]
