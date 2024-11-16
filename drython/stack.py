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
from drython.statement import Print, Raise

from functools import update_wrapper, partial
from collections import deque, Mapping

from drython.core import entuple, efset, decorator


# To avoid circular dependencies in this package,
# stack.py shall depend only on the core.py and statement.py modules.

class Stack(object):
    """
    Stack is a data structure for metaprogramming.

    Pushing a special type of function, called a combinator, onto a
    Stack applies the combinator to to the stack.

    Pushing an ordinary Pyhton function applies it to a
    list of arguments on the top of the stack.

    (The Print function returns None)
    >>> Stack([1,2,3],Print)
    1 2 3
    Stack(None,)

    Keywords are also supported with a dictionary on top of the list.
    >>> Stack([1,2,3],dict(sep=':'),Print)
    1:2:3
    Stack(None,)

    Use an empty list for no arguments.
    >>> Stack([],dict)
    Stack({},)

    Any non-Mapping iterable will do for the arguments list.
    Any Mapping will do for the keywords dictionary
    """

    def run(self, func):
        stack, kwargs = self.pop()
        if isinstance(kwargs, Mapping):
            stack, args = stack.pop()
            return stack.push(func(*args, **kwargs))
        return stack.push(func(*kwargs))  # kwargs was just args

    def __init__(self, *args, **rest):
        assert set(rest.keys()) <= efset('rest')
        # Stack operations are postfix.
        # Thus the "cons cells" composing the stack are ordered (rest, top);
        # reversed compared to lisp list convention of (first, rest).
        self.head = rest.get('rest', None)
        for e in args:
            if callable(e):
                if hasattr(e, '_combinator_'):
                    self.head = e(self).head
                else:
                    self.head = self.run(e).head
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

    def trace(self, *words):
        """
        Shows the stack returned by each word.

        Used for developing and debugging stack programs.
        >>> from drython.combinator import *
        >>> Stack((7,),{}).trace(pop,Ic,dup,times)
        Stack((7,), {}) pop
        Stack((7,),) Ic
        Stack(7,) dup
        Stack(7, 7) times
        Stack(49,)
        """
        next = self
        for word in words:
            Print(next, word)
            next = next.push(word)
        return next

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
        >>> from drython.combinator import dup
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


@decorator
class Phrase(object):
    """ Creates a new combinator from a composition of other combinators.
    >>> from drython.combinator import dup, bi
    >>> from operator import mul
    >>> @Phrase(dup,bi,mul)
    ... def square(): '''multiplies by itself'''

    The function code is the phrase. The def is just for the name and docstring.
    >>> square.__doc__
    'multiplies by itself'
    >>> Stack(3,square)
    Stack(9,)
    """
    _combinator_ = None

    def __init__(self, f, *words):
        self.words = words
        update_wrapper(self, f)

    def __call__(self, stack):
        return stack.push(*self.words)

    def __repr__(self):
        return self.__name__


class Def(tuple):
    """
    Defines a Python function from stack elements.

    The stack begins with the args tuple and kwargs dict, applies the words, and returns the topmost element.
    >>> from drython.combinator import pop,Ic,dup,bi
    >>> from operator import mul, add
    >>> Def()(1,2,3,foo='bar')
    {'foo': 'bar'}
    >>> Def(pop)(1,2,3,foo='bar')
    (1, 2, 3)

    equivalent to lambda x: x*x, but without using intermediate variables
    >>> square = Def(pop,Ic,dup,bi,mul)
    >>> square(7)
    49
    >>> square(4)
    16

    the repr is readable code.
    >>> square
    Def(pop, Ic, dup, bi, <built-in function mul>)
    """

    def __new__(cls, *elements):
        return tuple.__new__(cls, elements)

    def __call__(self, *args, **kwargs):
        return Stack(args, kwargs).push(*self).peek()

    def __repr__(self):
        return "Def" + tuple.__repr__(self)
