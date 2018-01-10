import json

from datetime import datetime
import dateutil.tz

from tornado.httpclient import AsyncHTTPClient
from tornado.gen import coroutine


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



_json = { 'Content-type': 'application/json' }

class HTTP(object):
    """
    a more user-friendly (i.e. requests like :) )
    wrapper for using tornado async http-client with json endpoints
    """

    def __init__(self, client=None, base=None, cookie=None):
        self.base = base or ''
        self.client = client or AsyncHTTPClient()
        self.cookie = cookie

    @coroutine
    def _fetch(self, *args, headers=None, **kwargs):

        if not headers: headers = {}

        # this could re-use httpheaders util from tornado,
        # that would give correct case insensitivity
        if 'Cookie' not in headers and self.cookie: headers['Cookie'] = self.cookie

        r = yield self.client.fetch(*args, headers=headers, **kwargs)

        if 'Set-Cookie' in r.headers:
            # we only support one cookie, we could parse and keep a dict
            self.cookie = r.headers['Set-Cookie']


        return r


    @coroutine
    def post(self, url, body=None, headers=None, raise_error=True):

        r = yield self._fetch(self.base+url, body=json.dumps(body) if body is not None else None,
                              allow_nonstandard_methods=True,
                              method='POST', headers=dict(**_json if body is not None else {}, **headers or {}), raise_error=raise_error)

        return json.loads(r.body)


    @coroutine
    def put(self, url, body, headers={}, raise_error=True):

        r = yield self._fetch(self.base+url, body=json.dumps(body),
                              method='PUT', headers=dict(**_json, **headers), raise_error=raise_error)

        return json.loads(r.body)

    @coroutine
    def get(self, url, headers={}, raise_error=True):

        r = yield self._fetch(self.base+url, method='GET', headers=headers, raise_error=raise_error)

        return json.loads(r.body)


    @coroutine
    def delete(self, url, headers={}, raise_error=True):

        r = yield self._fetch(self.base+url, method='DELETE', headers=headers, raise_error=raise_error)

        return json.loads(r.body)
