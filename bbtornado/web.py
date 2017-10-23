import logging

import tornado.web

from sqlalchemy.orm import scoped_session

import bbtornado.models
from bbtornado.handlers import ThreadRequestContext

log = logging.getLogger('bbtornado.web')


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Application(tornado.web.Application):

    """
    The main Application, your application object is an instance of this class
    """

    def __init__(self, handlers=None, default_host='', transforms=None, wsgi=False, user_model=None, domain=None, init_db=True,
                 sessionmaker_settings={},
                 create_engine_settings={},
                 **settings):
        if handlers: # append base url to handlers
            base = bbtornado.config['tornado']['server']['base']
            handlers = [(base + x[0],) + x[1:] for x in handlers]

        # Init app settings with config.tornado and add override by passed args.
        app_settings = {}
        app_settings.update(bbtornado.config['tornado']['app_settings'])
        app_settings.update(settings)
        super(Application, self).__init__(handlers=handlers, default_host=default_host,
                                          transforms=transforms, wsgi=wsgi, **app_settings)

        # Init engine settings with config.db and add overrider by passed args.
        _create_engine_settings = {}
        _create_engine_settings.update(bbtornado.config['db'])
        _create_engine_settings.update(create_engine_settings)
        # Handle db_uri explicitely
        db_uri = bbtornado.config['db']['uri']
        _create_engine_settings.pop('uri', None)
        # setup database engine
        log.info('Using database from %s'%db_uri)
        self.engine = create_engine(db_uri,
                                    convert_unicode=True,
                                    **_create_engine_settings)

        if init_db:
            bbtornado.models.init_db(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine, **sessionmaker_settings), scopefunc=lambda: ThreadRequestContext.data.get('request', None))
        # this allows the BaseHandler to get and set a model for self.current_user
        self.user_model = user_model

        # you can set this to override the domain for secure cookies
        self.domain = domain
