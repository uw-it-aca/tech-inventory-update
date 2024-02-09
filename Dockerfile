FROM python:3.10 as app-container

WORKDIR /app/
ENV PYTHONUNBUFFERED 1
ENV LOG_FILE stdout

RUN groupadd -r acait -g 1000 && \
    useradd -u 1000 -rm -g acait -d /home/acait -s /bin/bash -c "container user" acait && \
    chown -R acait:acait /app && \
    chown -R acait:acait /home/acait

USER acait

ADD --chown=acait:acait setup.py /app/
ADD --chown=acait:acait requirements.txt /app/
RUN pip install -r requirements.txt

ADD --chown=acait:acait . /app/
ADD --chown=acait:acait docker/settings.py /app/github_inventory_settings.py
ADD --chown=acait:acait docker/run.sh /scripts/run.sh
RUN chmod -R +x /scripts /app/update_github_sheet.py
