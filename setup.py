#!/usr/bin/env python
# vim: fileencoding=utf8:et:sw=4:ts=8:sts=4

from setuptools import setup


VERSION = (0, 0, 1, "")


setup(
    name="statistician",
    description="simple statsd client",
    py_modules=["statistician"],
    version='.'.join(filter(None, map(str, VERSION))),
)
