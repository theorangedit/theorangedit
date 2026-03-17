#!/bin/bash

# start rsyslog service
rsyslogd

# fix permissions of docker-compose volume
# https://github.com/moby/moby/issues/2259
# https://github.com/docker/compose/issues/3270
chown -R $REDDIT_USER:$REDDIT_GROUP /srv/www/media

# wait for cassandra
while ! nc -vz $CASSANDRA_HOST $CASSANDRA_PORT; do
    echo "Waiting for Cassandra..."
    sleep 1
done

# init cassandra keyspace and column families
python3 <<END
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy

cluster = Cluster(["$CASSANDRA_HOST"], port=$CASSANDRA_PORT,
                  load_balancing_policy=RoundRobinPolicy())
session = cluster.connect()

keyspaces = [r.keyspace_name for r in session.execute(
    "SELECT keyspace_name FROM system_schema.keyspaces")]

if "reddit" not in keyspaces:
    print("creating keyspace 'reddit'")
    session.execute("""
        CREATE KEYSPACE reddit
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'}
    """)
    print("done")

session.set_keyspace("reddit")

tables = [r.table_name for r in session.execute(
    "SELECT table_name FROM system_schema.tables WHERE keyspace_name='reddit'")]

if "permacache" not in tables:
    print("creating table 'permacache'")
    session.execute("""
        CREATE TABLE permacache (
            key text PRIMARY KEY,
            value blob
        )
    """)
    print("done")

cluster.shutdown()
END

# wait for postgres
while ! nc -vz $POSTGRES_HOST $POSTGRES_PORT; do
    echo "Waiting for Postgres..."
    sleep 1
done

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
