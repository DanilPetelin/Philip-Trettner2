# Copyright 2015, 2016 Matthew Egan Odendahl
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
########################################################################
"""
This module exports a set of statement replacement functions.

These correspond to Python statements, but are usable as expressions,
including (for example) in eval and lambda. As higher-order functions,
these substitutes can be composed, curried, returned, and passed as
arguments, unlike the statements they emulate, which must stand alone.

Typical module import is:

    from drython.statement import *

This includes
`Atom` (thread-locked updates and nonlocal assignment emulation),
`Box` (simpler nonlocals for Python 2, but not thread safe),
`Bind` (sets and deletes items and attrs)
`let` (local assignment emulation and Return() support),
`do` (for side effects in expressions, especially lambdas),
`loop` (optimized tail-call recursion loops)
`dest` (destructuring bindings)
plus the 13 reserved word statement replacements.

Despite convention for Python function names, the 13 replacements
`Assert`, `Break`, `Continue`, `Elif/Else`, `For/Else`, `Import/From`,
`Pass`, `Print`, `Raise/From`, `let/Return`, `Try/Except/Else/Finally`,
`With`, and `While/Else` are capitalized to avoid conflicts with the
original Python reserved word.

`Print` is provided since it's a statement in Python 2. This is merely
an alias for the builtin `print` function. Without an alias, Python 2
files would be forced to use `from __future__ import print_function`
even if they already used print statements, or else a long invocation
like `getattr(__builtin__, 'print')`.

Functions for the reserved words `False`, `None`, `True`, `and`, `if`,
`in`, `is`, `lambda`, `not`, `or`, and `yield` are not provided because
they are already expressions. Similarly for most operators, but not for
assignments. The `yield` expressions are not entirely compatible with
the replacements, but see `@generator` in the expression module.

`Bind` replaces `del` and `=` statements when targeting attrs or items.
The builtin `globals` function effectively replaces the `global`
statement. Due to optimizations for Python locals, the changes to the
builtin `locals()` may not write through to the local scope, unlike
`globals()`, which does guarantee changes are reflected in the global
scope. Although direct local and nonlocal `del` and `=` statements
cannot be delegated to called functions, lambda can introduce new locals
in its body. The `let` function immediately calls a lambda to make this
use convenient.

`dest` substitutes for starred assignments, in combination with a
lambda introduction or Bind. `dest` is more powerful than Python3's
nested iterable destructuring because it also works on mappings.

The `nonlocal` statement doesn't exist in Python 2. The workaround is to
use a mutable container object instead.  `Atom` is a mutable container
and also has a `.reset()` method to replace `=` when used as a nonlocal
workaround.  `Atom` can also be used locally, of course.

The augmented assignment statements, += -= *= /= %= &= |= ^= <<= >>= **=
//=, are partially supported with the operator module combined with
Atom.swap() and assign_attr()/assign_item() from core.

Use the metaclass directly to substitute for `class`, for example
  X = type('X', (A, B), dict(a=1))
is the same as
  class X(A, B): a = 1

A substitute for `def` is not provided here, but `lambda` is a viable
alternative now that statements are available as expressions.
Multiple sequential expressions are available in lambda via do.
Multiple exits are available via let/Return:

    lambda ...: let(lambda:(
        expression1,
        expression2,
        ...
        Return(...)))

See stack.Def and macros.L1 for two alternative `def` substitutes.
"""
# To avoid circular dependencies in this package,
# statement.py shall depend only on the core.py module

from __future__ import absolute_import, division, print_function

from functools import wraps
from itertools import islice
from collections import Mapping
from importlib import import_module
import sys

from drython.core import entuple, efset, partition, Empty


class LabeledBreak(BaseException):
    def handle(self, label=None):
        """ re-raise self if label doesn't match. """
        if self.label is None or self.label == label:
            return
        else:
            raise self

    def __init__(self, label=None):
        self.label = label
        raise self


class LabeledResultBreak(LabeledBreak):
    def __init__(self, result=None, *results, **label):
        assert set(label.keys()) <= efset('label')
        if results:
            self.result = entuple(result, *results)
        else:
            self.result = result
        LabeledBreak.__init__(self, label.get('label', None))


_exclude_from__all__ = set(globals().keys())
__test__ = {}


def _private():
    class PassType(object):
        """
        A no-operation empty thunk; returns None.

        Pass can substitute for `pass` where a statement substitution
        requires a thunk. (A thunk is a 0-arg func.) Pass() also
        works anywhere `pass` does, because None does, and in some
        places `pass` does not, like
        >>> (lambda: Pass())()
        """
        __slots__ = ()

        def __call__(self):
            return None

        def __repr__(self):
            return 'Pass'

    res = PassType()

    def __init__(self):
        raise TypeError("cannot create 'PassType' instances")

    PassType.__init__ = __init__

    __test__[PassType.__name__] = PassType.__doc__

    return res


Pass = _private()
del _private


# noinspection PyPep8Naming
def Assert(boolean):
    """
    Wraps an assert statement.
    >>> Assert(1+1 == 2)
    >>> Assert(1+1 == 7)
    Traceback (most recent call last):
        ...
    AssertionError

    Unlike naked assert statements,
    Assert() is allowed anywhere expressions are.
    When assert is disabled, Assert() simply returns None.
    """
    assert boolean


class Break(LabeledResultBreak):
    """
    a substitute for the break statement.

    This breaks out of While and For, by raising itself.
    >>> try:
    ...     Break()
    ...     assert False
    ... except BaseException as ex:
    ...     Print(repr(ex))
    Break()

    Unlike while and for, While and For support labels
    to break targeted outer loops from within inner loops.

    >>> For(range(4), lambda i:
    ...     For(range(4), lambda j:
    ...         (Break() if i==j else Pass(),
    ...          Print(i, j))))
    1 0
    2 0
    2 1
    3 0
    3 1
    3 2
    >>> For(range(1, 4), lambda i:
    ...     For(range(4), lambda j:
    ...         (Break(label="outer") if i==j else Pass(),
    ...          Print(i, j))),
    ...     label="outer")
    1 0

    Break can also return a value. This becomes the result of
    the loop itself.
    >>> str(For(range(1,100,7), lambda i:
    ...         Print('.'*i) if i<20 else Break(i)))
    .
    ........
    ...............
    '22'
    """


class Continue(LabeledBreak):
    """
    a substitute for the continue statement.

    This continues a While or For, by raising self.
    >>> try:
    ...     Continue()
    ...     assert False
    ... except BaseException as ex:
    ...     Print(repr(ex))
    Continue()

    Unlike while and for, While and For support labels
    to continue a targeted outer loop from within inner loops.
    If the label exists, but doesn't match, the Continue is
    raised again.

    >>> For(range(4), lambda i:
    ...     For(range(4), lambda j:
    ...         (Continue("outer") if i==j else Pass(),
    ...          Print(i,j))),
    ...     label="outer")
    1 0
    2 0
    2 1
    3 0
    3 1
    3 2
    >>> For(range(3), lambda i:
    ...     For(range(3), lambda j:
    ...         (Continue() if i==j else Pass(),
    ...          Print(i,j))))
    0 1
    0 2
    1 0
    1 2
    2 0
    2 1
    >>> For(range(3), lambda i: do(
    ...     Print(i),
    ...     While(lambda:True, lambda:
    ...         Continue('outer')),
    ...     Print('impossible')),
    ...     label='outer')
    0
    1
    2
    """


# a Smalltalk-like implementation of Lisp's COND.
# noinspection PyPep8Naming
def Elif(*thunks, **Else):
    """
    Cascading if.

    The args are paired. Pairs are checked in order. If the left
    evaluates to true, the right is called. If all are false, Else is
    called.
    >>> Elif()  # Else defaults to Pass
    >>> Elif(Pass, lambda:1)  # Pass() is None
    >>> Elif(lambda:True, lambda:1)
    1
    >>> Elif(Pass, lambda:Print('a'),
    ...      Else=lambda:Print('b'))
    b
    >>> Elif(Pass, lambda:Print('a'),
    ...      Pass, lambda:Print('b'))
    >>> Elif(lambda:True, lambda:Print('a'),
    ...      Pass, lambda:Print('b'))
    a
    >>> Elif(Pass, lambda:1,
    ...      lambda:Print('a'), lambda:2,  # head has to be checked.
    ...      Pass, lambda:3,
    ...      Else=lambda:4)
    a
    4
    >>> Elif(lambda:Print('a'), lambda:2,  # Print returns None
    ...      lambda:3, lambda:4,  # nonzero is truthy
    ...      lambda:Print('skipped?'), lambda:Print('skipped?'),
    ...      Else=lambda:Print('skipped?'))
    a
    4

    Recall that `a if b else c` is already an expression. These can
    be nested, but Elif may be easier to use for deep nesting.
    """
    assert len(thunks) % 2 == 0
    assert set(Else.keys()) <= efset('Else')
    for predicate, thunk in zip(*2 * (iter(thunks),)):
        if predicate():
            return thunk()
    return Else.get('Else', Pass)()


# noinspection PyPep8Naming,PyShadowingNames
def For(iterable, body, Else=Pass, label=None):
    """
    Unpacks each element from iterable and applies body to it.

    Unlike map() (and like `for`) For is strict, not lazy;
    it is not a generator and evaluation begins immediately.

    body must be 1-argument
    >>> For({'a':'A'}.items(), lambda pair:
    ...         Print(pair))
    ('a', 'A')

    Use the star function for unpacking
    >>> from drython.core import star
    >>> For({'key':'value'}.items(), star(lambda k, v:
    ...         (Print(k),
    ...          Print(v))))
    key
    value

    For can nest
    >>> For('ab', lambda i:
    ...     For('AB', lambda j:
    ...         Print(i, j)))
    a A
    a B
    b A
    b B

    For also has an optional Else thunk, and supports labeled
    Break and Continue.
    >>> For(range(99), lambda i:
    ...       Print(i) if i<4 else Break(),
    ...     Else=lambda:
    ...       Print("not found"))
    0
    1
    2
    3
    >>> For(range(2), lambda i:
    ...       Print(i) if i<4 else Break(),
    ...     Else=lambda:
    ...       Print("not found"))
    0
    1
    not found
    """
    try:
        for e in iterable:
            try:
                body(e)
            except Continue as c:
                c.handle(label)
    except Break as b:
        b.handle(label)
        # skip Else() on Break
        return b.result
    return Else()


# noinspection PyPep8Naming
def Import(item, *items, **package_From):
    """
    convenience function wrapping importlib.import_module()

    # from operator import sub, mul
    >>> sub, mul = Import('sub', 'mul', From='operator')
    >>> sub(1,3)
    -2
    >>> mul(2,3)
    6
    >>> operator = Import('operator')  # import operator
    >>> operator.add(1, 1)
    2
    >>> xmldom = Import('xml.dom')  # import xml.dom as xmldom
    >>> hasattr(xmldom,'domreg')
    True

    # from xml.dom import domreg
    >>> domreg = Import('domreg', From='xml.dom')
    >>> xmldom.domreg == domreg
    True

    # from .stack import Stack
    >>> Stack = Import('Stack', From='.stack', package='drython')
    >>> Stack((1,2),sub).peek()
    -1
    """
    assert set(package_From.keys()) <= efset('package', 'From')
    package = package_From.get('package', None)
    From = package_From.get('From', None)
    if items:
        items = entuple(item, *items)
    if package:
        import_module(package)  # really necessary?
    if From:
        module = import_module(From, package)
        if items:
            return (getattr(module, item) for item in items)
        else:
            return getattr(module, item)
    else:
        if items:
            return (import_module(item, package) for item in items)
        else:
            return import_module(item, package)


# Did
# from __future__ import print_function
# at the top of this module, so this also works in Python 2.
Print = print


# noinspection PyPep8Naming,PyCompatibility
def Raise(ex=None, From=Ellipsis):
    """
    raises an exception.

    >>> Raise(ZeroDivisionError)
    Traceback (most recent call last):
        ...
    ZeroDivisionError


    >>> Raise(ZeroDivisionError("Just a test!"))
    Traceback (most recent call last):
        ...
    ZeroDivisionError: Just a test!

    Unlike a naked raise statement, this works anywhere
    an expression is allowed, which has some unexpected uses:
    >>> from itertools import count
    >>> list(i if i<10 else Raise(StopIteration) for i in count())
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    empty raise also works as expected
    >>> try:
    ...     1/0
    ... except ZeroDivisionError:
    ...     Print('zde!')
    ...     Raise() # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    ZeroDivisionError: ...

    raise ... from is also supported, even experimentally in 2.7
    >>> Raise(ZeroDivisionError, From=None)
    Traceback (most recent call last):
        ...
    ZeroDivisionError

    >>> try:
    ...     Raise(ZeroDivisionError, From=StopIteration())
    ... except ZeroDivisionError as zde:
    ...     Print(repr(zde.__cause__))
    StopIteration()
    """
    if ex:
        if From is not Ellipsis:
            if ex.__class__ == type:
                ex = ex()
            # raise ex from From
            ex.__cause__ = From
        raise ex
    raise
    # there are two other possible versions of Raise below.


if sys.version_info[0] >= 3:
    _doc = Raise.__doc__  # preserve docstring for new version.
    # check for Python's 3.3+ PEP 409 which allows raise ... from None
    if sys.version_info[1] >= 3:
        # noinspection PyCompatibility
        exec ("""\
def Raise(ex=None, From=Ellipsis):
    if ex:
        if From is not Ellipsis:
            raise ex from From
        raise ex
    raise
""")
    else:
        # noinspection PyCompatibility
        exec ("""\
def Raise(ex=None, From=Ellipsis):
    if ex:
        if From is not Ellipsis:
            if From is not None:
                raise ex from From
            elif type(ex.__init__) != type(Exception().__init__):
                ex = ex()
            ex.__context__ = None
        raise ex
    raise
""")
    Raise.__doc__ = _doc
    del _doc


class Return(LabeledResultBreak):
    """
    Aborts an expression early, but keeps a result value.
    Must be wrapped in a let().

    >>> let(lambda: do(
    ...  1,
    ...  2,
    ...  3,))
    3
    >>> let(lambda: do(
    ...  1,
    ...  Return(2),
    ...  3,))
    2

    Like `return` an empty Return() returns None.
    >>> let(lambda: do(
    ...  1,
    ...  Return(),
    ...  3,))

    Like `return`, multiple Return values result in a tuple.
    >>> let(lambda: do(
    ...  1,
    ...  Return(1,2,3),
    ...  3,))
    (1, 2, 3)

    Can return through multiple let()s using a label.
    >>> let(label='outer', body=lambda a=1,d=4: do(
    ...   let(lambda b=42,c=3: do(
    ...     a,
    ...     Return(b,label='outer'),
    ...     c,)),
    ...   d,))
    42
    """


# noinspection PyPep8Naming
def Try(thunk, *Except, **ElseFinally):
    """
    wraps a try statement

    Try() returns the thunk's result normally
    >>> Try(lambda: 1+1)
    2

    Exception handlers are written as an exception type paired with
    a function. The exception handlers are required to take an
    argument, but they are not required to use it.
    Try() returns the exception handler's result on exceptions.
    This overrides both the normal thunk and else part's result.
    Else is not evaluated after exceptions.
    >>> Try(lambda:
    ...         1/0,  # error
    ...     ZeroDivisionError, lambda zdr: do(
    ...         Print(zdr.__class__.__name__),
    ...         'returns: take a limit!',),
    ...     Finally=lambda:
    ...         Print('finally!'),
    ...     Else=lambda:
    ...         Print('returns: or else!'))
    ZeroDivisionError
    finally!
    'returns: take a limit!'

    Try() evaluates to the else part if provided.
    >>> Try(lambda:
    ...         0/1,  # allowed
    ...     ZeroDivisionError, lambda zdr: do(
    ...         Print(zdr),
    ...         'take a limit!',),
    ...     Finally=lambda:
    ...         Print('finally!'),
    ...     Else=lambda:
    ...         'returns: or else!')
    finally!
    'returns: or else!'

    Try() never returns the result of Finally(), which is only
    for side effects.

    Multiple exception handlers are allowed. They're checked
    in order.
    >>> Try(lambda:
    ...         1/0,
    ...     ZeroDivisionError, lambda zdr:
    ...         Print('by ZeroDivisionError'),
    ...     Exception, lambda x:
    ...         Print('by Exception'),)
    by ZeroDivisionError
    >>> Try(lambda:
    ...         1/0,
    ...     Exception, lambda x:
    ...         Print('by Exception'),
    ...     ZeroDivisionError, lambda zdr:
    ...         Print('by ZeroDivisionError'),)
    by Exception

    to catch any exception, like the final `except:`, use BaseException.
    """
    assert set(ElseFinally.keys()) <= efset('Else', 'Finally')
    assert len(Except) % 2 == 0
    assert all(issubclass(x, BaseException)
               for x, c in partition(Except))
    Else = ElseFinally.get('Else', None)
    Finally = ElseFinally.get('Finally', Pass)
    try:
        res = thunk()
    except BaseException as ex:
        for ex_type, ex_handler in partition(Except):
            if isinstance(ex, ex_type):
                return ex_handler(ex)
        else:
            raise
    else:
        if Else:
            res = Else()
    finally:
        Finally()
    return res


class Box(object):
    """
    A simple class with exactly one (mutable) slot 'e'.

    Used internally by Atom.
    """
    __slots__ = 'e'

    def __init__(self, e):
        self.e = e

    def __repr__(self):
        return 'Box(' + repr(self.e) + ')'


class Atom(object):
    """
    a locked boxed mutable variable, assignable in expressions.

    >>> spam = Atom(44)  # initial value (required)
    >>> spam
    Atom(44)
    >>> from operator import sub

    atomic updates with a callback. The element is the first argument.
    >>> spam.swap(sub, 2)
    42

    unbox with .e (element) attr
    >>> spam.e
    42

    get() also works
    >>> spam.get()
    42

    >>> spam.reset('eggs')
    'eggs'
    """

    def __init__(self, e):
        from threading import Lock

        lock = Lock()

        b = Box(e)

        def var_swap(f, *args):
            """
            Atomically updates the element, and returns the new value.

            The return value is set inside the lock, to make it
            consistent with the update.
            """
            # Threading with primitive locks is generally a bad idea.
            # since race conditions are impossible to test properly.
            # The only testing alternative is mathematical proof.
            # Best keep this block as simple as possible.
            # Atom is a useful alternative to primitive locks
            # in many cases.
            with lock:
                b.e = f(b.e, *args)
                res = b.e
            return res

        def var_reset(new):
            """
            Atomically sets the value of this atom to new, ignoring
            the current value. Returns new.
            """
            with lock:
                b.e = new
                res = b.e
            return res

        self.swap = var_swap
        self.reset = var_reset
        self.get = lambda: b.e  # readonly

    @property
    def e(self):
        return self.get()

    @e.setter
    def e(self, new):
        raise AttributeError(
            "Use .swap() or .reset() to assign to a Atom, not .e = ...")

    def __repr__(self):
        return 'Atom(%s)' % repr(self.e)


# noinspection PyPep8Naming
def While(predicate, body, label=None, Else=Pass):
    """
    wraps a while statement.

    # spam = 4
    # while spam:
    #    spam += -1
    #    print(spam)
    >>> from operator import add
    >>> spam = Atom(4)
    >>> While(spam.get, lambda:
    ...     Print(spam.swap(add,-1)))
    3
    2
    1
    0
    >>> spam = Atom(1)
    >>> While(spam.get, lambda:
    ...   Print(spam.swap(add,-1)),
    ... Else=lambda:
    ...   'done')
    0
    'done'
    >>> While(lambda: True, lambda:
    ...   Print(spam.swap(add,1)) if spam.e < 2 else Break(),
    ... Else=lambda:
    ...   Print('impossible'))
    1
    2

    While also supports labels.
    >>> While(lambda: True, lambda:do(
    ...     While(lambda: True, lambda:
    ...         Break('done',label='outer')),
    ...     Print('impossible')),
    ...     label='outer')
    'done'
    """

    try:
        while predicate():
            try:
                body()
            except Continue as c:
                c.handle(label)
    except Break as b:
        b.handle(label)
        return b.result
    return Else()


# noinspection PyPep8Naming
def With(guard, body):
    """
    wraps a with statement; applies body to the result of guard in the
    context of guard.

    >>> from contextlib import contextmanager
    >>> @contextmanager
    ... def test():
    ...     Print('enter')
    ...     try:
    ...         yield 'spam'
    ...     except:
    ...         Print('Caught in manager.')
    ...     Print('exit')

    With returns the result of body
    >>> With(test, lambda ans:do(
    ...     Print(ans),
    ...     'The result.',))
    enter
    spam
    exit
    'The result.'

    exit always happens, like a try/finally
    >>> With(test, lambda ans:
    ...     Raise(Exception))
    enter
    Caught in manager.
    exit


    Unlike with, With supports only one guard, but as pointed out in
    the documentation, a with statement with multiple guards is
    equivalent to nested withs anyway, so

    with A() as a, B() as b:
            suite

    is equivalent to

    with A() as a:
        with B() as b:
            suite

    Thus, nested Withs will work the same way:
    With(A,lambda a:
        With(B,lambda b:
            do(...)))
    """
    with guard() as g:
        return body(g)


def let(body, bind=Empty, label=None):
    """
    immediately calls body.
    can catch a Return exception and returns its result.
    Used for expression-local variables and closures.
    This can fill in for some uses of the '=' assignment statements.
    >>> let(lambda x=4,y=3: x+y)
    7
    >>> let(lambda x='*'*7: x+'spam'+x)
    '*******spam*******'

    Default parameters don't support unpacking like assignment
    statements. Set the argument dictionary with bind. Combine with
    dest for arbitrary destructuring.
    >>> quadruple = (1,2,3,4)
    >>> let(bind=dest(['a',list,'b','c'], quadruple),
    ...     body=lambda a,b,c: Print(a,b,c))
    1 [2, 3] 4

    Combine with attrs to avoid repeating names. This way doesn't
    need bind=. It does require dot access in the body, but that may
    be more convenient in expressions, since that give you a target
    for setattr, delattr, and Bind.
    >>> from drython.core import attrs
    >>> let(lambda x=attrs(
    ...     dest([all,'N','a','b',list,'rest'], quadruple)):
    ...         Print(x.N,x.rest,x.b,x.a))
    (1, 2, 3, 4) [3, 4] 2 1
    """
    try:
        return body(**bind)
    except Return as r:
        r.handle(label)
        return r.result


_sentinel = object()


class Bind(object):
    """
    Convenience assignment expression syntax.
    Does not work directly on locals.

    >>> spam = lambda:None

    You can Bind to an attr that doesn't even exist yet.
    >>> Bind(spam).foo(1)  # returns the value, not spam itself
    1
    >>> spam.foo
    1

    An empty Bind deletes it.
    >>> Bind(spam).foo()
    >>> spam.foo
    Traceback (most recent call last):
        ...
    AttributeError: 'function' object has no attribute 'foo'

    >>> eggs = {}
    >>> Bind(eggs)[1]('one')  # Note this returns the map, not the value
    {1: 'one'}
    >>> eggs
    {1: 'one'}
    >>> Bind(eggs)[1]()
    {}
    >>> eggs
    {}

    Sequences work as well as maps
    >>> bacon = [0,0,0,0]
    >>> Bind(bacon)[1](42)  # similarly returns the list
    [0, 42, 0, 0]

    even slice assignments and deletions work
    >>> Bind(bacon)[:-1]([1,2,3])
    [1, 2, 3, 0]
    >>> Bind(bacon)[1:-1]()
    [1, 0]
    >>> bacon
    [1, 0]
    """

    def __init__(self, to):
        self.to = to

    def __getattribute__(self, item):
        to = object.__getattribute__(self, 'to')
        return lambda value=_sentinel: (
            delattr(to, item) if value is _sentinel
            else do(setattr(to, item, value), value))

    def __getitem__(self, item):
        to = object.__getattribute__(self, 'to')
        return lambda value=_sentinel: do(
            to.__delitem__(item) if value is _sentinel
            else to.__setitem__(item, value),
            to)


def do(*body):
    """
    returns its last argument.
    >>> do(1,1+1,1+1+1)
    3

    To keep all arguments, use a tuple instead of a do.
    >>> (1,1+1,1+1+1)
    (1, 2, 3)

    do is used to combine several expressions into one by sequencing,
    for side-effects. Python guarantees sequential evaluation of
    arguments:
    docs.python.org/3/reference/expressions.html#evaluation-order
    >>> spam = do(Print('side'),Print('effect'),'suppressed',42)
    side
    effect
    >>> spam
    42
    """
    return body[-1] if body else Empty


def loop(f):
    """
    Tail-call optimized recursion.

    The loop decorator injects the recursion thunk factory as the
    first argument, by convention called `recur`. When recur is
    called its thunk must be returned. The recursion doesn't happen
    until after the return, hence it doesn't take up stack frames
    like direct recursion would. To avoid confusion, recur() should
    be returned immediately.

    In decorator form.
    >>> @loop
    ... def my_range(recur, stop, answer=(0,)):
    ...     if answer[-1] >= stop:
    ...         return answer
    ...     return recur(stop, answer + (answer[-1] + 1,))
    >>> my_range(6)
    (0, 1, 2, 3, 4, 5, 6)

    The above in expression form. Notice it's simpler than a While
    expression would be.
    >>> loop(lambda recur, stop,ans=(0,):
    ...     ans if ans[-1] >= stop
    ...     else recur(stop, ans + (ans[-1] + 1,))
    ... )(6)
    (0, 1, 2, 3, 4, 5, 6)
    """
    again = Box(False)

    def recur(*args, **kwargs):
        again.e = True
        return lambda: f(recur, *args, **kwargs)

    @wraps(f)
    def wrapper(*args, **kwargs):
        res = f(recur, *args, **kwargs)
        while again.e:
            again.e = False
            res = res()  # when recur is called it must be returned!
        return res

    return wrapper


def dest(targets, values, bindings=Ellipsis):
    """
    Clojure-style iterable and Mapping destructuring. Returns a dict.

    iterable destructuring is similar to Python's unpacking
    >>> dest(['a','b'],[1,2]) == dict(a=1, b=2)
    True

    list is like a * unpacking. Only one is allowed per iterable,
    but it need not be at the end.
    >>> (dest(['a','b',list,'args','c'],[1,2,3,4,5]) ==
    ...  dict(a=1, b=2, args=[3,4], c=5))
    True

    you can also keep the whole thing with all. It must come first.
    >>> dest([all,'N','a','b'],[1,2]) == dict(a=1, b=2, N=[1,2])
    True

    you can use both all and list in the same iterable
    >>> (dest([all,'N','a','b',list,'args'],[1,2,3,4,5]) ==
    ...  dict(a=1, b=2, args=[3,4,5], N=[1,2,3,4,5]))
    True

    If the targets is a mapping then it re-keys the values mapping.
    >>> dest(dict(a='A',b='B'),dict(A=1,B=2)) == dict(a=1,b=2)
    True

    It works the same on indexes.
    >>> dest(dict(a=0,b=1),[10,11]) == dict(a=10,b=11)
    True

    In Mappings, dict is for defaults. (all still works)
    >>> dest({'a':'A','b':'B','c':'C',dict:dict(a=2,b=3),all:'N'},
    ...     dict(A=5,C=6)) == dict(a=5,b=3,c=6,N=dict(A=5,C=6))
    True

    Keep a set of keys as-is with str.
    >>> (dest({str:{'a','b','c'},'d':'X'},dict(a=1,b=2,c=3,X=42)) ==
    ...  dict(a=1,b=2,c=3,d=42))
    True

    The structures can nest. `dest` will recursively destructure them.
    >>> dest([all,'out',[all,'in','a','b'],
    ...      {str:{'c','d'},e:('f','g')}],
    ...      ['AB',dict(c='C',d='D',e='EF')])
    """
    if bindings is Ellipsis:
        bindings = {}
    if isinstance(targets, Mapping):
        defaults = targets.get(dict, Empty)
        for left, right in targets.items():
            if isinstance(left, str):
                try:
                    bindings[left] = values[right]
                except LookupError:
                    bindings[left] = defaults[left]
            elif left is all:
                bindings[right] = values
            elif left is dict:
                pass
            elif left is str:
                for s in right:
                    bindings[s] = values[s]
            else:
                dest(left, right, bindings)
    else:
        try:
            ivalues = iter(values)
            itargets = iter(targets)
            name = next(itargets)
            if name is all:
                bindings[next(itargets)] = values
                name = next(itargets)
            while True:
                if name is list:
                    # this would be easy if list was only allowed at
                    # the end, like Clojure. but Python3's starred
                    # binding can be in the middle.
                    name = next(itargets)
                    targets = tuple(itargets)  # to count remaining
                    values = list(ivalues)
                    sublist = values[:len(values) - len(targets)]
                    itargets = iter(targets)
                    ivalues = iter(values[len(sublist):])
                    bindings[name] = sublist
                else:
                    try:
                        val = next(ivalues)
                    except StopIteration:
                        raise ValueError(
                            "not enough values to unpack for target %s" %
                            repr(name))
                    if isinstance(name, str):
                        bindings[name] = val
                    else:
                        dest(name, val, bindings)
                name = next(itargets)
        except StopIteration:
            pass
    return bindings


__all__ = [e for e in globals().keys()
           if not e.startswith('_')
           if e not in _exclude_from__all__]
