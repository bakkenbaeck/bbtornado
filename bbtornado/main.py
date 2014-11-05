import tornado.ioloop
import tornado.httpserver
import tornado.options
import tornado.log
try:
    import settings
    if hasattr(settings, 'settings'): settings = settings.settings

except:
    import default_settings as settings

def setup():
    tornado.options.define("host", default="0.0.0.0", help="run on the given address", type=str)
    tornado.options.define("port", default=5000, help="run on the given port", type=int)
    tornado.options.define("base", default=settings.BASE_URL, type=str)
    tornado.options.define("debug", default=settings.DEBUG, type=bool)
    tornado.options.define("fcgi", default=None, type=str)
    tornado.options.define("db_path", default=settings.SQLALCHEMY_DATABASE_URI, type=str)
    tornado.options.parse_command_line()


def main(app):

    if not tornado.options.options.fcgi:

        http_server = tornado.httpserver.HTTPServer(app)
        http_server.listen(tornado.options.options.port, address=tornado.options.options.host)
        tornado.log.gen_log.info('HTTP Server started on http://%s:%s/%s',
                                 tornado.options.options.host, tornado.options.options.port,
                                 tornado.options.options.base)
        tornado.ioloop.IOLoop.instance().start()

    else:

        from tornado.wsgi import WSGIAdapter

        wsgi_app = WSGIAdapter(app)

        def fcgiapp(env, start):
            # set the script name to "" so it does not appear in the tonado path match pattern
            env['SCRIPT_NAME'] = ''
            return wsgi_app(env, start)

        from flup.server.fcgi import WSGIServer
        WSGIServer(fcgiapp, bindAddress=tornado.options.options.fcgi).run()
