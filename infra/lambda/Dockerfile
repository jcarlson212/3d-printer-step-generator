# Container image for the generation Lambda.
#
# Build context is the REPO ROOT (set in api_stack.py) so we can copy the
# printforge package and pyproject in. build123d/OpenCascade is large, hence a
# container image rather than a zip/layer.

FROM public.ecr.aws/lambda/python:3.11

# OpenCascade (OCP) runtime shared libraries needed by build123d.
# The lambda/python:3.11 base image is Amazon Linux 2 (yum).
RUN yum install -y \
        mesa-libGL \
        libXext \
        libSM \
        libICE \
        fontconfig \
        libgomp \
    && yum clean all

# Install the package with the cad (build123d) + aws (boto3) extras.
COPY pyproject.toml README.md ${LAMBDA_TASK_ROOT}/
COPY src ${LAMBDA_TASK_ROOT}/src
RUN pip install --no-cache-dir "${LAMBDA_TASK_ROOT}[cad,aws]"

# The handler lives alongside the package.
COPY infra/lambda/handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
