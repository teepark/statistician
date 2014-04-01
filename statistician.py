# vim: fileencoding=utf8:et:sw=4:ts=8:sts=4

import contextlib
import functools
import random
import socket
import time


_sock = None

def _get_sock():
    global _sock
    if _sock is None:
        _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return _sock


class Client(object):
    "Client interface for StatsD"

    def __init__(self, host='localhost', port=8125, prefix=None):
        self._hostport = (socket.gethostbyname(host), port)
        self._prefix = (prefix.encode('utf8') + '.') if prefix else ''

    def incr(self, stat, by=1, sample=1):
        "manipulate a counter"
        if sample < 1:
            if random.random() > sample:
                return
            self._send(stat, str(by), 'c', sample)
        else:
            self._send(stat, str(by), 'c')

    def time(self, stat, value):
        "record a timer value"
        self._send(stat, str(int(value + 0.5)), 'ms')

    def timer(self, stat):
        "return a Timer object for use as a context manager or decorator"
        return Timer(self, stat)

    def gauge(self, stat, value):
        "set a gauge value"
        if value < 0:
            raise ValueError("gauges can only be set to non-negative numbers")
        self._send(stat, str(value), 'g')

    def incr_gauge(self, stat, by=1):
        "modify a gauge value"
        by = str(by)
        if not by.startswith("-"):
            by = '+' + by
        self._send(stat, by, 'g')

    def set(self, stat, value):
        "send a 'set' value (statsd counts unique values)"
        value = str(value)
        self._send(stat, str(value), 's')

    @contextlib.contextmanager
    def pipeline(self):
        """
        return a context manager that groups statsd messages together

        in the below example, 'gorets', 'glork', and 'gaugor' will all be
        modified in a single packet sent to statsd:

        >>> with client.pipeline() as pipeline:
        ...     pipeline.incr('gorets')
        ...     with pipeline.timer('glork'):
        ...         # ...
        ...     pipeline.gauge('gaugor', 16)
        """
        sc = StatCollector(self._prefix)
        yield sc
        _get_sock().sendto('\n'.join(sc._msgs), self._hostport)

    def _format(self, stat, value, code, sample=None):
        msg = "%s%s:%s|%s" % (self._prefix, stat.encode('utf8'), value, code)
        if sample is not None:
            msg += ('@%f' % sample).rstrip('0')
        return msg

    def _send(self, stat, value, code, sample=None):
        msg = self._format(stat, value, code, sample)
        _get_sock().sendto(msg, self._hostport)


class Timer(object):
    def __init__(self, client, stat):
        self.client = client
        self.stat = stat

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, klass, exc, tb):
        self.end = time.time()
        self.client.time(self.stat, (self.end - self.start) * 1000000)
        
    def __call__(self, func):
        @functools.wraps(func)
        def decorator(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                self.client.time(self.stat, (time.time() - start) * 1000000)
        return decorator


class StatCollector(Client):
    def __init__(self, prefix):
        self._prefix = prefix
        self._msgs = []

    def _send(self, stat, value, code, sample=None):
        self._msgs.append(self._format(stat, value, code, sample))
