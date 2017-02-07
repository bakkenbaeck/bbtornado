import logging
import json
import urllib

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

ENDPOINT = 'https://hooks.slack.com/services/xxx'
CHANNEL = '#notifications'

def post_message(msg, username='BBTornado', channel=CHANNEL, unfurl_links=False, icon=":robot_face:"):

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

    req = HTTPRequest(ENDPOINT, method='POST', headers={ 'Content-Type': 'application/json' }, body=json.dumps(body))

    IOLoop.current().spawn_callback(client.fetch, req)

class SlackFilter(object):

    def __init__(self, level):
        self.level = level

    def filter(self, record):
        if hasattr(record, 'slack'): return record.slack

        return record.levelno>=self.level


class SlackHandler(logging.Handler):
    """A logging handler that sends error messages to slack"""
    def __init__(self, slack_endpoint_url, channel, level=logging.ERROR):
        logging.Handler.__init__(self)
        self.slack_endpoint = slack_endpoint_url
        self.channel = channel
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
            unfurl_links=False,
            username="Robot",
            channel=self.channel,
            icon_emoji=icon
        )


if __name__ == '__main__':

    import sys
    from tornado.ioloop import IOLoop

    ioloop = IOLoop.instance()
    ioloop.add_callback(lambda : post_message(sys.argv[1], channel='#test2'))
    ioloop.call_later(3, lambda : sys.exit())
    ioloop.start()
