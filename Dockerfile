FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates ncurses-base && rm -rf /var/lib/apt/lists/* && useradd -m -d /home/container container
USER container
ENV USER=container HOME=/home/container PYTHONPATH=/home/container/vendor/python
WORKDIR /home/container
CMD ["python3", "server.py"]
