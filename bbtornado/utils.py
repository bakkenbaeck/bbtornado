from datetime import datetime
import dateutil.tz

def now():
    """ A datetime of now with timezone """
    return datetime.now(dateutil.tz.tzutc())
