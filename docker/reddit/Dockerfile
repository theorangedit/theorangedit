FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

# for reddit installer
# WARNING: some of this is hardcoded in 'cron' and 'supervisord.conf' and 'docker-compose.yml'
ENV REDDIT_USER reddit
ENV REDDIT_GROUP nogroup
ENV REDDIT_HOME /home/reddit
ENV REDDIT_DOMAIN reddit.local
ENV REDDIT_PLUGINS ''
ENV INSTALL_PROFILE docker
ENV PGUSER reddit
ENV PGHOST postgres
# for container init
ENV CASSANDRA_HOST cassandra
ENV CASSANDRA_PORT 9042
ENV POSTGRES_HOST postgres
ENV POSTGRES_PORT 5432
ENV RABBITMQ_HOST rabbitmq
ENV RABBITMQ_PORT 5672
# for container run
ENV PYTHONPATH "${PYTHONPATH}:/home/reddit/src/reddit/r2"

RUN apt-get update && apt-get -y upgrade

# locale stuff
RUN apt-get -y install locales && \
    locale-gen en_US.UTF-8 && \
    dpkg-reconfigure locales
ENV LANG en_US.UTF-8

# rsyslog, cron
RUN apt-get -y install rsyslog cron netcat-openbsd
RUN touch /var/log/syslog
RUN chown syslog:adm /var/log/syslog

# supervisor
RUN apt-get -y install supervisor
RUN mkdir -p /var/log/supervisor

# reddit user
RUN apt-get -y install sudo
RUN useradd --create-home --shell /bin/bash reddit
RUN echo "reddit:password" | chpasswd
RUN adduser reddit sudo

# Python 3.11 and build dependencies
RUN apt-get -y install \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    build-essential \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    libmemcached-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libxml2-dev \
    libxslt1-dev \
    git \
    wget \
    nginx

# Make python3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN update-alternatives --install /usr/bin/python python python3.11 1
RUN python3 -m pip install --upgrade pip setuptools wheel

# Copy reddit source
COPY --chown=reddit:nogroup . /home/reddit/src/reddit/

# Install reddit r2 package and Python dependencies
RUN cd /home/reddit/src/reddit/r2 && pip3 install -e .

# reddit app cron replacement
COPY cron /etc/cron.d/reddit
RUN chmod go-rwx /etc/cron.d/reddit

# reddit app upstart replacement
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY init_container.sh init_container.sh
RUN chmod +x init_container.sh

EXPOSE 8001 9000 8082

CMD ["./init_container.sh"]
