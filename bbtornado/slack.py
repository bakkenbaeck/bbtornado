import logging
import json
import urllib
import six

from tornado.ioloop import IOLoop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

"""

Utilities for logging to slack.

Add a `SlackHandler` to your logger to have messages logged to slack.

>>> import logging
>>> logging.getLogger().addHandler(SlackHandler('http://my.slack.incoming.webhook', '#bbtornado'))

Messages are either filtered by level, or you can force logging to slack by passing in an extra dict when logging

>>> log.info("hello on slack!", extra=dict(slack='#general'))

"""

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

    IOLoop.current().spawn_callback(client.fetch, req, raise_error=False)

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

        # make sure to include the last (most relevant) lines in a stracktrace, too
        if len(text)>550: text=text[:250]+" (...)\n(...) "+text[-250:]

        if record.levelno >= logging.ERROR: # error or critical
            icon = ":heavy_exclamation_mark:"
        elif record.levelno >= logging.WARNING: # warning
            icon = ":bangbang:"
        elif record.levelno >= logging.INFO:
            icon = ":sunny:"
        else: # debug
            icon = ":sparkles:"

        channel = self.channel
        if hasattr(record, 'slack') and isinstance(record.slack, six.string_types) and record.slack[0] in ('#', '@'):
            channel = record.slack

        post_message(msg=text,
            endpoint=self.slack_endpoint,
            unfurl_links=False,
            username=self.username,
            channel=channel,
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

    if len(args)<2:
        raise Exception("You need to specify the endpoint and the message!")

    ioloop = IOLoop.instance()

    ioloop.add_callback(lambda : post_message(args[0], args[1], channel=options.channel, username=options.username, icon=options.icon))
    ioloop.call_later(3, lambda : sys.exit())
    ioloop.start()
