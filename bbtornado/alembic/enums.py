import logging
from sqlalchemy.dialects.postgresql import ENUM

"""
This file contains utility methods for dealing with enums in alembic
migration scripts.

This assumes a postgresql server

Both creation/adding options will gracefully handle enum/options
already existing.

Downgrading is not supported.

This requires that you set `transaction_per_migration=True` in the config clause for alembic:

i.e. in the env.py file:

```
    context.configure(
        transaction_per_migration=True,
        connection=connection,
        target_metadata=target_metadata
    )
```


"""

log = logging.getLogger(__file__)

def create(op, name, *values):

    enum = ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)

    return enum


def add_options(op, name, *options):

    log.warn("This will roll back any upgrades done before this!")

    connection = None
    if not op.get_context().as_sql:
        connection = op.get_bind()
        connection.execution_options(isolation_level='AUTOCOMMIT')

    for option in options:
        op.execute("ALTER TYPE %s ADD VALUE IF NOT EXISTS '%s'"%(name, option))

    if connection is not None:
        connection.execution_options(isolation_level='READ_COMMITTED')


def remove_option(op, name, option):

    raise Exception("lol - good luck!")

def existing(name):
    return ENUM(name=name, create_type=False)
