# Grab the terraform binary from the official image, then add tflocal
# (terraform-local) on a Python base so the whole toolchain is containerised.
FROM hashicorp/terraform:latest AS terraform

FROM python:3.13-slim
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
RUN pip install --no-cache-dir terraform-local
WORKDIR /terraform
