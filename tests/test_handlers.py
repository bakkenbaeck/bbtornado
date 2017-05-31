from unittest import TestCase

from tornado.web import HTTPError

from bbtornado.handlers import json_requires


class MockClass:

    def __init__(self):
        self.json_data = None

    def test_json_data(self, **data):
        """
        Convenience method for setting the json-data in our mock-object and calling the `@json_requires`
        decorated method.
        """
        self.json_data = data
        self.mock_method()

    @json_requires("a", "b", "c")
    def mock_method(self):
        """
        In a handler this would be the get, put, post or delete method.
        """
        return True


class JsonRequiresTest(TestCase):

    def __init__(self, *args, **kwargs):
        super(JsonRequiresTest, self).__init__(*args, **kwargs)
        self.handler = None

    def setUp(self):
        self.handler = MockClass()

    def test_pass_on_valid_input(self):
        """
        The `@json_requires` decorator doesn't raise an exception when it shouldn't.
        """
        self.handler.test_json_data(a=1, b=2, c=3)

    def test_invalid_input(self):
        """
        The `@json_requires` decorator does raise an error when missing a required json-field.
        """
        try:
            self.handler.test_json_data(a=1, b=2)
            raise Exception("Expected HTTPError")

        except HTTPError as e:
            self.assertEqual(e.status_code, 400)
