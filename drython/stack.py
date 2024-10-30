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
from __future__ import absolute_import, division
from drython.statement import Print

from functools import update_wrapper
from collections import deque

from drython.core import entuple, efset


# To avoid circular dependencies in this package,
# stack.py shall depend only on the core.py and statement.py modules.
# statement.py is not required in the current version.
from drython.statement import Raise


class Stack(object):
    """
    Stack is a data structure for metaprogramming.

    Pushing a special type of function, called a combinator, onto a
    Stack applies the combinator to elements from the stack.
    """

    def __init__(self, *args, **rest):
        assert set(rest.keys()) <= efset('rest')
        self.head = rest.get('rest', None)
        for e in args:
            if hasattr(e, '_combinator_'):
                self.head = e(self).head
            else:
                self.head = (self.head, e)

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
        return 'Stack' + repr(tuple(reversed(self)))
        # return 'Stack(head=%s)' % repr(self.head)

    def __reversed__(self):
        """
        returns elements in insertion order.
        >>> list(reversed(Stack(1,2,3)))
        [1, 2, 3]
        """
        return reversed(tuple(self))

    def push(self, *args):
        """
        push an element on top of the stack. Does not mutate this stack.

        Because Stack is implemented as a linked list, the new stack
        can (and does) share its tail with the original. Unlike
        strings, pushing to a long stack doesn't double the memory
        required, it just adds a link.

        >>> spam = Stack()
        >>> spam.push(1)
        Stack(1,)
        >>> spam  # original is still there.
        Stack()

        Returns the new stack.
        >>> Stack().push(1).push(2).push(3).push(4)
        Stack(1, 2, 3, 4)

        Same as above
        >>> Stack().push(1, 2, 3, 4)
        Stack(1, 2, 3, 4)

        Pushing a combinator executes it
        >>> from drython.combinators import dup
        >>> Stack().push(1, dup, 2)
        Stack(1, 1, 2)

        Chaining push after *unpacking
        >>> Stack().push(*[1, 2, 3]).push(dup)
        Stack(1, 2, 3, 3)
        """
        return Stack(*args, rest=self.head)

    def pop(self, depth=1):
        r"""
        >>> four = Stack(1,2,3,4)
        >>> four.pop()  # depth defaults to 1
        (Stack(1, 2, 3), 4)
        >>> four.pop(1)
        (Stack(1, 2, 3), 4)
        >>> four.pop(2)  # order preserved.
        (Stack(1, 2), 3, 4)
        >>> four.pop(3)
        (Stack(1,), 2, 3, 4)
        >>> four.pop(4)
        (Stack(), 1, 2, 3, 4)
        >>> stack, a, b = four.pop(2)
        >>> Print(stack, a, b, sep='\n')
        Stack(1, 2)
        3
        4
        >>> try:
        ...     four.pop(5)
        ...     assert False
        ... except IndexError as ie:
        ...     Print(ie)
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
            Raise(IndexError('Stack underflow'), From=te)
        return entuple(Stack(rest=head), *xs)

    def peek(self, depth=None):
        """
        >>> Stack(1,2,3).peek()
        3
        >>> Stack(1,2,3).peek(1)
        (3,)
        >>> Stack(1,2,3).peek(2)  # order preserved
        (2, 3)
        >>> Stack(1,2,3).peek(3)
        (1, 2, 3)
        >>> try:
        ...     Stack(1,2,3).peek(4)
        ...     assert False
        ... except IndexError as ie:
        ...     Print(ie)
        Stack underflow
        """
        if depth:
            res = self.pop(depth)[1:]
        else:
            stack, res = self.pop()
        return res


# ###
# Combinator constructors
# ###

class Combinator(object):
    """
    Marks func as a combinator. Combinators act on a Stack, and return a Stack.

    A list containing combinators is not itself a combinator, but a kind of
    quoted program. Some combinators consume these quoted programs.
    """
    _combinator_ = None

    def __init__(self, func):
        self.func = func
        update_wrapper(self, func)
        # self.__doc__ = func.__doc__

    def __call__(self, stack):
        return self.func(stack)

    def __repr__(self):
        return self.func.__name__


# @lru_cache()  # memoized
def op(func, depth=2):
    """
    converts a binary Python function into a combinator
    >>> from operator import add, mul
    >>> Stack(2, 3, op(add))
    Stack(5,)
    >>> Stack(2, 3, op(mul)).peek()
    6
    >>> Stack(4, 2, 3, op(add), op(mul)).peek()
    20

    you can specify a different arity
    >>> Stack(1,2,3,4,5,op(entuple,4))
    Stack(1, (2, 3, 4, 5))

    but the default assumption is two arguments
    >>> Stack(1,2,3,op(entuple))
    Stack(1, (2, 3))
    """

    class OpCombinator(Combinator):
        def __repr__(self):
            name = func.__name__
            if func.__name__.startswith('<'):
                name = repr(func)
            if depth == 2:
                return "op(%s)" % name
            return "op({0}, {1})".format(name, depth)

    @OpCombinator
    # @Combinator
    def op_combinator(stack):
        stack_args = stack.pop(depth)
        stack = stack_args[0]
        args = stack_args[1:]
        return stack.push(func(*args))

    # return Combinator(op_combinator)
    return op_combinator


def op1(func):
    """ short for op(func, 1). Unary Python function to combinator"""
    return op(func, 1)


def defcombinator(*args):
    """ Creates a new combinator from a composition of other combinators."""

    @Combinator
    def phrase(stack):
        return stack.push(*args)

    return phrase


class Def(tuple):
    """
    Defines a Python function from stack elements.

    Def is an executable tuple for metaprogramming.
    >>> from operator import mul, add
    >>> from drython.combinators import dup
    >>> square = Def(dup,op(mul))
    >>> square(7)
    49
    >>> square(4)
    16
    >>> square
    Def(dup, op(mul))
    """
    def __new__(cls, *elements):
        return tuple.__new__(cls, elements)

    def __call__(self, *args):
        return Stack(*args).push(*self).peek()

    def __repr__(self):
        return "Def" + tuple.__repr__(self)
