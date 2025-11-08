FROM ubuntu:24.04

# Install python3.12
RUN : \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       python3.12 \
       python3.12-venv \
       python3-pip \
       git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && :

# Add env to PATH
RUN python3.12 -m venv /venv
ENV PATH=/venv/bin:$PATH

# Website specific requirements
COPY requirements.txt ./
RUN apt-get install nodejs -y
RUN apt-get install curl -y
RUN python3 -m pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# Copy the entry point script and set the entry point.
COPY docker/docker_local/run.sh /root
ENTRYPOINT ["/bin/bash", "/root/run.sh"]
