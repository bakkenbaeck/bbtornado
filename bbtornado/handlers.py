import os
import tornado.web
import traceback
import threading
import logging
import socket

from functools import wraps, partial

from concurrent.futures import ThreadPoolExecutor
from tornado.escape import json_decode
from tornado.web import HTTPError
from tornado.util import ObjectDict


from six import with_metaclass


log = logging.getLogger('bbtornado')

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

class JsonError(HTTPError):
    def __init__(self, status_code, message, details=None):
        HTTPError.__init__(self, status_code, log_message=message, reason=message)
        self.details = details

class JsonErrorHandler():
    def write_error(self, code, **args):

        if code == 500:
            log.error("[%s] 500 error: %s %s %s"%(socket.gethostname(), self.request.method, self.request.uri, self.request.body))

        out = dict(status=code)

        if "exc_info" in args:
            typ, ex, st = args["exc_info"]
            if typ in (JsonError, HTTPError) :
                out['msg'] = ex.log_message
                if hasattr(ex, 'details') and ex.details: out["details"] = ex.details

        self.write(out)
        self.finish()




class ThreadRequestContextMeta(type):
    # property() doesn't work on classmethods,
    #  see http://stackoverflow.com/q/128573/1231454
    @property
    def data(cls):
        if not hasattr(cls._state, 'data'):
           return ObjectDict()
        return cls._state.data


class ThreadRequestContext(with_metaclass(ThreadRequestContextMeta)):
    """A context manager that saves some per-thread state globally.
    Intended for use with Tornado's StackContext.

    Provide arbitrary data as kwargs upon creation,
    then use ThreadRequestContext.data to access it.
    """

    _state = threading.local()
    _state.data = {}

    def __init__(self, **data):
        self._data = ObjectDict(data)

    def __enter__(self):
        self._prev_data = self.__class__.data
        self.__class__._state.data = self._data

    def __exit__(self, *exc):
        self.__class__._state.data = self._prev_data
        del self._prev_data
        return False

class BaseHandler(tornado.web.RequestHandler):

    def _execute(self, transforms, *args, **kwargs):
        """
        Override this to save some data in a StackContact local dict
        """
        global_data = dict(request=self.request)

        with tornado.stack_context.StackContext(partial(ThreadRequestContext, **global_data)):
            # this uses ORM, which needs a DB connection, which needs ThreadRequestContext.data.request
            # so it must be here.
            ThreadRequestContext.data.current_user = self.current_user
            return super(BaseHandler, self)._execute(transforms, *args, **kwargs)

    @property
    def db(self):
        if not hasattr(self, '_session'):
            self._session = self.application.Session()
        return self._session

    def on_finish(self):
        if hasattr(self, '_session') and self._session:
            self.application.Session.remove()
            del self._session

    def on_connection_close(self):
        self.on_finish()

    def get_current_user(self):
        user_id = self.get_secure_cookie('user_id')
        try:
            if self.application.user_model is not None:
                return self.db.query(self.application.user_model).get(int(user_id)) if user_id else None
            else:
                return int(user_id) if user_id else None
        except:
            log.exception('Exception while trying to get current user')
            return None

    @tornado.web.RequestHandler.current_user.setter
    def current_user(self, value):
        if self.application.user_model is not None and isinstance(value, self.application.user_model):
            value = value.id
        self.set_secure_cookie('user_id', str(value), domain=self.application.domain)


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
    def head(self, *args, **kwargs):
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


class FallbackStaticFileHandler(tornado.web.StaticFileHandler):

    def initialize(self, path=None, filename=None):

        self.filename = filename
        return tornado.web.StaticFileHandler.initialize(self, path=path)

    def write_error(self, status_code=500, **kwargs):
        if status_code == 404:
            self.set_status(200)
            return self.get(self.filename)
        elif status_code == 403 and 'is not a file' in kwargs['exc_info'][1].log_message:
            # Check for folders
            self.set_status(200)
            return self.get(self.filename)
        else:
            tornado.web.StaticFileHandler.write_error(self, status_code, **kwargs)
