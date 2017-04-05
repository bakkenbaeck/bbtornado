import logging
import time
import signal

import tornado.ioloop
import tornado.httpserver
import tornado.options
import tornado.log

log = logging.getLogger(__name__)

http_server = None

try:
    import settings
    if hasattr(settings, 'settings'): settings = settings.settings

except:
    log.warning("Using bbtornado default settings!")
    import bbtornado.default_settings as settings

def setup():
    tornado.options.define("host", default="0.0.0.0", help="run on the given address", type=str)
    tornado.options.define("port", default=5000, help="run on the given port", type=int)
    tornado.options.define("base", default=settings.BASE_URL, type=str)
    tornado.options.define("debug", default=settings.DEBUG, type=int)
    tornado.options.define("fcgi", default=None, type=str)
    tornado.options.define("db_path", default=None, type=str)
    return tornado.options.parse_command_line()

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
        http_server.listen(tornado.options.options.port, address=tornado.options.options.host)
        tornado.log.gen_log.info('HTTP Server started on http://%s:%s/%s',
                                 tornado.options.options.host, tornado.options.options.port,
                                 tornado.options.options.base)

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
            # set the script name to "" so it does not appear in the tonado path match pattern
            env['SCRIPT_NAME'] = ''
            return wsgi_app(env, start)

        from flup.server.fcgi import WSGIServer
        WSGIServer(fcgiapp, bindAddress=tornado.options.options.fcgi).run()
