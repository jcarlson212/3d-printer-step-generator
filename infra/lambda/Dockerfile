# Container image for the generation Lambda.
#
# Build context is the REPO ROOT (set in api_stack.py) so we can copy the
# printforge package and pyproject in. build123d/OpenCascade (OCP) is large, hence
# a container image rather than a zip/layer.
#
# Base is the AL2023 Lambda image (python:3.12): modern glibc (2.34) so the OCP
# manylinux wheels resolve. (The python:3.11 image is AL2 / glibc 2.26, where no
# compatible OCP wheel exists.) Built for linux/amd64 -- OCP is x86_64-only.

FROM public.ecr.aws/lambda/python:3.12

# OpenCascade (OCP) runtime shared libraries needed by build123d (AL2023 -> dnf).
RUN dnf install -y \
        mesa-libGL \
        libXext \
        libSM \
        libICE \
        fontconfig \
        libgomp \
    && dnf clean all

# Install the package with the cad (build123d) + aws (boto3) extras.
COPY pyproject.toml README.md ${LAMBDA_TASK_ROOT}/
COPY src ${LAMBDA_TASK_ROOT}/src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "${LAMBDA_TASK_ROOT}[cad,aws]"

# The handler lives alongside the package.
COPY infra/lambda/handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
