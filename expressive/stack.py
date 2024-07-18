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
Stack-based combinator algebra for Python.
"""

from functools import lru_cache
from itertools import permutations
from expressive.core import Tuple
from collections import deque, Mapping


class Stack:
    """
    Stack is an executable data structure for metaprogramming.

    Pushing a special type of function, called verb, onto a
    Stack applies the verb to nouns from the stack.

    Non-verb elements are considered nouns.

    Functions that return a verb (like op) are considered adjectives.
    Adjectives can create or decorate verbs.

    A list containing verbs is still a noun. This is a kind of
    quoted program.

    Verbs that consume quoted programs are called combinators.
    """
    def __init__(self, *args, rest=None):
        self.head = rest
        for w in args:
            if hasattr(w, '__verb__'):
                self.head = w(self).head
            else:
                self.head = (self.head, w)

    def __iter__(self):
        """
        Stack returns its elements in the reverse of insertion order,
        hence the name.
        >>> list(Stack(1,2,3))
        [3, 2, 1]
        """
        def it():
            head = self.head
            while head:
                yield head[1]
                head = head[0]
        return it()

    def __repr__(self):
        return 'Stack' + repr(tuple(reversed(tuple(self))))
        # return 'Stack(head=%s)' % repr(self.head)

    def push(self, *args):
        """
        Add an element on top of the stack.
        >>> Stack().push(1)
        Stack(1,)

        Returns the new stack.
        >>> Stack().push(1).push(2).push(3).push(4)
        Stack(1, 2, 3, 4)

        Same as above
        >>> Stack().push(1, 2, 3, 4)
        Stack(1, 2, 3, 4)

        Pushing a stack word executes it
        >>> Stack().push(1, dup, 2)
        Stack(1, 1, 2)
        """
        return Stack(*args, rest=self.head)

    def pop(self, depth=1):
        """
        >>> four = Stack(1,2,3,4)
        >>> four.pop()
        (Stack(1, 2, 3), 4)
        >>> four.pop(1)
        (Stack(1, 2, 3), 4)
        >>> four.pop(2)
        (Stack(1, 2), 3, 4)
        >>> four.pop(3)
        (Stack(1,), 2, 3, 4)
        >>> four.pop(4)
        (Stack(), 1, 2, 3, 4)
        >>> try:
        ...     four.pop(5)
        ...     assert False
        ... except IndexError as ie:
        ...     print(ie)
        Stack underflow
        """
        xs = deque()
        head = self.head
        try:
            while depth > 0:
                depth -= 1
                xs.appendleft(head[1])
                head = head[0]
        except TypeError as te:
            raise IndexError('Stack underflow') from te
        return Tuple(Stack(rest=head), *xs)

    def peek(self, depth=None):
        """
        >>> Stack(1,2,3).peek()
        3
        >>> Stack(1,2,3).peek(1)
        [3]
        >>> Stack(1,2,3).peek(2)
        [2, 3]
        >>> Stack(1,2,3).peek(3)
        [1, 2, 3]
        >>> try:
        ...     Stack(1,2,3).peek(4)
        ...     assert False
        ... except IndexError as ie:
        ...     print(ie)
        Stack underflow
        """
        if depth:
            stack, *res = self.pop(depth)
        else:
            stack, res = self.pop()
        return res

# ###
# verb creation functions
# ###

def verb(func):
    """Marks func as a verb. Verbs act on nouns in a Stack."""
    func.__verb__ = None
    return func


def op(func, depth=2):
    """
    converts a binary Python function into a verb
    >>> from operator import add, mul
    >>> Stack(2, 3, op(add))
    Stack(5,)
    >>> Stack(2, 3, op(mul)).peek()
    6
    >>> Stack(4, 2, 3, op(add), op(mul)).peek()
    20

    you can specify a different arity
    >>> Stack(1,2,3,4,5,op(Tuple,4))
    Stack(1, (2, 3, 4, 5))

    but the default assumption is two arguments
    >>> Stack(1,2,3,op(Tuple))
    Stack(1, (2, 3))
    """
    @lru_cache()  # memoize
    @verb
    def op_verb(stack):
        stack, *args = stack.pop(depth)
        return stack.push(func(*args))
    op_verb.__name__ = 'verb_'+op_verb.__name__
    return op_verb


def op1(func):
    """ short for op(func, 1). Unary Python function to verb"""
    return op(func, 1)


def define(*args):
    """ Creates a new verb that pushes the given arguments on the stack. """
    @verb
    def phrase(stack):
        return stack.push(*args)
    return phrase


# ##
# Stack manipulation verbs
# ##


@verb
def pop(stack):
    """
    discards the top of the stack
    >>> Stack(..., 'a', pop)
    Stack(Ellipsis,)
    """
    stack, a = stack.pop()
    return stack


@verb
def dup(stack):
    """
    duplicates the top of the stack
    >>> Stack(..., 'a', dup)
    Stack(Ellipsis, 'a', 'a')
    """
    return stack.push(stack.peek())


@verb
def nop(stack):
    """ no-operation. Returns stack unchanged. """
    return stack


@verb
def swap(stack):
    """
    swaps the top two elements of the stack
    >>> Stack(..., 'a', 'b', swap)
    Stack(Ellipsis, 'b', 'a')
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
@verb
def {0}(stack):
    """
    permutes the top three elements of the stack,
    >>> Stack(..., 'a', 'b', 'c', {0})
    Stack(Ellipsis, '{1}', '{2}', '{3}')
    """
    stack, a, b, c = stack.pop(3)
    return stack.push({1},{2},{3})

    '''.format(''.join(_cs), *_cs))
# del _cs


# creates all depth-4 stack permutation functions
for _cs in permutations('abcd'):
    if _cs[0] == 'a':
        continue  # depth < 4; already defined above
    exec('''
@verb
def {0}(stack):
    """
    permutes the top four elements of the stack,
    >>> Stack(..., 'a', 'b', 'c', 'd', {0})
    Stack(Ellipsis, '{1}', '{2}', '{3}', '{4}')
    """
    stack, a, b, c, d = stack.pop(4)
    return stack.push({1},{2},{3},{4})

    '''.format(''.join(_cs), *_cs))
del _cs


# popd = define((pop,), dip)
@verb
def popd(stack):
    """
    pops one deeper
    >>> Stack(..., 'a', 'b', popd)
    Stack(Ellipsis, 'b')
    """
    stack, a, b = stack.pop(2)
    return stack.push(b)


# dupd = define((dup,), dip)
@verb
def dupd(stack):
    """
    duplicates one deeper
    >>> Stack(..., 'a', 'b', dupd)
    Stack(Ellipsis, 'a', 'a', 'b')
    """
    stack, a, b = stack.pop(2)
    return stack.push(a, a, b)


# ##
# Operator verbs
# ##


@verb
def quote(stack):
    """
    wraps the top n elements in a list
    >>> Stack('a','b','c',2,quote)
    Stack('a', ['b', 'c'])
    """
    stack, depth = stack.pop()
    stack, *args = stack.pop(depth)
    return stack.push(args)


@verb
def choice(stack):
    stack, b, t, f = stack.pop(3)
    return stack.push(t if b else f)


# ##
# Combinators
# ##

@verb
def do(stack):
    """
    calls an ordinary Python function using the stack.
    (The print function returns None)
    >>> Stack((1,2,3),print,do)
    1 2 3
    Stack(None,)

    Keywords are also supported with a dictionary
    >>> Stack((1,2,3),dict(sep=':'),print,do)
    1:2:3
    Stack(None,)

    Use an empty tuple for no arguments
    >>> Stack((),dict,do)
    Stack({},)
    """
    stack, kwargs, func = stack.pop(2)
    if isinstance(kwargs, Mapping):
        stack, args = stack.pop()
        return stack.push(func(*args, **kwargs))
    return stack.push(func(*kwargs))  # kwargs was just args


@verb
def dip(stack):
    stack, x, p = stack.pop(2)
    return stack.push(*p).push(x)


@verb
def Ic(stack):
    """
    the I combinator. Unquotes the iterable by pushing its elements.
    >>> from operator import add
    >>> Stack([1,2,op(add)], Ic)
    Stack(3,)
    """
    stack, x = stack.pop()
    return stack.push(*x)


@verb
def Bc(stack):
    stack, p, q = stack.pop()
    return stack.push(*p).push(*q)


Cc = define([swap], dip, Ic)
Kc = define([pop], dip, Ic)
Wc = define([dup], dip, Ic)


@verb
def Xc(stack):
    p = stack.peek()
    return stack.push(*p)


@verb
def dipd(stack):
    stack, x, y, p = stack.pop(3)
    return stack.push(*p).push(x, y)


@verb
def dipdd(stack):
    stack, x, y, z, p = stack.pop(4)
    return stack.push(*p).push(x, y, z)


@verb
def ifte(stack):
    stack, b, t, e = stack.pop(3)
    return stack.push(*(t if Stack(*b).peek() else e))


@verb
def step(stack):
    stack, it, p = stack.pop(2)
    for a in it:
        stack.push(a).push(*p)





if __name__ == "__main__": import doctest; doctest.testmod()

