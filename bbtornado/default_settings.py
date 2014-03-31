from os.path import join, dirname, abspath, pardir, expanduser, exists
import json

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s'%join(dirname(abspath(__file__)), pardir, 'database.db')
SECRET_KEY = 'something not very random'
DEBUG = True
if exists('../config.json'):
    _config = json.load(open('../config.json', 'r'))
    BASE_URL = _config['baseUrl'] if _config.has_key('baseUrl') else ""
    DEBUG = _config['debug'] if _config.has_key('baseUrl') else True
elif exists('../baseURL.json'): # depreciated!
    BASE_URL = json.load(open('../baseURL.json', 'r'))
else:
    BASE_URL = ""
