"""
>>> False
from drython.expression import *
from threading import enumerate
import gc
@generator
def foo(Yield):
    Yield(1)
    Yield(2)
def echo():
    reply = yield
    while True:
        reply = yield reply
e1 = echo()
@generator
def echo2(Yield):
    reply = Yield()
    while True:
        reply = Yield(reply)
e2 = echo2()
e2.send(None)
del e2
gc.collect()
print(enumerate())
"""
from __future__ import print_function
import doctest
import unittest

import drython as dry
import drython.core
import drython.statement
import drython.expression


if __name__ == '__main__':
    print('in test main')
    unittest.main()
    doctest.testfile('../README.md')
    doctest.testmod()