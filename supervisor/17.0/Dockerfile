FROM python:3.11-bookworm
MAINTAINER Rosen Vladimirov <vladimirv.rosen@gmail.com>

ENV PIPX_BIN_DIR=/usr/local/bin
ENV PIPX_DEFAULT_PYTHON=python3
ENV PIPX_GLOBAL_MAN_DIR=/usr/local/share/man
ENV PIPX_GLOBAL_HOME=/opt/odoo/pipx
ENV PYTHONPATH=/opt/python3

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
        python3-pip \
        libcups2-dev

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

RUN pip3 install --upgrade pip && \
    pip3 install pipx && \
    pipx ensurepath --force && \
    pipx install oca-maintainers-tools@git+https://github.com/OCA/maintainer-tools.git

RUN mkdir -p /etc/odoo && \
    mkdir -p /opt/odoo && \
    mkdir -p /mnt/extra-addons && \
    mkdir -p $PYTHONPATH  && \
    mkdir /var/lib/odoo
COPY --chown=root:root ./addons.conf /etc/odoo/
COPY --chown=root:root ./supervisor.py /app/
COPY --chown=root:root ./github_credentials.sh /usr/local/bin/

ENTRYPOINT ["python3"]
CMD ["/app/supervisor.py", "/etc/odoo/addons.conf"]
