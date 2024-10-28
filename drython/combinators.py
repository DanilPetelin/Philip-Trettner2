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
Stack combinators.

supports import *
"""
from __future__ import absolute_import, division
from drython.statement import Print

from itertools import permutations
import collections

from drython.core import enlist
from drython.stack import Combinator, defcombinator, Stack


_exclude_from__all__ = set(globals().keys())


# ##
# Stack manipulation combinators
# ##


@Combinator
def pop(stack):
    """
    discards the top of the stack
    >>> Stack('...', 'a', pop)
    Stack('...',)
    """
    stack, a = stack.pop()
    return stack


@Combinator
def dup(stack):
    """
    duplicates the top of the stack
    >>> Stack('...', 'a', dup)
    Stack('...', 'a', 'a')
    """
    return stack.push(stack.peek())


@Combinator
def nop(stack):
    """ no-operation. Returns stack unchanged. """
    return stack


@Combinator
def swap(stack):
    """
    swaps the top two elements of the stack
    >>> Stack('...', 'a', 'b', swap)
    Stack('...', 'b', 'a')
    """
    stack, a, b = stack.pop(2)
    return stack.push(b, a)

# creates all depth-3 stack permutation functions
for _cs in permutations('abc'):
    if _cs[0] == 'a':
        # abc is nop
        # acb is swap
        continue
    exec('''
@Combinator
def {0}(stack):
    """
    permutes the top three elements of the stack,
    >>> Stack('...', 'a', 'b', 'c', {0})
    Stack('...', '{1}', '{2}', '{3}')
    """
    stack, a, b, c = stack.pop(3)
    return stack.push({1},{2},{3})

    '''.format(''.join(_cs), *_cs))
# noinspection PyUnboundLocalVariable
del _cs


# creates all depth-4 stack permutation functions
for _cs in permutations('abcd'):
    if _cs[0] == 'a':
        continue  # depth < 4; already defined above
    exec('''
@Combinator
def {0}(stack):
    """
    permutes the top four elements of the stack,
    >>> Stack('...', 'a', 'b', 'c', 'd', {0})
    Stack('...', '{1}', '{2}', '{3}', '{4}')
    """
    stack, a, b, c, d = stack.pop(4)
    return stack.push({1},{2},{3},{4})

    '''.format(''.join(_cs), *_cs))
del _cs


# popd = defcombinator((pop,), dip)
@Combinator
def popd(stack):
    """
    pops one deeper
    >>> Stack('...', 'a', 'b', popd)
    Stack('...', 'b')
    """
    stack, a, b = stack.pop(2)
    return stack.push(b)


# dupd = defcombinator((dup,), dip)
@Combinator
def dupd(stack):
    """
    duplicates one deeper
    >>> Stack('...', 'a', 'b', dupd)
    Stack('...', 'a', 'a', 'b')
    """
    stack, a, b = stack.pop(2)
    return stack.push(a, a, b)


# ##
# Operator combinators
# ##


@Combinator
def quote(stack):
    """
    wraps the top n elements in a tuple
    >>> Stack('a','b','c',2,quote)
    Stack('a', ('b', 'c'))
    """
    stack, depth = stack.pop()
    # stack, *args = stack.pop(depth)
    stack_args = stack.pop(depth)
    stack = stack_args[0]
    args = stack_args[1:]
    return stack.push(args)


@Combinator
def choice(stack):
    stack, b, t, f = stack.pop(3)
    return stack.push(t if b else f)


# ##
# Quotation Combinators
# ##

@Combinator
def call(stack):
    """
    The call combinator applies an ordinary Python function to a
    list of arguments.

    (The Print function returns None)
    >>> Stack([1,2,3],Print,call)
    1 2 3
    Stack(None,)

    Keywords are also supported with a dictionary
    >>> Stack([1,2,3],dict(sep=':'),Print,call)
    1:2:3
    Stack(None,)

    Use an empty list for no arguments
    >>> Stack([],dict,call)
    Stack({},)

    Any non-Mapping iterable will do for the arguments list.
    Any Mapping will do for the keywords dictionary
    """
    stack, kwargs, func = stack.pop(2)
    if isinstance(kwargs, collections.Mapping):
        stack, args = stack.pop()
        return stack.push(func(*args, **kwargs))
    return stack.push(func(*kwargs))  # kwargs was just args


@Combinator
def dip(stack):
    stack, x, p = stack.pop(2)
    return stack.push(*p).push(x)


@Combinator
def cons(stack):
    stack, p, q = stack.pop(2)
    return stack.push(enlist(p, *q))


@Combinator
def take(stack):
    stack, p, q = stack.pop(2)
    return stack.push(list(p) + [q])


# noinspection PyPep8Naming
@Combinator
def Ic(stack):
    """
    the I combinator. Unquotes the iterable by pushing its elements.
    >>> from operator import add
    >>> from drython.stack import op
    >>> Stack([1,2,op(add)], Ic)
    Stack(3,)
    """
    stack, x = stack.pop()
    return stack.push(*x)


# noinspection PyPep8Naming
@Combinator
def Jc(stack):
    stack, p, q, r, s = stack.pop(4)
    return stack.push(q, p, *s).push(r, *s)


# noinspection PyPep8Naming
@Combinator
def Bc(stack):
    stack, p, q = stack.pop()
    return stack.push(*p).push(*q)


# noinspection PyPep8Naming
@Combinator
def Sc(stack):
    stack, p, q, r = stack.pop(3)
    return stack.push(enlist(p, *q), p, *r)


# noinspection PyPep8Naming
@Combinator
def Tc(stack):
    stack, p, q = stack.pop(2)
    return stack.push(q, *p)


Cc = defcombinator([swap], dip, Ic)

# Kc = defcombinator([pop], dip, Ic)
# noinspection PyPep8Naming
@Combinator
def Kc(stack):
    stack, p, q = stack.pop(2)
    return stack.push(*q)


Wc = defcombinator([dup], dip, Ic)


# noinspection PyPep8Naming
@Combinator
def Xc(stack):
    p = stack.peek()
    return stack.push(*p)


@Combinator
def dipd(stack):
    stack, x, y, p = stack.pop(3)
    return stack.push(*p).push(x, y)


@Combinator
def dipdd(stack):
    stack, x, y, z, p = stack.pop(4)
    return stack.push(*p).push(x, y, z)


@Combinator
def step(stack):
    stack, it, p = stack.pop(2)
    for a in it:
        stack.push(a).push(*p)


@Combinator
def nullary(stack):
    stack, p = stack.pop()
    return stack.push(stack.push(*p).peek())


@Combinator
def cleave(stack):
    stack, x, p, q = stack.pop(3)
    return stack.push(
        stack.push(x, *p).peek(),
        stack.push(x, *q).peek())


@Combinator
def ifte(stack):
    """
    the if-then-else combinator
    >>> from operator import lt
    >>> from drython.stack import op
    >>> Stack([1,2,op(lt)],
    ...       [['was true'],Print,call],
    ...       [["wasn't"],Print,call], ifte)
    was true
    Stack(None,)
    >>> Stack([2,1,op(lt)],
    ...       [['was true'],Print,call],
    ...       [["wasn't"],Print,call], ifte)
    wasn't
    Stack(None,)
    """
    stack, b, t, e = stack.pop(3)
    return stack.push(*(t if Stack(*b).peek() else e))


@Combinator
def times(stack):
    stack, n, p = stack.pop(2)
    for i in range(n):
        stack = stack.push(*p)


@Combinator
def infra(stack):
    stack, a, p = stack.pop(2)
    return stack.push(Stack(*reversed(a)).push(*p))


@Combinator
def subspace(stack):
    stack, a, p = stack.pop(2)
    return stack.push(Stack(*a).push(*p))

# TODO: port Joy's recursive combinators


__all__ = [e for e in globals().keys() if not e.startswith('_') if e not in _exclude_from__all__]


# combinators are callable instances, not functions, so this helps doctest find their docstrings.
__test__ = {k: globals()[k].__doc__ for k in __all__ if globals()[k].__doc__ is not None}

