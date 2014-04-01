#!/usr/bin/env python
# vim: fileencoding=utf8:et:sw=4:ts=8:sts=4


import errno
import random
import socket
import time
import unittest

import statistician


TIMEOUT = 0.01


class StatsTests(unittest.TestCase):
    def setUp(self):
        # create a listening socket for a phony statsd server
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listener.settimeout(TIMEOUT)

        # find an available UDP port for it
        port = 9000
        while 1:
            try:
                self.listener.bind(("127.0.0.1", port))
            except EnvironmentError, exc:
                if exc.args[0] != errno.EADDRINUSE:
                    raise
                port += 1
            else:
                break

        # create a client that connects to it
        self.client = statistician.Client(port=port)

        # mock random.random
        self._realrand = random.random
        random.random = lambda: 0.0

    def tearDown(self):
        self.listener.close()
        self.listener = None
        random.random = self._realrand

    def get_msg(self):
        return self.listener.recvfrom(8192)[0]

    def assertMsgRecvd(self, msg):
        self.assertEqual(self.get_msg(), msg)

    def test_incr(self):
        self.client.incr('a.b')
        self.assertMsgRecvd('a.b:1|c')

        self.client.incr('c.d', 3)
        self.assertMsgRecvd('c.d:3|c')

        self.client.incr('e', -10)
        self.assertMsgRecvd('e:-10|c')

        self.client.incr('f.g', sample=0.2)
        self.assertMsgRecvd('f.g:1|c@0.2')

        self.client.incr('h', -4, sample=0.7)
        self.assertMsgRecvd('h:-4|c@0.7')

    def test_time(self):
        self.client.time('a.b.c', 100)
        self.assertMsgRecvd('a.b.c:100|ms')

    def test_timer(self):
        with self.client.timer('asdf'):
            self.client.time('qwerty', 30)
        self.assertMsgRecvd('qwerty:30|ms')
        self.assertRegexpMatches(self.get_msg(), r'^asdf:\d+\|ms$')

        @self.client.timer('x.y')
        def thing():
            pass

        # not yet
        self.assertRaises(socket.timeout, self.listener.recvfrom, 8192)

        thing()

        # now
        self.assertRegexpMatches(self.get_msg(), r'^x\.y:\d+\|ms$')

    def test_gauge(self):
        self.client.gauge('foo', 11)
        self.assertMsgRecvd('foo:11|g')

    def test_incr_gauge(self):
        self.client.incr_gauge('a.b', 3)
        self.assertMsgRecvd('a.b:+3|g')

        self.client.incr_gauge('c.d', -4)
        self.assertMsgRecvd('c.d:-4|g')

    def test_set(self):
        self.client.set('a.b.c', 2)
        self.assertMsgRecvd('a.b.c:2|s')

        self.client.set('d.e', -4)
        self.assertMsgRecvd('d.e:-4|s')

    def test_pipeline(self):
        # heck, let's use the example from the docstring
        with self.client.pipeline() as pipeline:
            pipeline.incr('gorets')
            self.assertRaises(socket.timeout, self.listener.recvfrom, 8192)

            with pipeline.timer('glork'):
                time.sleep(TIMEOUT)
            self.assertRaises(socket.timeout, self.listener.recvfrom, 8192)

            pipeline.gauge('gaugor', 16)
            self.assertRaises(socket.timeout, self.listener.recvfrom, 8192)

        lines = self.get_msg().splitlines()
        self.assertEqual(len(lines), 3)

        self.assertEqual(lines[0], 'gorets:1|c')
        self.assertRegexpMatches(lines[1], r'^glork:\d+|ms')
        self.assertEqual(lines[2], 'gaugor:16|g')


if __name__ == '__main__':
    unittest.main()
