"""
Custom PostgreSQL ranking functions used for sorting links.

These match the functions originally defined in tdb_sql.py and referenced
in ORDER BY clauses throughout the codebase. They are installed once on
each new connection via the SQLAlchemy engine event hook.
"""

import sqlalchemy as sa
from sqlalchemy import event


_FUNCTIONS_SQL = """
CREATE OR REPLACE FUNCTION hot(ups INTEGER, downs INTEGER, date TIMESTAMPTZ)
RETURNS FLOAT AS $$
DECLARE
    s FLOAT;
    order_ FLOAT;
    sign INT;
    seconds FLOAT;
BEGIN
    s := ups - downs;
    IF s > 0 THEN sign := 1;
    ELSIF s < 0 THEN sign := -1;
    ELSE sign := 0;
    END IF;
    order_ := log(greatest(abs(s), 1));
    seconds := extract(epoch FROM date) - 1134028003;
    RETURN round((sign * order_ + seconds / 45000.0)::numeric, 7);
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;


CREATE OR REPLACE FUNCTION score(ups INTEGER, downs INTEGER)
RETURNS FLOAT AS $$
BEGIN
    RETURN ups - downs;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;


CREATE OR REPLACE FUNCTION controversy(ups INTEGER, downs INTEGER)
RETURNS FLOAT AS $$
DECLARE
    magnitude FLOAT;
    balance FLOAT;
BEGIN
    IF downs <= 0 OR ups <= 0 THEN
        RETURN 0;
    END IF;
    magnitude := ups + downs;
    IF ups > downs THEN
        balance := downs::FLOAT / ups;
    ELSE
        balance := ups::FLOAT / downs;
    END IF;
    RETURN magnitude * balance;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;
"""


def install_functions(dbapi_conn, connection_record):
    """Install custom ranking functions. Registered on engine 'connect' event."""
    cursor = dbapi_conn.cursor()
    cursor.execute(_FUNCTIONS_SQL)
    dbapi_conn.commit()
    cursor.close()


def register(engine):
    """Register the install_functions hook on the given engine."""
    event.listen(engine, 'connect', install_functions)
