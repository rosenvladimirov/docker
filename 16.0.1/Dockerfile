FROM debian:bookworm
LABEL maintainer="Rosen Vladimirov <vladimirv.rosen@gmail.com>"

# Fail fast, strict vars, pipefail; show commands for easier debugging
SHELL ["/bin/bash", "-euo", "pipefail", "-x", "-c"]

# Build/runtime parameters
ARG ODOO_VERSION="16.0"
# Comma-separated list of locales in the format "ll_CC.UTF-8 UTF-8"
# Example:
#   --build-arg LOCALES="en_US.UTF-8 UTF-8, bg_BG.UTF-8 UTF-8"
ARG LOCALES="C.UTF-8 UTF-8,en_US.UTF-8 UTF-8"
# Default locale exported in the environment
# Example:
#   --build-arg DEFAULT_LOCALE="en_US.UTF-8"
ARG DEFAULT_LOCALE="C.UTF-8"

# Global environment
ENV LANG=${DEFAULT_LOCALE} \
    LC_ALL=${DEFAULT_LOCALE} \
    ODOO_RC=/etc/odoo/odoo.conf \
    PYTHONPATH=/opt/python3

# Base system + runtime deps (wkhtmltopdf from Debian repo for trusted, signed install)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dirmngr \
        fonts-noto-cjk \
        git \
        gnupg \
        locales \
        lsb-release \
        node-less \
        npm \
        python3-venv \
        python3-magic \
        python3-num2words \
        python3-odf \
        python3-pdfminer \
        python3-pip \
        python3-phonenumbers \
        python3-ldap \
        python3-qrcode \
        python3-reportlab \
        python3-setuptools \
        python3-slugify \
        python3-vobject \
        python3-watchdog \
        python3-xlrd \
        python3-xlwt \
        python3-psycopg2 \
        python3-transliterate \
        wkhtmltopdf \
        xz-utils && \
    update-ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Locales: enable and generate (separate for clarity)
RUN set -euo pipefail; \
    IFS=',' read -r -a REQ_LOCALES <<< "${LOCALES}"; \
    for loc in "${REQ_LOCALES[@]}"; do \
        loc="$(echo "$loc" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"; \
        [ -n "$loc" ] || continue; \
        sed -i "s/^# *${loc//\//\\/}$/${loc}/" /etc/locale.gen || true; \
        grep -qxF "${loc}" /etc/locale.gen || echo "${loc}" >> /etc/locale.gen; \
    done && \
    locale-gen

# Pin global npm tool needed by Odoo assets
RUN npm install -g rtlcss@4.1.0 && npm cache clean --force

# PostgreSQL client (PGDG) with signed key
RUN install -d /usr/share/postgresql-common/pgdg && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -f /etc/apt/sources.list.d/pgdg.list && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Odoo installation: fetch exact Filename and SHA256 from Packages, then verify over HTTPS
ARG ODOO_PACKAGE_URL="https://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/Packages"
RUN set -euo pipefail; \
    PKG_TMP="/tmp/odoo_packages" && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 -o "${PKG_TMP}" "${ODOO_PACKAGE_URL}" && \
    FILENAME="$(awk 'BEGIN{RS="";FS="\n"} /Package: odoo/{for(i=1;i<=NF;i++){if($i ~ /^Filename:/){sub(/^Filename: */,"",$i); print $i; exit}}}' "${PKG_TMP}")" && \
    SHA256="$(awk 'BEGIN{RS="";FS="\n"} /Package: odoo/{for(i=1;i<=NF;i++){if($i ~ /^SHA256:/){sub(/^SHA256: */,"",$i); print $i; exit}}}' "${PKG_TMP}")" && \
    if [[ -z "${FILENAME}" || -z "${SHA256}" ]]; then \
        echo "ERROR: Could not determine Odoo Filename/SHA256 from Packages." >&2; exit 3; \
    fi && \
    ODOO_URL="https://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/${FILENAME}" && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 -o /tmp/odoo.deb "${ODOO_URL}" && \
    echo "${SHA256}  /tmp/odoo.deb" | sha256sum -c - && \
    apt-get update && \
    apt-get install -y --no-install-recommends /tmp/odoo.deb && \
    rm -f /tmp/odoo.deb "${PKG_TMP}" && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy entrypoint, configs and helper scripts
RUN install -d -m 0755 /etc/odoo
COPY --chown=root:root ./entrypoint.sh /
COPY --chown=odoo:odoo ./odoo.conf /etc/odoo/
COPY --chown=root:root ./addons.conf /etc/odoo/
COPY --chown=root:root ./requirements.txt /etc/odoo/
COPY --chown=root:root ./wait-for-psql.py /usr/local/bin/wait-for-psql.py
COPY --chown=root:root ./supervisor.py /usr/local/bin/supervisor.py
RUN chmod 0755 /entrypoint.sh /usr/local/bin/wait-for-psql.py /usr/local/bin/supervisor.py && \
    mkdir -p /mnt/extra-addons /opt/odoo "$PYTHONPATH" && \
    chown -R odoo:odoo /mnt/extra-addons /opt/odoo

VOLUME ["/var/lib/odoo", "/var/log/odoo", "/mnt/extra-addons", "/opt/odoo"]

# Expose Odoo services
EXPOSE 8069 8071 8072

# Default user and process
USER odoo
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
