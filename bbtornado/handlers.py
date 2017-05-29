import os
import tornado.web
import traceback
import threading
import logging
import socket
import jsonschema

from functools import wraps, partial

from concurrent.futures import ThreadPoolExecutor
from tornado.escape import json_decode
from tornado.web import HTTPError
from tornado.util import ObjectDict
from tornado.concurrent import is_future
from tornado.gen import Return, coroutine

from six import with_metaclass

from models import _to_json
from jsend import JSendMixin

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
        return super(SingleFileHandler, self).head(self.filename)

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


class NoObjectDefaults(Exception):

    """ Raised when a schema type object ({"type": "object"}) has no "default"
    key and one of their properties also don't have a "default" key.
    """
    pass


# copied from
# https://github.com/hfaran/Tornado-JSON/blob/master/tornado_json/schema.py
def get_schema_defaults(object_schema):
    """
    Extracts default values dict (nested) from an type object schema.
    :param object_schema: Schema type object
    :type  object_schema: dict
    :returns: Nested dict with defaults values
    """
    default = {}
    for k, schema in object_schema.get('properties', {}).items():

        if schema.get('type') == 'object':
            if 'default' in schema:
                default[k] = schema['default']

            try:
                object_defaults = get_object_defaults(schema)
            except NoObjectDefaults:
                if 'default' not in schema:
                    raise NoObjectDefaults
            else:
                if 'default' not in schema:
                    default[k] = {}

                default[k].update(object_defaults)
        else:
            if 'default' in schema:
                default[k] = schema['default']

    if default:
        return default

    raise NoObjectDefaults


# copied from
# https://github.com/hfaran/Tornado-JSON/blob/master/tornado_json/utils.py
def deep_update(source, overrides):
    """Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    :type source: collections.Mapping
    :type overrides: collections.Mapping
    :rtype: collections.Mapping
    """
    for key, value in overrides.items():
        if isinstance(value, collections.Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source


# copied from
# https://github.com/hfaran/Tornado-JSON/blob/master/tornado_json/schema.py
def validate_json(input_schema=None,
                  output_schema=None,
                  input_example=None,
                  output_example=None,
                  validator_cls=None,
                  format_checker=jsonschema.FormatChecker(),
                  on_empty_404=False,
                  use_defaults=False):
    """Parameterized decorator for schema validation
    :type validator_cls: IValidator class
    :type format_checker: jsonschema.FormatChecker or None
    :type on_empty_404: bool
    :param on_empty_404: If this is set, and the result from the
        decorated method is a falsy value, a 404 will be raised.
    :type use_defaults: bool
    :param use_defaults: If this is set, will put 'default' keys
        from schema to self.body (If schema type is object). Example:
            {
                'published': {'type': 'bool', 'default': False}
            }
        self.body will contains 'published' key with value False if no one
        comes from request, also works with nested schemas.
    """
    def _validate(rh_method):
        """Decorator for RequestHandler schema validation
        This decorator:
            - Validates request body against input schema of the method
            - Calls the ``rh_method`` and gets output from it
            - Validates output against output schema of the method
            - Calls ``JSendMixin.success`` to write the validated output
        :type  rh_method: function
        :param rh_method: The RequestHandler method to be decorated
        :returns: The decorated method
        :raises ValidationError: If input is invalid as per the schema
            or malformed
        :raises TypeError: If the output is invalid as per the schema
            or malformed
        :raises APIError: If the output is a falsy value and
            on_empty_404 is True, an HTTP 404 error is returned
        """
        @wraps(rh_method)
        @coroutine
        def _wrapper(self, *args, **kwargs):
            # In case the specified input_schema is ``None``, we
            #   don't json.loads the input, but just set it to ``None``
            #   instead.
            if input_schema is not None:
                # add default values to _input
                if use_defaults and input_schema.get('type') == 'object':
                    try:
                        defaults = get_schema_defaults(input_schema)
                    except NoObjectDefaults:
                        pass
                    else:
                        deep_update(defaults, self.json_data)

                try:
                    # Validate the received input
                    jsonschema.validate(
                        self.json_data,
                        input_schema,
                        cls=validator_cls,
                        format_checker=format_checker
                    )
                except jsonschema.ValidationError as e:
                    field = '.'.join(e.path)
                    msg = "%s: %s" % (field, e.message) if field \
                          else e.message
                    if isinstance(self, JSendMixin):
                        self.fail(message=msg,
                                  field=field)
                    raise JsonError(400, msg, field)
            else:
                self.json_data = {}

            # Call the requesthandler method
            output = rh_method(self, *args, **kwargs)
            # If the rh_method returned a Future a la `raise Return(value)`
            #   we grab the output.
            if is_future(output):
                output = yield output

            # if output is empty, auto return the error 404.
            if not output and on_empty_404:
                raise APIError(404, "Not found.")

            if output_schema is not None:
                # We wrap output in an object before validating in case
                #  output is a string (and ergo not a validatable JSON object)
                try:
                    jsonschema.validate(
                        {"result": output},
                        {
                            "type": "object",
                            "properties": {
                                "result": output_schema
                            },
                            "required": ["result"]
                        }
                    )
                except jsonschema.ValidationError as e:
                    # We essentially re-raise this as a TypeError because
                    #  we don't want this error data passed back to the client
                    #  because it's a fault on our end. The client should
                    #  only see a 500 - Internal Server Error.
                    raise TypeError(str(e))

            if output:
                if isinstance(self, JSendMixin):
                    self.success(output._to_json())
                else:
                    self.write(output._to_json())

            raise Return(output)

        setattr(_wrapper, "input_schema", input_schema)
        setattr(_wrapper, "output_schema", output_schema)
        setattr(_wrapper, "input_example", input_example)
        setattr(_wrapper, "output_example", output_example)

        return _wrapper
    return _validate
