FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /srv

RUN useradd --system --uid 10001 --home-dir /srv --shell /usr/sbin/nologin cauldron \
	&& mkdir -p /data \
	&& chown cauldron:cauldron /data

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
	CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1

# The entrypoint fixes ownership of the /data volume, then runs CMD as the
# unprivileged "cauldron" user.
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
