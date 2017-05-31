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
    canceled = Column(types.Boolean)
    datetime = Column(types.DateTime)
    date = Column(types.Date,)
    name = Column(types.String, nullable=False)

    child_id = Column(types.Integer, ForeignKey('mockmodel.id'), nullable=True)
    child = relationship("MockModel", foreign_keys='MockModel.child_id', uselist=False)

    _json_fields_hidden = ['child_id']


def create_mock_object():
    obj = MockModel()
    obj.id = 1
    obj.canceled = True
    obj.datetime = datetime.fromtimestamp(1284101485)
    obj.date = date.fromtimestamp(1284101485)
    obj.name = "Name"
    return obj


def key_sort(x):
    return sorted(x.items(), key=operator.itemgetter(0))


class ToJsonTest(AsyncTestCase):

    def test_to_json_output(self):
        expectation = {
            "datetime": "2010-09-10T08:51:25Z",
            "name": "Name",
            "canceled": True,
            "id": 1,
            "date": "2010-09-10",
            "child": None
        }

        self.assertEquals(create_mock_object()._to_json(), expectation)

    def test_extra_fields(self):
        expectation1 = {
            "name": "Name",
            "id": 1
        }
        self.assertEquals(create_mock_object()._to_json(extra_fields=['^id', '^name']), expectation1)

        expectation2 = {
            "datetime": "2010-09-10T08:51:25Z",
            "canceled": True,
            "date": "2010-09-10",
            "child": None
        }
        self.assertEquals(create_mock_object()._to_json(extra_fields=['!id', '!name']), expectation2)

    def test_extra_fields_relationships(self):
        expectation = {
            "name": "Name",
            "child": {
                "datetime": "2010-09-10T08:51:25Z",
                "canceled": True,
                "date": "2010-09-10",
                "id": 1,
                "child": None
            }
        }

        obj = create_mock_object()
        obj.child = create_mock_object()

        self.assertEquals(obj._to_json(extra_fields=['^name', '^child', 'child.!name']), expectation)
