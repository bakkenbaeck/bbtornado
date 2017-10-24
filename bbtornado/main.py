import logging
import time
import signal
import yaml

import tornado.ioloop
import tornado.httpserver
import tornado.options
import tornado.log
from bbtornado import config as le_config


log = logging.getLogger(__name__)

http_server = None

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_BASE = ""

DEFAULT_COOKIE_SECRET = 'Do not use in production'

def setup():
    """
    setup common commandline options and parse them all

    you must add any of your own options before this
    """
    tornado.options.define("host", default=None, help="run on the given address", type=str)
    tornado.options.define("port", default=None, help="run on the given port", type=int)
    tornado.options.define("base", default=None, type=str)
    tornado.options.define("debug", default=None, type=int)
    tornado.options.define("fcgi", default=None, type=str)
    tornado.options.define("db_path", default=None, type=str)

    tornado.options.define("config", default=None, help='Config file', type=str)
    not_parsed = tornado.options.parse_command_line()


    setup_global_config()

    return not_parsed


def find_first(array):
    return next(item for item in array if item is not None)


def override_config(config):
    '''Overrides the given config by tornado.options'''
    override = tornado.options.options

    # Init config object
    if 'tornado' not in config:
        config['tornado'] = {}
    if config['tornado'].get('server') is None:
        config['tornado']['server'] = {}
    if config['tornado'].get('app_settings') is None:
        config['tornado']['app_settings'] = {}
    if 'db' not in config:
        config['db'] = {}


    # Handle host, port, base, with the following priorities
    # 1. command line arg (by tornado.options)
    # 2. config file
    # 3. hardcoded default
    server_cfg = config['tornado']['server']
    host = find_first([override.host, server_cfg.get('host'), DEFAULT_HOST])
    port = find_first([override.port, server_cfg.get('port'), DEFAULT_PORT])
    base = find_first([override.base, server_cfg.get('base'), DEFAULT_BASE])
    config['tornado']['server'].update(dict(host=host, port=port, base=base))

    # If the debug flag is set, save it in app_settings and activate db echo
    if override.debug is not None:
        config['tornado']['app_settings']['debug'] = override.debug
        config['db']['echo'] = override.debug == 2

    if override.db_path is not None:
        config['db']['uri'] = override.db_path


    # Set up default cookie secret if it is not given
    cookie_secret = config['tornado']['app_settings'].get('cookie_secret')
    cookie_secret = find_first([cookie_secret, DEFAULT_COOKIE_SECRET])
    config['tornado']['app_settings']['cookie_secret'] = cookie_secret


def setup_global_config():
    '''Reads the config file from the command line arguemnt --config and installs
    it globally as `bbtornado.config`.'''
    config_path = tornado.options.options.config
    if config_path is not None:
        config = read_config(config_path)
    else:
        config = {}
    override_config(config)

    validate_config(config)

    # Update global config object
    le_config.update(config)


def read_config(config_path):
    '''Reads the config yaml.'''
    try:
        config = parse_config(config_path)
    except Exception as e:
        raise Exception('Failed loading config %s' % config_path, e)
    return config


def parse_config(config_yaml_path):
    '''Parses the config yaml file'''
    with open(config_yaml_path, 'r') as fd:
        config = yaml.load(fd)
    return config


def validate_config(config):
    if config is None:
        raise Exception('Config is empty')

    # Validate tornado settings
    if not config.get('tornado'):
        raise Exception('Missing object tornado')
    if not config['tornado'].get('server'):
        raise Exception('Missing object tornado.server')
    if not config['tornado']['server'].get('host'):
        raise Exception('Missing object tornado.server.host')
    if config['tornado']['server'].get('port') is None:
        raise Exception('Missing object tornado.server.port')
    if config['tornado']['server'].get('base') is None:
        raise Exception('Missing object tornado.server.base')
    if config['tornado'].get('app_settings') is None:
        raise Exception('Missing object tornado.app_settings')
    if config['tornado']['app_settings'].get('debug'):
        tornado.log.gen_log.warning('HTTP Server in debug mode, do not use in production.')
    cookie_secret = config['tornado']['app_settings'].get('cookie_secret')
    if not cookie_secret or cookie_secret == DEFAULT_COOKIE_SECRET:
        tornado.log.gen_log.warning('Insecure default cookie secret, do not use in production.')

    # Validate database settings
    if not config.get('db'):
        raise Exception('Missing object db')
    if not config['db'].get('uri'):
        raise Exception('Missing object db.uri')
    if config['db'].get('echo'):
        tornado.log.gen_log.warning('DB in echo mode, do not use in production.')
    return True


MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 0

def sig_handler(sig, frame):
    log.warning('Caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback_from_signal(shutdown)

def shutdown():
    log.info('Stopping http server')
    http_server.stop()

    if hasattr(http_server.request_callback, 'shutdown_hook'):
        http_server.request_callback.shutdown_hook()

    log.info('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
    io_loop = tornado.ioloop.IOLoop.instance()

    deadline = time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN

    def stop_loop():
        now = time.time()
        if now < deadline and (io_loop._callbacks or io_loop._timeouts):
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            log.info('Shutdown')
    stop_loop()


def get_http_server():
    return http_server


def main(app):

    global http_server

    if not tornado.options.options.fcgi:

        http_server = tornado.httpserver.HTTPServer(app)

        server_opts = le_config['tornado']['server']
        host = server_opts['host']
        port = server_opts['port']
        base = server_opts['base']
        http_server.listen(port, address=host)
        tornado.log.gen_log.info('HTTP Server started on http://%s:%s/%s',
                                 host, port, base)

        signal.signal(signal.SIGTERM, sig_handler)
        signal.signal(signal.SIGINT, sig_handler)

        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            if hasattr(app, 'shutdown_hook'):
                app.shutdown_hook()
            raise


    else:

        from tornado.wsgi import WSGIAdapter

        wsgi_app = WSGIAdapter(app)

        def fcgiapp(env, start):
            # set the script name to "" so it does not appear in the tornado path match pattern
            env['SCRIPT_NAME'] = ''
            return wsgi_app(env, start)

        from flup.server.fcgi import WSGIServer
        WSGIServer(fcgiapp, bindAddress=tornado.options.options.fcgi).run()
