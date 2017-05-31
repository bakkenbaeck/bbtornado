import operator
from datetime import datetime, date

from sqlalchemy import Column, types, ForeignKey
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from tornado.testing import AsyncTestCase

from bbtornado.models import BaseModel, Base


class MockModel(Base, BaseModel):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(types.Integer, primary_key=True)
    _canceled = Column(types.Boolean)

    @property
    def canceled(self):
        return self._canceled

    @canceled.setter
    def canceled(self, value):
        self._canceled = value

    datetime = Column(types.DateTime)
    date = Column(types.Date,)
    name = Column(types.String, nullable=False)

    child_id = Column(types.Integer, ForeignKey('mockmodel.id'), nullable=True)
    child = relationship("MockModel", foreign_keys='MockModel.child_id', uselist=False)

    _json_fields_public = ['canceled']
    _json_fields_hidden = ['child_id', '_canceled']


def create_mock_object():
    obj = MockModel()
    obj.id = 1
    obj.canceled = True
    obj.datetime = datetime.utcfromtimestamp(1284101485)
    obj.date = datetime.utcfromtimestamp(1284101485).date()
    obj.name = "Name"
    return obj


def key_sort(x):
    return sorted(x.items(), key=operator.itemgetter(0))


class ToJsonTest(AsyncTestCase):
    """
    Test that _to_json() in bbtornado's BaseModel works as it should.

    Indirect tests:
     - Properties can be shown by adding the property name to _json_fields_public
     - fields are hidden when added to _json_fields_hidden

    """

    def test_to_json_output(self):
        """
        _to_json() returns dict with the correct number of fields and the expected values
        """
        expectation = {
            "datetime": "2010-09-10T06:51:25Z",
            "name": "Name",
            "canceled": True,
            "id": 1,
            "date": "2010-09-10",
            "child": None
        }

        self.assertEquals(create_mock_object()._to_json(), expectation)

    def test_extra_fields(self):
        """
        _to_json() returns the right fields when using extra_fields with "!" and "^"
        """
        expectation1 = {
            "name": "Name",
            "id": 1
        }
        self.assertEquals(create_mock_object()._to_json(extra_fields=['^id', '^name']), expectation1)

        expectation2 = {
            "datetime": "2010-09-10T06:51:25Z",
            "canceled": True,
            "date": "2010-09-10",
            "child": None
        }
        self.assertEquals(create_mock_object()._to_json(extra_fields=['!id', '!name']), expectation2)

    def test_extra_fields_relationships(self):
        """
        _to_json() is capable of returning nested objects (relationships)
        """
        expectation = {
            "name": "Name",
            "child": {
                "datetime": "2010-09-10T06:51:25Z",
                "canceled": True,
                "date": "2010-09-10",
                "id": 1,
                "child": None
            }
        }

        obj = create_mock_object()
        obj.child = create_mock_object()

        self.assertEquals(obj._to_json(extra_fields=['^name', '^child', 'child.!name']), expectation)
