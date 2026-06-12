FROM registry.cern.ch/inveniosoftware/almalinux:1 as deps

RUN dnf -y install python3.12 python3.12-devel python3.12-libs python3.12-pip && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    alternatives --set python3 /usr/bin/python3.12 && \
    python3.12 -m pip install --upgrade pip && \
    python3.12 -m pip install pipenv

COPY site ./site
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system

FROM deps as assets-builder

RUN dnf -y module enable nodejs:20 && \
    dnf -y install nodejs && \
    dnf clean all

COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}
COPY ./assets/ ${INVENIO_INSTANCE_PATH}/assets/
COPY ./static/ ${INVENIO_INSTANCE_PATH}/static/
COPY ./templates/ ${INVENIO_INSTANCE_PATH}/templates/

RUN invenio collect --verbose && \
    invenio webpack buildall

FROM deps

COPY ./docker/uwsgi/ ${INVENIO_INSTANCE_PATH}
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}
COPY ./templates/ ${INVENIO_INSTANCE_PATH}/templates/
COPY ./app_data/ ${INVENIO_INSTANCE_PATH}/app_data/
COPY ./translations/ ${INVENIO_INSTANCE_PATH}/translations/
COPY ./ .

COPY --from=assets-builder ${INVENIO_INSTANCE_PATH}/static/ /opt/invenio/var/instance/static/

ENV INVENIO_SITE_UI_URL=https://localhost
ENV INVENIO_SITE_API_URL=https://localhost/api

EXPOSE 5000

CMD ["uwsgi", "/opt/invenio/var/instance/uwsgi_ui.ini"]
