from expressive.core import Tuple
from collections import deque
class Stack:
    def __init__(self, *args, head=None):
        self._head = head
        for e in args:
            self._head = (self._head, e)

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
        return Stack(*args, head=self._head)

    def pop(self, depth=1):
        xs = deque()
        head = self._head
        try:
            while depth > 0:
                depth -= 1
                xs.appendleft(head[1])
                head = head[0]
        except TypeError:
            raise IndexError('stack underflow')
        return Tuple(Stack(head=head), *xs)

    def eval(self, scope=None):
        pass

