FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir deepcode-hku==2.3.1
COPY patch_deepcode.py /opt/patch_deepcode.py
RUN python /opt/patch_deepcode.py
RUN useradd --uid 1000 --create-home coder
COPY coder_service.py /opt/coder_service.py
USER 1000:1000
ENV HOME=/home/coder
WORKDIR /workspace/coder
CMD ["python", "/opt/coder_service.py"]
