import logging
import json
import urllib


from tornado.ioloop import IOLoop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

def post_message(msg, endpoint, channel, username='BBTornado', unfurl_links=False, icon=":robot_face:"):

    """
    Post a message on slack.
    This will "fire-and-forget", so returns nothing.
    """

    client = AsyncHTTPClient()

    body = dict(icon_emoji=icon,
                text=msg,
                username=username,
                unfurl_links=unfurl_links,
                channel=channel)

    req = HTTPRequest(endpoint, method='POST', headers={ 'Content-Type': 'application/json' }, body=json.dumps(body))

    IOLoop.current().spawn_callback(client.fetch, req)

class SlackFilter(object):

    def __init__(self, level):
        self.level = level

    def filter(self, record):
        if hasattr(record, 'slack'): return record.slack

        return record.levelno>=self.level


class SlackHandler(logging.Handler):
    """A logging handler that sends error messages to slack"""
    def __init__(self, slack_endpoint_url, channel, username="BBTornado", level=logging.ERROR):
        logging.Handler.__init__(self)
        self.slack_endpoint = slack_endpoint_url
        self.channel = channel
        self.username = username
        self.addFilter(SlackFilter(level))

    def emit(self, record):
        text = self.format(record)

        if len(text)>300: text=text[:300]+'(...)'

        if record.levelno >= logging.ERROR: # error or critical
            icon = ":heavy_exclamation_mark:"
        elif record.levelno >= logging.WARNING: # warning
            icon = ":bangbang:"
        elif record.levelno >= logging.INFO:
            icon = ":sunny:"
        else: # debug
            icon = ":sparkles:"


        post_message(msg=text,
            endpoint=self.slack_endpoint,
            unfurl_links=False,
            username=self.username,
            channel=self.channel,
            icon=icon
        )


if __name__ == '__main__':

    import sys
    from optparse import OptionParser

    parser = OptionParser()

    parser.add_option("-c", "--channel", dest="channel", help="channel", default='#test2')
    parser.add_option("-u", "--username", dest="username", help="username", default='BBTornado')
    parser.add_option("-i", "--icon", dest="icon", help="icon", default=':robot_face:')

    (options, args) = parser.parse_args()


    ioloop = IOLoop.instance()
    ioloop.add_callback(lambda : post_message(sys.argv[1], sys.argv[2], channel='#test2'))
    ioloop.call_later(3, lambda : sys.exit())
    ioloop.start()
