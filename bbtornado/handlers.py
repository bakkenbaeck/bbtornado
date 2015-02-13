import os
import tornado.web
import traceback


from functools import wraps

from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import scoped_session
from tornado.escape import json_decode
from tornado.web import HTTPError


def authenticated(error_code=403, error_message="Not Found"):
    """Decorate methods with this to require that the user be logged in.
    If the user is not logged in, error_code will be set and error_message returned
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.current_user:
                raise tornado.web.HTTPError(error_code, reason=error_message)
            return method(self, *args, **kwargs)
        wrapper._needs_authentication = True
        return wrapper
    return decorator

class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        if not hasattr(self, '_session'):
            self._session = scoped_session(self.application.Session)
        return self._session

    def on_finish(self):
        if hasattr(self, '_session') and self._session:
            self._session.remove()
            del self._session

    def get_current_user(self):
        user_id = self.get_secure_cookie('user_id')
        if self.application.user_model is not None:
            return self.db.query(self.application.user_model).get(int(user_id)) if user_id else None
        else:
            return int(user_id) if user_id else None

    @tornado.web.RequestHandler.current_user.setter
    def current_user(self, value):
        if self.application.user_model is not None and isinstance(value, self.application.user_model):
            value = value.id
        self.set_secure_cookie('user_id', unicode(value))

    @property
    def executor(self):
        return self.get_executor()

    _default_executor = ThreadPoolExecutor(10)
    def get_executor(self):
        return self._default_executor

    def prepare(self):
        """Puts any json data into self.request.arguments"""
        if any(('application/json' in x for x in self.request.headers.get_list('Content-Type'))):
            try:
                json_data = json_decode(self.request.body)
            except ValueError:
                raise tornado.web.HTTPError(500, "Invalid JSON structure.", reason="Invalid JSON structure.")
            if type(json_data) != dict:
                raise tornado.web.HTTPError(500, "We only accept key value objects!", reason="We only accept key value objects!")
            self.json_data = json_data

    def _get_arguments(self, name, source, strip=True):
        """Override _get_arguments to also look-up json args"""
        values = tornado.web.RequestHandler._get_arguments(self, name, source, strip)

        if not values and hasattr(self, 'json_data') and name in self.json_data:
            values = self.json_data[name]
            if not isinstance(values, list):
                values = [values]

        return values



class JSONWriteErrorMixin(object):
    def write_error(self, status_code, **kwargs):
        rval = dict(code=status_code, message=self._reason)
        # only give exc_info when in debug mode
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            rval['exc_info'] = traceback.format_exception(*kwargs["exc_info"])
        self.write(rval)
        self.finish()

class SingleFileHandler(tornado.web.StaticFileHandler):
    def initialize(self,filename):
        path, self.filename = os.path.split(filename)
        return super(SingleFileHandler, self).initialize(path)
    def get(self, *args, **kwargs):
        return super(SingleFileHandler, self).get(self.filename)

def json_requires(*fields):

    def wrapper1(func):
        @wraps(func)
        def wrapper2(self, *args, **kwargs):

            if not hasattr(self, 'json_data'):
                raise HTTPError(400, "JSON Body required - check your body + headers")

            for f in fields:
                if f not in self.json_data: raise HTTPError(400, "Required field '%s' is missing."%(f,))

            return func(self, *args, **kwargs)

        return wrapper2


    return wrapper1
