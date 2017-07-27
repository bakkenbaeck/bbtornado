from datetime import datetime
import dateutil.tz
from sqlalchemy import func

def now():
    """A datetime of now with timezone"""
    return datetime.now(dateutil.tz.tzutc())

def today():
    """A datetime of midnight today"""
    now = datetime.now(dateutil.tz.tzutc())
    return datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)

def count_results(q):
    """Returns the count for the supplied sqlalchemy query"""
    # https://gist.github.com/hest/8798884
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count
