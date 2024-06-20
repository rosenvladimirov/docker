FROM debian:bullseye-slim
MAINTAINER Rosen Vladimirov <vladimirov.rosen@gmail.com>

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG C.UTF-8
ENV PIPX_BIN_DIR=/usr/local/bin
ENV PIPX_DEFAULT_PYTHON=python3
ENV DEBIAN_FRONTEND noninteractive

# Retrieve the target architecture to install the correct wkhtmltopdf package
ARG TARGETARCH

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        dirmngr \
        fonts-noto-cjk \
        gnupg \
        libssl-dev \
        node-less \
        npm \
        python3-venv \
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
    case ${TARGETARCH} in \
    "amd64") WKHTMLTOPDF_ARCH=amd64 && WKHTMLTOPDF_SHA=cecbf5a6abbd68d324a7cd6c51ec843d71e98951 && WKHTMLTOPDF_ARCH=0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_${TARGETARCH}  ;; \
    "arm64")  WKHTMLTOPDF_SHA=abf9e031dd561b46e82744b72588d9c5d4c303ca && WKHTMLTOPDF_ARCH=0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_${TARGETARCH}  ;; \
    "arm")  WKHTMLTOPDF_SHA=538b88cdfb5ea5e99a175ab6aeaacb92b3c722f7 && WKHTMLTOPDF_ARCH=0.12.6.1-2/wkhtmltox_0.12.6.1-2.raspberrypi.bullseye_armhf  ;; \
    "ppc64le" | "ppc64el") WKHTMLTOPDF_SHA=47fd255b8a729fbc4cb4705bad7c11e315c30e0c && WKHTMLTOPDF_ARCH=0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_ppc64el  ;; \
    esac \
    && curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_ARCH}.deb \
    && echo ${WKHTMLTOPDF_SHA} wkhtmltox.deb | sha1sum -c - \
    && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* wkhtmltox.deb  \
    && pip3 install pipx \
    && pipx ensurepath

# install latest postgresql-client
RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ bullseye-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
    && GNUPGHOME="$(mktemp -d)" \
    && export GNUPGHOME \
    && repokey='B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8' \
    && gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "${repokey}" \
    && gpg --batch --armor --export "${repokey}" > /etc/apt/trusted.gpg.d/pgdg.gpg.asc \
    && gpgconf --kill all \
    && rm -rf "$GNUPGHOME" \
    && apt-get update  \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -f /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Install rtlcss (on Debian buster)
RUN npm install -g rtlcss

# Install Odoo
ENV ODOO_VERSION 16.0
ARG ODOO_RELEASE=20240416
ARG ODOO_SHA=d9418fee3ef105b40a58d89b8c7c500d34743ed5
RUN curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
    && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
    && apt-get update \
    && apt-get -y install --no-install-recommends ./odoo.deb \
    && rm -rf /var/lib/apt/lists/* odoo.deb

# Copy entrypoint script and Odoo configuration file
COPY ./entrypoint.sh /
COPY ./odoo.conf /etc/odoo/

# Set permissions and Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
RUN chown odoo /etc/odoo/odoo.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons \
    && mkdir -p /opt/odoo/odoo-16.0/oca \
    && chown -R odoo /opt/odoo

#RUN case ${TARGETARCH} in \
#    "amd64") pipx install oca-maintainers-tools@git+https://github.com/OCA/maintainer-tools.git && oca-clone-everything --target-branch 16.0 /opt/odoo/odoo-16.0/oca ;; \
#    "arm64") pipx install oca-maintainers-tools@git+https://github.com/OCA/maintainer-tools.git && oca-clone-everything --target-branch 16.0 /opt/odoo/odoo-16.0/oca ;; \
#    esac

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/opt/odoo"]
COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py
COPY make_symb_links.py /usr/local/bin/make_symb_links.py
RUN chmod +x /usr/local/bin/make_symb_links.py && \
    chmod +x /usr/local/bin/wait-for-psql.py

# Expose Odoo services
EXPOSE 8069 8071 8072

# Set the default config file
ENV ODOO_RC /etc/odoo/odoo.conf

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py
COPY make_symb_links.py /usr/local/bin/make_symb_links.py
RUN chmod +x /usr/local/bin/make_symb_links.py

# Set default user when running the container
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
