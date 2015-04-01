from datetime import datetime
import dateutil.tz

def now():
    """ A datetime of now with timezone """
    return datetime.now(dateutil.tz.tzutc())

def today():
    """ A datetime of midnight today"""

    now = datetime.now(dateutil.tz.tzutc())
    return datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
