ARG BASE_IMAGE=research-workbench-base:current
FROM ${BASE_IMAGE}
USER root
# Writer alone drops Office Math objects during PDF conversion.
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-math python3-uno && rm -rf /var/lib/apt/lists/*
USER 1000:1000
