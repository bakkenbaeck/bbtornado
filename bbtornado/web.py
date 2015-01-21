import tornado.options
import tornado.web

import bbtornado.models

try:
    import settings as app_settings
    if hasattr(app_settings, 'settings'): app_settings = app_settings.settings
except:
    import default_settings as app_settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Application(tornado.web.Application):
    def __init__(self, handlers=None, default_host='', transforms=None, wsgi=False, user_model=None,
                 autocommit=False, autoflush=True, **settings):
        if handlers: # append base url to handlers
            handlers = [(tornado.options.options.base + x[0],) + x[1:] for x in handlers]
        if not settings.has_key('debug'):
            settings['debug'] = tornado.options.options.debug
        if not settings.has_key('cookie_secret'):
            settings['cookie_secret'] = app_settings.SECRET_KEY
        super(Application, self).__init__(handlers=handlers, default_host=default_host,
                                          transforms=transforms, wsgi=wsgi, **settings)
        # setup database
        self.engine = create_engine(tornado.options.options.db_path,
                                    convert_unicode=True,
                                    # set echo to true if debug option is set to 2
                                    echo=tornado.options.options.debug == 2)
        bbtornado.models.init_db(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=autocommit, autoflush=autoflush)
        # this allows the BaseHandler to get and set a model for self.current_user
        self.user_model = user_model
