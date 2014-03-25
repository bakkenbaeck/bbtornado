import sqlalchemy.orm

from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm.query import Query
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def _to_json(o):
    if isinstance(o, dict):
        o = {k: _to_json(v) for k,v in o.items()}
    elif isinstance(o, (list, tuple)):
        o = [_to_json(v) for v in o]
    elif isinstance(o, Query):
        rval = []
        for v in o:
            rval.append(_to_json(v))
        o = rval
    elif hasattr(o, '_to_json'):
        o = o._to_json()
    elif isinstance(o, Decimal):
        o = float(o)
    elif isinstance(o, (date, datetime,)):
        o = o.isoformat()
    return o

class BaseModel(object):
    def _to_json(self, private=False, extra_fields=[]):
        fields = [p.key for p in sqlalchemy.orm.object_mapper(self).iterate_properties]
        rval = {}
        for k in fields:
            if (not private and k in self._json_fields_private) or (k in self._json_fields_hidden):
                continue
            rval[k] = _to_json(getattr(self, k))
        return rval

    _json_fields_public = []
    _json_fields_private = []
    _json_fields_hidden = []

def init_db(engine=None):
    Base.metadata.create_all(bind=engine)

def drop_db(engine=None):
    Base.metadata.drop_all(bind=engine)
