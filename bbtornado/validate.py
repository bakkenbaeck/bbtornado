from tornado.concurrent import is_future
from tornado.gen import Return, coroutine

from functools import wraps
import collections
import jsonschema

from jsend import JSendMixin
from handlers import JsonError


'''
Use the @validate_json decorator to
- Verify json input (field names, types, required, enums, ...)
- Checks formats (e.g. email)
- Optional: Verify json output (raise 500 on error)
- Optional: Support jsend response format via mixin

Note: The decorator turns the function it wraps into a coroutine!


Example:

    @validate_json(
        input_schema={
            "$schema": "http://json-schema.org/schema#",
            "title": "Signup",
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string"
                },
                "last_name": {
                    "type": "string"
                },
                "email": {
                    "type": "string",
                    "format": "email"
                },
                "phone": {
                    "type": "string"
                },
                "role": {
                    "enum": ['sales', 'marketing', 'development']
                }
            },
            "required": ["first_name", "last_name", "email", "phone"]
        }
    )
    def signup_new_user(self):
        ...

'''


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
                object_defaults = get_schema_defaults(schema)
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


# based on
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
                        self.json_data = deep_update(defaults, self.json_data)

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
                raise JsonError(404, "Not found.")

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
