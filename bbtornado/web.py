import logging

import tornado.options
import tornado.web

from sqlalchemy.orm import scoped_session

import bbtornado.models

log = logging.getLogger('bbtornado.web')

try:
    import settings as app_settings
    if hasattr(app_settings, 'settings'): app_settings = app_settings.settings
except:
    log.warn('No app settings founds, falling back on default settings')
    import default_settings as app_settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Application(tornado.web.Application):
    def __init__(self, handlers=None, default_host='', transforms=None, wsgi=False, user_model=None, domain=None,
                 sessionmaker_settings={}, **settings):
        if handlers: # append base url to handlers
            handlers = [(tornado.options.options.base + x[0],) + x[1:] for x in handlers]
        if 'debug' not in settings:
            settings['debug'] = tornado.options.options.debug
        if 'cookie_secret' not in settings:
            settings['cookie_secret'] = app_settings.SECRET_KEY
        super(Application, self).__init__(handlers=handlers, default_host=default_host,
                                          transforms=transforms, wsgi=wsgi, **settings)

        log.info('Using database from %s'%tornado.options.options.db_path)
        # setup database
        self.engine = create_engine(tornado.options.options.db_path,
                                    convert_unicode=True,
                                    # set echo to true if debug option is set to 2
                                    echo=tornado.options.options.debug == 2)
        bbtornado.models.init_db(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine, **sessionmaker_settings))
        # this allows the BaseHandler to get and set a model for self.current_user
        self.user_model = user_model

        # you can set this to override the domain for secure cookies
        self.domain = domain
