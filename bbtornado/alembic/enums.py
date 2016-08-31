import logging
from sqlalchemy.dialects.postgresql import ENUM

"""
This file contains utility methods for dealing with enums in alembic
migration scripts.

This assumes a postgresql server

"""

log = logging.getLogger(__file__)

def create(op, name, values):

    enum = ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)

    return enum


def add_option(op, name, option):

    log.warn("This will roll back any upgrades done before this!")

    connection = None
    if not op.get_context().as_sql:
        connection = op.get_bind()
        connection.execution_options(isolation_level='AUTOCOMMIT')

    op.execute("ALTER TYPE %s ADD VALUE '%s'"%(name, option))

    if connection is not None:
        connection.execution_options(isolation_level='READ_COMMITTED')


def remove_option(op, name, option):

    raise Exception("lol - good luck!")
