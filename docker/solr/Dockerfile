FROM solr:9-slim

# Copy Reddit schema and config into the _default configset so the
# auto-created core picks them up on first start.
COPY solr/managed-schema.xml /opt/solr/server/solr/configsets/_default/conf/managed-schema.xml
COPY solr/solrconfig.xml      /opt/solr/server/solr/configsets/_default/conf/solrconfig.xml

# The SOLR_CORES env var tells the entrypoint script to create this core
# on first startup if it doesn't already exist.
ENV SOLR_CORES=reddit
