# Copyright 2015 Matthew Egan Odendahl
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO: docstring core.py module

# Other modules in this package may require core.
# To avoid circular dependencies, core.py shall not depend on any other modules in this package.


from __future__ import absolute_import, division, print_function

# noinspection PyPep8Naming
import functools
from collections import Mapping, Set
import sys


class Empty(tuple, Mapping, Set):
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        return tuple.__new__(cls)

    def __init__(self):
        tuple.__init__(self)

    def __getitem__(self, key):
        raise KeyError(key)

    def __repr__(self):
        return self.__class__.__name__ + '()'


def star(func):
    """
    Converts a multiple-argument function to a function of one iterable.
    >>> nums = [1, 2, 3]
    >>> print(*nums)
    1 2 3
    >>> star(print)(nums)
    1 2 3
    """
    return lambda arg: func(*arg)


def unstar(func):
    """
    Converts a fuction of one iterable to a function of its elements.
    >>> list((1, 2, 3))
    [1, 2, 3]
    >>> unstar(list)(1, 2, 3)
    [1, 2, 3]
    """
    return lambda *args: func(args)


def stars(func):
    """
    Converts a multiple-argument function to a function of one mapping
    """
    return lambda kwargs: func(**kwargs)


def unstars(func):
    return lambda **kwargs: func(kwargs)


entuple = unstar(tuple)
entuple.__doc__ = """\
returns args as a tuple
>>> entuple(1, 2, 3)
(1, 2, 3)
"""

enlist = unstar(list)
enlist.__doc__ = """\
returns args as a list
>>> enlist(1, 2, 3)
[1, 2, 3]
"""


enset = unstar(set)
enset.__doc__ = """\
returns args as a set
>>> enset(1, 2, 3) == {1, 2, 3}
True
"""

efset = unstar(frozenset)
efset.__doc__ = """\
return args as a frozenset
>>> efset(1, 2, 3) == frozenset([1, 2, 3])
True
"""


def edict(*args):
    """
    pairs args and makes a dictionary with them
    >>> edict(1, 2)
    {1: 2}
    >>> edict(1, 2,  3, 4,  5, 6)[3]
    4
    >>> edict(1, 2,
    ...      3, 4) == {1: 2, 3: 4}
    True
    """
    return dict(partition(args))


class Namespace:
    """
    An "empty" object for containing attrs.
    Not completely empty since it inherits from object
    >>> spam = Namespace(foo=1)
    >>> spam
    Namespace(foo=1)
    >>> spam.foo
    1
    >>> spam.bar = 2
    >>> spam.bar
    2
    """

    def __init__(self, **kwargs):
        self.__dict__ = kwargs

    def __repr__(self):
        return 'Namespace({0})'.format(
            ', '.join('{0}={1}'.format(k, repr(v))
                      for k, v in self.__dict__.items()))


# prog1 = lambda *body: body[0]
# prog1.__doc__ = '''\
# returns the first argument.
# >>> prog1(1, 1+1, 1+1+1)
# 1
# '''


def _private():
    from itertools import islice
    if sys.version_info[0] == 2:
        from itertools import izip_longest as zip_longest
    else:
        from itertools import zip_longest

    _sentinel = object()

    global partition

    def partition(iterable, n=2, step=None, fillvalue=_sentinel):
        """
        Chunks iterable into tuples of length n. (default pairs)
        >>> list(partition(range(10)))
        [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]

        The remainder, if any, is not included.
        >>> list(partition(range(10), 3))
        [(0, 1, 2), (3, 4, 5), (6, 7, 8)]

        Keep the remainder by using a fillvalue.
        >>> list(partition(range(10), 3, fillvalue=None))
        [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, None, None)]
        >>> list(partition(range(10), 3, fillvalue='x'))
        [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 'x', 'x')]

        The step defaults to n, but can be more to skip elements.
        >>> list(partition(range(10), 2, 3))
        [(0, 1), (3, 4), (6, 7)]

        Or less for a sliding window with overlap.
        >>> list(partition(range(5), 2, 1))
        [(0, 1), (1, 2), (2, 3), (3, 4)]
        """
        step = step or n
        slices = (islice(iterable, start, None, step) for start in range(n))
        if fillvalue is _sentinel:
            return zip(*slices)
        else:
            return zip_longest(*slices, fillvalue=fillvalue)


partition = None
_private()
del _private


def identity(x):
    """
    The identity function. Returns is argument.
    not to be confused with the id() builtin
    >>> identity('foo')
    'foo'
    """
    return x


def funcall(func, *args, **kwargs):
    return func(*args, **kwargs)


def apply(func, *args, **kwargs):
    # TODO: doctest apply
    return (lambda a=(), kw=Empty():
            functools.partial(func, *args, **kwargs)(*a, **kw))

