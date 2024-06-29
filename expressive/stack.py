from expressive.core import Tuple
from collections import deque


class Stack:
    def __init__(self, *args, head=None):
        self._head = head
        for w in args:
            if hasattr(w, '__stack_word__'):
                self._head = w(self)._head
            else:
                self._head = (self._head, w)

    def __iter__(self):
        def it():
            head = self._head
            while head:
                yield head[1]
                head = head[0]
        return it()

    def __repr__(self):
        return 'Stack%s' % repr(tuple(reversed(tuple(self))))
        # return 'Stack(head=%s)' % repr(self._head)

    def push(self, *args):
        """
        >>> Stack().push(1)
        Stack(1,)
        >>> Stack().push(1, 2, 3, 4, 5)
        Stack(1, 2, 3, 4, 5)
        >>> Stack(1, 2).push(3).push(4, 5)
        Stack(1, 2, 3, 4, 5)
        """
        return Stack(*args, head=self._head)

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
        head = self._head
        try:
            while depth > 0:
                depth -= 1
                xs.appendleft(head[1])
                head = head[0]
        except TypeError:
            raise IndexError('Stack underflow')
        return Tuple(Stack(head=head), *xs)

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




def stack_word(func):
    func.__stack_word__ = None
    return func


@stack_word
def call(stack):
    stack, func, args, kwargs = stack.pop(3)
    return stack.push(func(*args,**kwargs))


@stack_word
def wrap(stack):
    stack, depth = stack.pop()
    stack, *args = stack.pop(depth)
    return stack, args


def op(func):
    """
    >>> from operator import add, mul
    >>> Stack(2, 3, op(add))
    Stack(5,)
    >>> Stack(2, 3, op(mul)).peek()
    6
    >>> Stack(4, 2, 3, op(add), op(mul)).peek()
    20
    """
    @stack_word
    def binary_operator(stack):
        stack, x, y = stack.pop(2)
        return stack.push(func(x, y))
    return binary_operator


def op1(func):
    @stack_word
    def unary_operator(stack):
        stack, x = stack.pop()
        return stack.push(func(x))


@stack_word
def dup(stack):
    return stack.push(stack.peek())


if __name__ == "__main__": import doctest; doctest.testmod()
