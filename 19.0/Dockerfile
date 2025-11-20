# Build/runtime parameters (override at build time if needed)
ARG ODOO_VERSION="19.0"
ARG LOCALES="en_US.UTF-8 UTF-8"
ARG DEFAULT_LOCALE="en_US.UTF-8"
ARG TARGETARCH="amd64"

# ============================================
# Stage 1: Metadata collector
# ============================================
FROM python:3.12-slim-bookworm AS metadata

RUN set -eu; \
    BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" && \
    OS_NAME="$(grep '^NAME=' /etc/os-release | cut -d'=' -f2 | tr -d '"')" && \
    OS_VERSION="$(grep '^VERSION=' /etc/os-release | cut -d'=' -f2 | tr -d '"')" && \
    OS_VERSION_ID="$(grep '^VERSION_ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')" && \
    ARCHITECTURE="$(dpkg --print-architecture)" && \
    DEBIAN_VERSION="$(cat /etc/debian_version)" && \
    PYTHON_VERSION="$(python3 --version | awk '{print $2}')" && \
    echo "BUILD_DATE='${BUILD_DATE}'" > /tmp/metadata.env && \
    echo "OS_NAME='${OS_NAME}'" >> /tmp/metadata.env && \
    echo "OS_VERSION='${OS_VERSION}'" >> /tmp/metadata.env && \
    echo "OS_VERSION_ID='${OS_VERSION_ID}'" >> /tmp/metadata.env && \
    echo "ARCHITECTURE='${ARCHITECTURE}'" >> /tmp/metadata.env && \
    echo "DEBIAN_VERSION='${DEBIAN_VERSION}'" >> /tmp/metadata.env && \
    echo "PYTHON_VERSION='${PYTHON_VERSION}'" >> /tmp/metadata.env

# ============================================
# Stage 2: Dependencies Builder
# ============================================
FROM debian:bookworm-slim AS dependencies-builder

ARG TARGETARCH
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates python3 python3-psycopg2 && \
    rm -rf /var/lib/apt/lists/*

# Извличане на wkhtmltopdf
RUN if [ -z "${TARGETARCH}" ]; then \
        TARGETARCH="$(dpkg --print-architecture)"; \
    fi; \
    case ${TARGETARCH} in \
        "amd64") \
            WKHTMLTOPDF_SHA=e9f95436298c77cc9406bd4bbd242f4771d0a4b2 && \
            WKHTMLTOPDF_PKG=0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64 ;; \
        "arm64") \
            WKHTMLTOPDF_SHA=77bc06be5e543510140e6728e11b7c22504080d4 && \
            WKHTMLTOPDF_PKG=0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_arm64 ;; \
        *) echo "ERROR: Unsupported architecture: ${TARGETARCH}" >&2 && exit 1 ;; \
    esac && \
    curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_PKG}.deb && \
    echo "${WKHTMLTOPDF_SHA}  wkhtmltox.deb" | sha1sum -c - && \
    dpkg-deb -x wkhtmltox.deb /opt/wkhtmltox && \
    rm wkhtmltox.deb && \
    echo "WKHTMLTOPDF_VERSION='0.12.6.1-3'" > /tmp/wkhtmltopdf_metadata.env && \
    echo "WKHTMLTOPDF_ARCHITECTURE='${TARGETARCH}'" >> /tmp/wkhtmltopdf_metadata.env && \
    echo "WKHTMLTOPDF_SHA='${WKHTMLTOPDF_SHA}'" >> /tmp/wkhtmltopdf_metadata.env

# Копиране на psycopg2 библиотеки
RUN mkdir -p /opt/psycopg2 && \
    cp -r /usr/lib/python3/dist-packages/psycopg2* /opt/psycopg2/ && \
    find /usr/lib -name "*psycopg*" -type f -exec cp {} /opt/psycopg2/ \; && \
    echo "Copied psycopg2 files:" && \
    ls -la /opt/psycopg2/

# ============================================
# Stage 3: Main image - Python 3.12
# ============================================
FROM python:3.12-slim-bookworm

ARG ODOO_VERSION
ARG LOCALES
ARG DEFAULT_LOCALE

# Копиране на метаданните и dependencies от предходните stages
COPY --from=metadata /tmp/metadata.env /tmp/
COPY --from=dependencies-builder /tmp/wkhtmltopdf_metadata.env /tmp/
COPY --from=dependencies-builder /opt/wkhtmltox/usr/local /usr/local/
COPY --from=dependencies-builder /opt/psycopg2 /tmp/psycopg2_debian/

SHELL ["/bin/bash", "-euo", "pipefail", "-x", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    QT_QPA_PLATFORM=offscreen \
    LANG=${DEFAULT_LOCALE} \
    LC_ALL=${DEFAULT_LOCALE} \
    PYTHONPATH=/opt/python3 \
    ODOO_RC=/etc/odoo/odoo.conf

# Base system + runtime deps (БЕЗ python3-psycopg2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pipx fontconfig libx11-6 libxcb1 libxext6 libxrender1 \
        libfreetype6 libjpeg62-turbo libpng16-16 fonts-dejavu-core \
        xfonts-75dpi xfonts-base gsfonts ca-certificates curl dirmngr \
        fonts-noto-cjk gnupg locales lsb-release node-less npm \
        python3-magic python3-num2words python3-odf python3-pdfminer \
        python3-pip python3-phonenumbers python3-ldap python3-qrcode \
        python3-reportlab python3-setuptools python3-slugify \
        python3-transliterate python3-vobject python3-watchdog \
        python3-xlrd python3-xlwt xz-utils \
        libpq5 && \
    update-ca-certificates && ldconfig && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Опит за инсталиране на Debian psycopg2 в Python 3.12
RUN set -eu; \
    echo "=== Attempting to install Debian psycopg2 into Python 3.12 ===" && \
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") && \
    PYTHON_SITE_PACKAGES="/usr/local/lib/python${PYTHON_VERSION}/site-packages" && \
    echo "Python version: ${PYTHON_VERSION}" && \
    echo "Python site-packages: ${PYTHON_SITE_PACKAGES}" && \
    cp -r /tmp/psycopg2_debian/psycopg2* ${PYTHON_SITE_PACKAGES}/ && \
    python3 -c "import psycopg2; print(f'✓ psycopg2 {psycopg2.__version__}')" || \
    (echo "✗ Debian psycopg2 incompatible with Python 3.12, installing psycopg2-binary..." && \
     pip3 install --no-cache-dir psycopg2-binary && \
     python3 -c "import psycopg2; print(f'✓ psycopg2-binary {psycopg2.__version__}')") && \
    rm -rf /tmp/psycopg2_debian

# Test psycopg2 installation
RUN echo "=== Final psycopg2 test ===" && \
    python3 <<'PYEOF'
import psycopg2
print(f'✓ psycopg2 version: {psycopg2.__version__}')
print(f'✓ psycopg2 location: {psycopg2.__file__}')
from psycopg2 import extensions, extras
print('✓ psycopg2.extensions: OK')
print('✓ psycopg2.extras: OK')
PYEOF

# Locales setup
RUN set -euo pipefail; \
    IFS=',' read -r -a REQ_LOCALES <<< "${LOCALES}"; \
    for loc in "${REQ_LOCALES[@]}"; do \
        loc="$(echo "$loc" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"; \
        [ -n "$loc" ] || continue; \
        sed -i "s/^# *${loc//\//\\/}$/${loc}/" /etc/locale.gen || true; \
        grep -qxF "${loc}" /etc/locale.gen || echo "${loc}" >> /etc/locale.gen; \
    done && locale-gen

# NPM tools
RUN npm install -g rtlcss@4.1.0 && npm cache clean --force

# PostgreSQL client
RUN install -d /usr/share/postgresql-common/pgdg && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    PG_VERSION="$(psql --version | awk '{print $3}')" && \
    echo "POSTGRESQL_VERSION='${PG_VERSION}'" >> /tmp/metadata.env && \
    rm -f /etc/apt/sources.list.d/pgdg.list && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install missing lxml-html-clean via pip and create dummy deb package
RUN echo "=== Installing lxml-html-clean and creating dummy package ===" && \
    apt-get update && \
    apt-get install -y --no-install-recommends equivs && \
    pip3 install --no-cache-dir 'lxml[html_clean]' && \
    python3 -c "import lxml.html.clean; print('✓ lxml.html.clean installed successfully')" && \
    mkdir -p /tmp/dummy-pkg && \
    cd /tmp/dummy-pkg && \
    echo "Section: python" > python3-lxml-html-clean && \
    echo "Priority: optional" >> python3-lxml-html-clean && \
    echo "Standards-Version: 3.9.2" >> python3-lxml-html-clean && \
    echo "" >> python3-lxml-html-clean && \
    echo "Package: python3-lxml-html-clean" >> python3-lxml-html-clean && \
    echo "Version: 999.0" >> python3-lxml-html-clean && \
    echo "Maintainer: Rosen <vladimirv.rosen@gmail.com>" >> python3-lxml-html-clean && \
    echo "Description: Dummy package for python3-lxml-html-clean" >> python3-lxml-html-clean && \
    echo " This is a dummy package that satisfies the dependency." >> python3-lxml-html-clean && \
    echo " The actual package is installed via pip." >> python3-lxml-html-clean && \
    equivs-build python3-lxml-html-clean && \
    dpkg -i python3-lxml-html-clean_*.deb && \
    cd / && \
    rm -rf /tmp/dummy-pkg && \
    apt-get purge -y equivs && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# Odoo installation
ARG ODOO_PACKAGE_URL="https://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/Packages"
RUN set -euo pipefail; \
    PKG_TMP="/tmp/odoo_packages" && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 -o "${PKG_TMP}" "${ODOO_PACKAGE_URL}" && \
    FILENAME="$(awk 'BEGIN{RS="";FS="\n"} /Package: odoo/{for(i=1;i<=NF;i++){if($i ~ /^Filename:/){sub(/^Filename: */,"",$i); print $i; exit}}}' "${PKG_TMP}")" && \
    VERSION="$(awk 'BEGIN{RS="";FS="\n"} /Package: odoo/{for(i=1;i<=NF;i++){if($i ~ /^Version:/){sub(/^Version: */,"",$i); print $i; exit}}}' "${PKG_TMP}")" && \
    SHA256="$(awk 'BEGIN{RS="";FS="\n"} /Package: odoo/{for(i=1;i<=NF;i++){if($i ~ /^SHA256:/){sub(/^SHA256: */,"",$i); print $i; exit}}}' "${PKG_TMP}")" && \
    if [[ -z "${FILENAME}" || -z "${SHA256}" || -z "${VERSION}" ]]; then \
        echo "ERROR: Could not determine Odoo Filename/SHA256/Version from Packages." >&2; exit 3; \
    fi && \
    echo "ODOO_FILENAME='${FILENAME}'" >> /tmp/metadata.env && \
    echo "ODOO_VERSION='${VERSION}'" >> /tmp/metadata.env && \
    echo "ODOO_SHA256='${SHA256}'" >> /tmp/metadata.env && \
    ODOO_URL="https://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/${FILENAME}" && \
    curl --fail --location --show-error --proto '=https' --tlsv1.2 -o /tmp/odoo.deb "${ODOO_URL}" && \
    echo "${SHA256}  /tmp/odoo.deb" | sha256sum -c - && \
    apt-get update && \
    apt-get install -y --no-install-recommends /tmp/odoo.deb && \
    rm -f /tmp/odoo.deb "${PKG_TMP}" && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Обединяване на метаданните и записване като ENV променливи
RUN set -eu; \
    . /tmp/metadata.env && \
    if [ -f /tmp/wkhtmltopdf_metadata.env ]; then \
        . /tmp/wkhtmltopdf_metadata.env; \
    else \
        WKHTMLTOPDF_VERSION='0.12.6.1-3'; \
        WKHTMLTOPDF_ARCHITECTURE='unknown'; \
        WKHTMLTOPDF_SHA='unknown'; \
    fi && \
    cat > /etc/build-info.env <<BUILDEOF
export BUILD_DATE="${BUILD_DATE}"
export BUILD_OS_NAME="${OS_NAME}"
export BUILD_OS_VERSION="${OS_VERSION}"
export BUILD_OS_VERSION_ID="${OS_VERSION_ID}"
export BUILD_ARCHITECTURE="${ARCHITECTURE}"
export BUILD_DEBIAN_VERSION="${DEBIAN_VERSION}"
export BUILD_PYTHON_VERSION="${PYTHON_VERSION}"
export BUILD_POSTGRESQL_VERSION="${POSTGRESQL_VERSION}"
export BUILD_WKHTMLTOPDF_VERSION="${WKHTMLTOPDF_VERSION}"
export BUILD_WKHTMLTOPDF_ARCHITECTURE="${WKHTMLTOPDF_ARCHITECTURE}"
export BUILD_WKHTMLTOPDF_SHA="${WKHTMLTOPDF_SHA}"
export BUILD_ODOO_VERSION="${ODOO_VERSION}"
export BUILD_ODOO_FILENAME="${ODOO_FILENAME}"
export BUILD_ODOO_SHA256="${ODOO_SHA256}"
BUILDEOF

# Показване на build информацията
RUN cat /etc/build-info.env

# Добавяне на source на build-info в bashrc
RUN echo "if [ -f /etc/build-info.env ]; then . /etc/build-info.env; fi" >> /etc/bash.bashrc

LABEL maintainer="Rosen Vladimirov <vladimirv.rosen@gmail.com>"
LABEL description="Hardened, reproducible Odoo build on Python 3.12 Debian Bookworm"
LABEL version="1.0"
LABEL os.base_image="python:3.12-slim-bookworm"
LABEL python.version="3.12"
LABEL build.reproducible="true"
LABEL build.security_hardened="true"
LABEL build.info="/etc/build-info.env"

RUN install -d -m 0755 /etc/odoo
COPY --chown=root:root ./entrypoint.sh /
COPY --chown=odoo:odoo ./odoo.conf /etc/odoo/
COPY --chown=root:root ./addons.conf /etc/odoo/
COPY --chown=root:root ./wait-for-psql.py /usr/local/bin/
COPY --chown=root:root ./supervisor.py /usr/local/bin/

RUN chmod 0755 /entrypoint.sh /usr/local/bin/wait-for-psql.py /usr/local/bin/supervisor.py && \
    mkdir -p /mnt/extra-addons /opt/odoo && \
    chown -R odoo:odoo /mnt/extra-addons /opt/odoo && \
    rm -f /tmp/metadata.env /tmp/wkhtmltopdf_metadata.env

VOLUME ["/var/lib/odoo", "/var/log/odoo", "/mnt/extra-addons", "/opt/odoo"]
EXPOSE 8069 8071 8072

USER odoo
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]