#!/bin/bash

# start rsyslog service
rsyslogd

# fix permissions of docker-compose volume
# https://github.com/moby/moby/issues/2259
# https://github.com/docker/compose/issues/3270
chown -R $REDDIT_USER:$REDDIT_GROUP /srv/www/media

# wait for postgres
while ! nc -vz $POSTGRES_HOST $POSTGRES_PORT; do
    echo "Waiting for Postgres..."
    sleep 1
done

# run Alembic migrations (idempotent — safe to run on every startup)
cd /home/reddit/src/reddit/r2
python3 -m alembic upgrade head

# wait for rabbitmq
while ! nc -vz $RABBITMQ_HOST $RABBITMQ_PORT; do
    echo "Waiting for RabbitMQ..."
    sleep 1
done

# init reddit app
REDDIT_INIT_ONCE="/home/reddit/install-complete"
if [ ! -e $REDDIT_INIT_ONCE ]; then
    echo "Initializing reddit with inject_configuration_data()..."
    touch $REDDIT_INIT_ONCE
    cd /home/reddit/src/reddit/r2 && python3 scripts/inject_test_data.py inject_configuration_data
fi

# start cron service
chmod go-rwx /etc/cron.d/reddit
cron

# supervisord is the main docker foreground process
/usr/bin/supervisord -n
