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
"""

"""


__author__ = 'Matthew Egan Odendahl'


def Tuple(*args):
    """ returns args as a tuple """
    return args


def List(*args):
    """ returns args as a list """
    return list(args)


def Set(*args):
    """ returns args as a set """
    return set(args)


def Dict(*args):
    """ pairs args and makes a dictionary with them
    >>> Dict(1,2)
    {1: 2}
    >>> Dict(1,2,  3,4,  5,6)[3]
    4
    """
    return dict(partition(args))


class Namespace:
    """ An empty object for containing attrs. """
    def __init__(self,**kwargs):
        self.__dict__ = kwargs


prog1 = lambda *body: body[0]
prog1.__doc__ = '''\
returns the first argument.
>>> prog1(1,1+1,1+1+1)
1
'''


def _private():
    from itertools import islice, zip_longest

    sentinel = object()

    # noinspection PyShadowingNames
    def partition(iterable, n=2, step=None, fillvalue=sentinel):
        """
        Chunks iterable into tuples of length n. (default pairs)
        >>> list(partition(range(10)))
        [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]

        The remainder, if any, is not included.
        >>> list(partition(range(10), 3))
        [(0, 1, 2), (3, 4, 5), (6, 7, 8)]

        Keep the remainder by using a fillvalue.
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
        if fillvalue is sentinel:
            return zip(*slices)
        else:
            return zip_longest(*slices, fillvalue=fillvalue)

    return partition
partition = _private()
del _private


def apply(func,*params,args=(),kwargs={}):
    # TODO: doctest apply
    return func(*(params+tuple(args)),**kwargs)


if __name__ == "__main__": import doctest; doctest.testmod()
