from os.path import join, dirname, abspath, pardir, expanduser, exists
import json

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s'%join(dirname(abspath(__file__)), pardir, 'database.db')
SECRET_KEY = 'something not very random'
DEBUG = True
try:
    BASE_URL = json.load(open('../baseURL.json', 'r'))
except IOError:
    BASE_URL = ""
