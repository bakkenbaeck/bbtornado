from tornado.concurrent import is_future

from functools import wraps
import collections
import jsonschema

from bbtornado.jsend import JSendMixin
from bbtornado.handlers import JsonError
from bbtornado.models import _to_json


'''
Use the validate_json utility function to verify a json object or string
against a given schema. An exception (jsonschema.ValidationError) is
raised in case of errors.

Use the @validate_json_input decorator to
- Verify json input (field names, types, required, enums, ...)
- Checks formats (e.g. email)

Use the @validate_json_output decorator to
- Verify json output (raise 500 on error)
- Optional: Support jsend response format via mixin


Example:

    @validate_json_input(
        input_schema={
            "$schema": "http://json-schema.org/schema#",
            "title": "Signup",
            "type": "object",
            "additionalProperties": False,
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

# based on
# https://github.com/hfaran/Tornado-JSON/blob/master/tornado_json/schema.py


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


def validate_json(json_data,
                  json_schema=None,
                  json_example=None,
                  validator_cls=None,
                  format_checker=jsonschema.FormatChecker(),
                  on_empty_404=False):
    # if output is empty, auto return the error 404.
    if not json_data and on_empty_404:
        raise JsonError(404, "Not found.")

    if json_schema is not None:
        json_data = _to_json(json_data)
        # We wrap output in an object before validating in case
        # output is a string (and ergo not a validatable JSON
        # object)
        jsonschema.validate(
            {
                "result": json_data
            },
            {
                "type": "object",
                "properties": {
                    "result": json_schema
                },
                "required": ["result"]
            },
            cls=validator_cls,
            format_checker=format_checker
        )

    return json_data


def validate_json_input(input_schema=None,
                        input_example=None,
                        validator_cls=None,
                        format_checker=jsonschema.FormatChecker(),
                        use_defaults=True):
    """Parameterized decorator for input schema validation
    :type validator_cls: IValidator class
    :type format_checker: jsonschema.FormatChecker or None
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
        :type  rh_method: function
        :param rh_method: The RequestHandler method to be decorated
        :returns: The decorated method
        :raises ValidationError: If input is invalid as per the schema
            or malformed
        """
        @wraps(rh_method)
        def _wrapper(self, *args, **kwargs):
            if input_schema is None:
                # no schema provided => clear input data
                self.json_data = {}
            else:
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
                    validate_json(
                        json_data=self.json_data,
                        json_schema=input_schema,
                        json_example=input_example,
                        validator_cls=validator_cls,
                        format_checker=format_checker,
                        on_empty_404=False
                    )
                except jsonschema.ValidationError as e:
                    field = '.'.join(e.path)
                    msg = "%s: %s" % (field, e.message) if field \
                          else e.message
                    if isinstance(self, JSendMixin):
                        self.fail(message=msg,
                                  field=field)
                    raise JsonError(400, msg, field)
            return rh_method(self, *args, **kwargs)

        setattr(_wrapper, "input_schema", input_schema)
        setattr(_wrapper, "input_example", input_example)
        return _wrapper
    return _validate


def validate_json_output(output_schema=None,
                         output_example=None,
                         validator_cls=None,
                         format_checker=jsonschema.FormatChecker(),
                         on_empty_404=False,
                         write_json=True):
    """Parameterized decorator for schema validation
    :type validator_cls: IValidator class
    :type format_checker: jsonschema.FormatChecker or None
    :type on_empty_404: bool
    :param on_empty_404: If this is set, and the result from the
        decorated method is a falsy value, a 404 will be raised.
    :type use_defaults: bool
    :param write_json: If set to True (default), write a json representation
                       of the output to the response body
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
        def _wrapper(self, *args, **kwargs):
            # Call the requesthandler method
            output = rh_method(self, *args, **kwargs)

            def validate_output(output):
                # in case output is a future, we can be sure it is finished
                if is_future(output):
                    output = output.result()

                json_data = validate_json(
                    json_data=output,
                    json_schema=output_schema,
                    json_example=output_example,
                    validator_cls=validator_cls,
                    format_checker=format_checker,
                    on_empty_404=on_empty_404
                )

                if json_data and write_json and \
                   not self._finished:
                    if isinstance(self, JSendMixin):
                        self.success(json_data)
                    else:
                        self.write(json_data)

            # If the rh_method returned a Future a la `raise Return(value)`, we
            # don't evaluate it immediately
            if is_future(output):
                output.add_done_callback(validate_output)
                return output
            else:
                # Validate the obtained output, but don't catch
                # any exceptions, so that errors result in status
                # code 500
                validate_output(output)

        setattr(_wrapper, "output_schema", output_schema)
        setattr(_wrapper, "output_example", output_example)
        return _wrapper
    return _validate
