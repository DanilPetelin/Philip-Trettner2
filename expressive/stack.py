from functools import lru_cache
from expressive.core import Tuple
from collections import deque, Mapping


class Stack:
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


def verb(func):
    func.__verb__ = None
    return func


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


def define(*args):
    @verb
    def phrase(stack):
        return stack.push(*args)
    return phrase


@verb
def wrap(stack):
    stack, depth = stack.pop()
    stack, *args = stack.pop(depth)
    return stack, args


def op(func, depth=2):
    """
    converts a binary Python function into a stack word
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
    @lru_cache  # memoize
    @verb
    def op_word(stack):
        stack, *args = stack.pop(depth)
        return stack.push(func(*args))
    return op_word


def op1(func):
    return op(func, 1)


nop = define()


@verb
def dip(stack):
    stack, x, p = stack.pop(2)
    return stack.push(*p).push(x)


@verb
def dup(stack):
    return stack.push(stack.peek())


@verb
def ba(stack):
    stack, a, b = stack.pop(2)
    return stack.push(b, a)


bac = define((ba,), dip)


@verb
def cab(stack):
    stack, a, b, c = stack.pop(3)
    return stack.push(c, a, b)


@verb
def bca(stack):
    stack, a, b, c = stack.pop(3)
    return stack.push(b, c, a)


@verb
def cba(stack):
    stack, a, b, c = stack.pop(3)
    return stack.push(c, b, a)


@verb
def pop(stack):
    stack, a = stack.pop()
    return stack


popd = define((pop,), dip)
dupd = define((dup,), dip)
cabd = define((cab,), dip)
bcad = define((bca,), dip)
cbad = define((cba,), dip)


@verb
def choice(stack):
    stack, b, t, f = stack.pop(3)
    return stack.push(t if b else f)


@verb
def use(stack):
    stack, p = stack.pop()
    return stack.push(*p)


@verb
def hatch(stack):
    p = stack.peek()
    return stack.push(*p)


if __name__ == "__main__": import doctest; doctest.testmod()

