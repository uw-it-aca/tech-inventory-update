FROM gcr.io/uwit-mci-axdd/django-container:1.3.1 as app-container

ADD --chown=acait:acait github_inventory/VERSION /app/github_inventory/
ADD --chown=acait:acait setup.py /app/
ADD --chown=acait:acait requirements.txt /app/
RUN . /app/bin/activate && pip install -r requirements.txt

ADD --chown=acait:acait . /app/
ADD --chown=acait:acait docker/ project/

FROM gcr.io/uwit-mci-axdd/django-test-container:1.3.1 as app-test-container

COPY --from=app-container /app/ /app/
