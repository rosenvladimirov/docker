FROM debian:bookworm
LABEL maintainer="Rosen Vladimirov <vladimirv.rosen@gmail.com>"

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG=en_US.UTF-8
ENV PYTHONPATH=/opt/python3

# Retrieve the target architecture to install the correct wkhtmltopdf package
ARG TARGETARCH
ARG DISTRO
ARG ODOO_SHA
ARG WKHTMLTOPDF_URL
ARG WKHTMLTOPDF_VERSION

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
        lsb-release \
        ca-certificates \
        curl \
        dirmngr \
        fonts-noto-cjk \
        gnupg \
        libssl-dev \
        node-less \
        npm \
        gcc \
        g++ \
        libicu-dev \
        pkg-config \
        python3-dev \
        python3-magic \
        python3-num2words \
        python3-odf \
        python3-pdfminer \
        python3-pip \
        python3-phonenumbers \
        python3-pyldap \
        python3-qrcode \
        python3-renderpm \
        python3-setuptools \
        python3-slugify \
        python3-vobject \
        python3-watchdog \
        python3-xlrd \
        python3-xlwt \
        python3-transliterate \
        xz-utils && \
    if [ -z "${TARGETARCH}" ]; then \
        TARGETARCH="$(dpkg --print-architecture)"; \
    fi; \
    WKHTMLTOPDF_ARCH=${TARGETARCH} && \
    WKHTMLTOPDF_URL=https://github.com/wkhtmltopdf/packaging/releases/download && \
    WKHTMLTOPDF_VERSION=0.12.6.1-3 && \
    DISTRO=$(lsb_release -cs) && \
    case ${TARGETARCH} in \
    "amd64") WKHTMLTOPDF_SHA=e9f95436298c77cc9406bd4bbd242f4771d0a4b2  ;; \
    "arm64") WKHTMLTOPDF_SHA=77bc06be5e543510140e6728e11b7c22504080d4  ;; \
    "armhf") DISTRO=raspberrypi.${DISTRO} && WKHTMLTOPDF_SHA=538b88cdfb5ea5e99a175ab6aeaacb92b3c722f7 ;; \
    "ppc64le" | "ppc64el") WKHTMLTOPDF_ARCH=ppc64el && WKHTMLTOPDF_SHA=47fd255b8a729fbc4cb4705bad7c11e315c30e0c  ;; \
    esac \
    && curl -o wkhtmltox.deb -sSL ${WKHTMLTOPDF_URL}/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.${DISTRO}_${WKHTMLTOPDF_ARCH}.deb \
    && echo ${WKHTMLTOPDF_SHA} wkhtmltox.deb | sha1sum -c - \
    && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* wkhtmltox.deb

# install latest postgresql-client
RUN install -d /usr/share/postgresql-common/pgdg \
    && curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' \
    && apt-get update  \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -f /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Install rtlcss (on Debian buster)
RUN npm install -g rtlcss

# Install Odoo
ENV ODOO_VERSION 17.0
ARG ODOO_RELEASE=latest
RUN ODOO_SHA=$(curl -sSL https://nightly.odoo.com/17.0/nightly/deb/Packages | grep -F SHA1 | cut -d ' ' -f2) \
    && curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
    && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
    && apt-get update \
    && apt-get -y install --no-install-recommends ./odoo.deb \
    && rm -rf /var/lib/apt/lists/* odoo.deb

RUN pip3 install --upgrade --break-system-packages pip

# Copy entrypoint script and Odoo configuration file
COPY --chown=root:root ./entrypoint.sh /
COPY ./odoo.conf /etc/odoo/
COPY ./addons.conf /etc/odoo/

# Set permissions and Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
RUN chown odoo /etc/odoo/odoo.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo:odoo /mnt/extra-addons \
    && mkdir -p /opt/odoo \
    && mkdir -p $PYTHONPATH \
    && chown -R odoo:odoo /opt/odoo
VOLUME ["/var/lib/odoo", "/var/log/odoo", "/mnt/extra-addons", "/opt/odoo"]

# Expose Odoo services
EXPOSE 8069 8071 8072

# Set the default config file
ENV ODOO_RC /etc/odoo/odoo.conf

COPY --chown=root:root wait-for-psql.py /usr/local/bin/
COPY --chown=root:root ./supervisor.py /usr/local/bin/

# Set default user when running the container
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
