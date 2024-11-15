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
Basic utilities for use with the other modules.
"""

# Other modules in this package may require core.
# To avoid circular dependencies, core.py shall not depend on any other modules in this package.


from __future__ import absolute_import, division, print_function
from abc import ABCMeta, abstractmethod

from collections import Mapping
import sys
from itertools import islice, chain
from functools import wraps

if sys.version_info[0] == 2:
    # noinspection PyUnresolvedReferences
    from itertools import izip_longest as zip_longest
else:
    from itertools import zip_longest

# This is to avoid depending on statement.Print
# a bug in Jython prevents from __future__ import print_statement from working in doctests.
Print = print

_exclude_from__all__ = set(globals().keys())
__test__ = {}


def _private():
    class EmptyType(Mapping, tuple):
        """
        Represents an immutable empty Mapping/tuple
        It's similar to None, but supports * and **
        >>> (lambda *args: tuple(args))(*Empty)
        ()
        >>> (lambda **kwargs: kwargs)(**Empty)
        {}
        >>> list(Empty)
        []
        >>> bool(Empty)
        False
        >>> (1,) + Empty + (2,)
        (1, 2)
        >>> () == Empty
        True
        >>> {} == Empty
        True

        A common mistake in Python is to use a mutable default:
        >>> foo = lambda x={}: x
        >>> foo()
        {}
        >>> foo()['spam'] = 'spam'
        >>> foo()  # surprise!
        {'spam': 'spam'}

        Empty doesn't have this problem, but is still a readonly Mapping
        >>> foo = lambda x=Empty: x
        >>> foo()['spam'] = 'spam'  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        TypeError: ...
        >>> foo()
        Empty
        """
        __slots__ = ()

        __len__ = tuple.__len__
        __iter__ = tuple.__iter__

        def __new__(cls, *args, **kwargs):
            return tuple.__new__(cls)

        def __init__(self):
            tuple.__init__(self)

        def __getitem__(self, key):
            raise KeyError(key)

        def __repr__(self):
            return 'Empty'

        def __eq__(self, other):
            if other == set() or other == {}:
                return True
            else:
                return tuple.__eq__(self, other)

        def __ne__(self, other):
            return not self == other

        def __hash__(self):
            return 0

    __test__[EmptyType.__name__] = EmptyType.__doc__

    res = EmptyType()

    def __init__(self):
        raise TypeError("cannot create 'EmptyType' instances")

    EmptyType.__init__ = __init__
    return res


Empty = _private()
del _private


# class Arguments(Mapping):
#     def __getitem__(self, key):
#         return self.kwargs.get(key, self.args[key])
#
#     def __iter__(self):
#         def it():
#             for i in range(len(self.args)):
#                 yield i
#             for k in self.kwargs:
#                 yield k
#         return it
#
#     def __len__(self):
#         return len(self.args) + len(self.kwargs)
#
#     def __init__(self, *args, **kwargs):
#         self.args = tuple(args)
#         self.kwargs = MappingProxyType(kwargs)
#
#     def apply(self, func):
#         return func(*self.args, **self.kwargs)

def star(func):
    """
    Converts a multiple-argument function to a function of one iterable.
    >>> nums = [1, 2, 3]
    >>> Print(*nums)
    1 2 3
    >>> star(Print)(nums)
    1 2 3
    """
    return lambda arg: func(*arg)


def unstar(func):
    """
    Converts a function of one iterable to a function of its elements.
    >>> list((1, 2, 3))
    [1, 2, 3]
    >>> unstar(list)(1, 2, 3)
    [1, 2, 3]
    """
    return lambda *args: func(args)


def stars(func):
    """
    Converts a multiple-argument function to a function of one mapping.
    >>> cba = dict(c='C', b='B', a='A')
    >>> test = (lambda a, b, c: Print(a, b, c))
    >>> test(**cba)
    A B C
    >>> stars(test)(cba)
    A B C
    """
    return lambda kwargs: func(**kwargs)


def unstars(func):
    """
    Converts a function of one mapping to a function of keyword arguments
    >>> test = lambda mapping: Print(mapping)
    >>> test(dict(a='A'))
    {'a': 'A'}
    >>> unstars(test)(a='A')
    {'a': 'A'}
    """
    return lambda **kwargs: func(kwargs)


# entuple = unstar(tuple)
def entuple(*args):
    """
    returns args as a tuple
    >>> entuple(1, 2, 3)
    (1, 2, 3)
    """
    return tuple(args)


# enlist = unstar(list)
def enlist(*args):
    """
    returns args as a list
    >>> enlist(1, 2, 3)
    [1, 2, 3]
    """
    return list(args)


# enset = unstar(set)
def enset(*args):
    """
    returns args as a set
    >>> enset(1, 2, 3) == {1, 2, 3}
    True
    """
    return set(args)


# efset = unstar(frozenset)
def efset(*args):
    """
    return args as a frozenset
    >>> efset(1, 2, 3) == frozenset([1, 2, 3])
    True
    """
    return frozenset(args)


def edict(*args):
    """
    pairs args and makes a dictionary with them
    >>> edict(1, 2)
    {1: 2}
    >>> edict(1, 2,  3, 4,  5, 6)[3]
    4
    >>> edict(1, 2,
    ...       3, 4) == {1: 2, 3: 4}
    True
    """
    return dict(partition(args))


class Namespace(object):
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


_sentinel = object()


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


def interleave(*iterables):
    """
    >>> ''.join(interleave('ABC','xyz'))
    'AxByCz'
    >>> ' '.join(interleave('ABC','xyz','123'))
    'A x 1 B y 2 C z 3'
    """
    return chain.from_iterable(zip(*iterables))


def identity(x):
    """
    The identity function. Returns its argument.
    not to be confused with the id() builtin
    >>> identity('foo')
    'foo'
    """
    return x


def apply(func, *args, **stargs):
    """
    applies a function to arguments.
    >>> apply(Print, 1, 2, 3)
    1 2 3

    also unpacks arguments with the special keywords star and stars

    # like Print(1, 2, *(3, 4), **dict(sep='::'))
    >>> apply(Print, 1, 2, star=(3, 4), stars=dict(sep='::'))
    1::2::3::4
    """
    return func(*args + tuple(stargs.get('star', ())), **stargs.get('stars', Empty))


def assign_attr(obj, name, val, oper=None):
    """
    does an augmented assignment to the named attr of obj
    returns obj.

    does a simple replacement if no operator is specified

    usually used in combination with the operator module,
    though any appropriate binary function may be used.
    >>> from operator import add, iadd
    >>> spam = lambda:None
    >>> assign_attr(assign_attr(spam,'eggs',40),'eggs',1,add).eggs
    41
    >>> assign_attr(spam,'eggs',1,iadd).eggs
    42
    """
    if oper:
        setattr(obj, name, oper(getattr(obj, name), val))
    else:
        setattr(obj, name, val)
    return obj


def assign_item(obj, index, val, oper=None):
    """
    does an augmented assignment to the indexed (keyed)
    item of obj. returns obj for chaining.

    does a simple replacement if no operator is specified

    usually used in combination with the operator module,
    though any appropriate binary function may be used.
    >>> from operator import add
    >>> spam = [40]
    >>> assign_item(spam,0, 2,add)
    [42]
    >>> assign_item(globals(),'eggs',  12)['eggs']
    12
    >>> eggs
    12
    """
    if oper:
        obj[index] = oper(obj[index], val)
    else:
        obj[index] = val
    return obj


def delitem(obj, index):
    """
    Deletes the element in obj at index, and returns obj for chaining
    >>> spam = [1, 2, 3]
    >>> delitem(spam, 1)
    [1, 3]
    >>> spam = {'one': 1, 'two': 2}
    >>> delitem(spam, 'one')
    {'two': 2}
    >>> (delitem(globals(), 'spam'), None)[-1]
    >>> try:
    ...    spam
    ...    assert False
    ... except NameError as ne:
    ...    Print(repr(ne))
    NameError("name 'spam' is not defined",)
    """
    del obj[index]
    return obj


# def funcall(func, *args, **kwargs):
#     """
#     Immediately calls the function with the given arguments.
#     """
#     return func(*args, **kwargs)
#
#
# def apply(func, *args, **kwargs):
#     """
#     Partially applies any given arguments to func and returns a function of args and kwargs
#     for the remainder.
#     """
#     # TODO: doctest apply
#     return (lambda a=(), kw=Empty:
#             functools.partial(func, *args, **kwargs)(*a, **kw))

# decorator = (lambda d: lambda *args,**kwargs: lambda f:  d(f,*args,**kwargs))
def decorator(arged_decorator):
    """Decorator-with-arguments decorator.

    Decorators can't take arguments, but you can work around this via currying, that is, call a decorator factory
    function with arguments that generates a new decorator function on the fly. The @ syntax works with these function
    calls, but it makes defining decorators with arguments difficult, especially when using callable classes.
    This decorator decorator abstracts and simplifies the process by turning a function of multiple arguments
    (the wrapper) into a decorator factory.

    The wrapper this decorates must take a function as its first argument. The remaining arguments will come from
    the factory call.
    @decorator
    >>> @decorator
    ... def before_after(f,before,after):
    ...     def wrapped(name):
    ...         Print(before)
    ...         f(name)
    ...         Print(after)
    ...     return wrapped

    <meet> becomes the first argument to the original before_after
    >>> @before_after("Hello","Goodbye")
    ... def meet(name):
    ...     Print(name)

    >>> meet("World")
    Hello
    World
    Goodbye
    """

    @wraps(arged_decorator)
    def args_taker(*args, **kwargs):
        def func_taker(f):
            return arged_decorator(f, *args, **kwargs)

        return func_taker

    return args_taker


if sys.version_info[0] >= 3:
    exec("class Abstract(metaclass=ABCMeta):pass")
else:
    class Abstract(object):
        __metaclass__ = ABCMeta


class SEvaluable(Abstract):
    _s_evaluable_ = None

    @abstractmethod
    def s_eval(self, scope):
        pass


__all__ = [e for e in globals().keys() if not e.startswith('_') if e not in _exclude_from__all__]
