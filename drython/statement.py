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
This module exports a set of statement replacement functions.

These correspond to Python statements, but are usable as expressions,
including (for example) in eval and lambda. As higher-order functions,
these substitutes can be composed, curried, returned, and passed as
arguments, unlike the statements they emulate, which must stand alone.

Typical module import is:

    from drython.statement import *

This includes
`Atom` (thread-locked nonlocal assignment emulation),
`let` (local assignment emulation and Return() support),
`do` (for side effects in expressions, especially lambdas),
plus the 13 keyword statement replacements.

Despite convention for Python function names, the 13 replacements
Assert, Break, Continue, Elif/Else, For/Else, Import/From, Pass, Print,
Raise/From, let/Return, Try/Except/Else/Finally, With, and While/Else
are capitalized to avoid conflicts with the original Python keywords.

Functions for the keywords `False`, `None`, `True`, `and`, `if`,
`in`, `is`, `lambda`, `not`, `or`, and `yield` are not provided because
they are already expressions. Similarly for most operators.

Print is provided, since it's a statement in Python 2. This is merely
an alias for the builtin print function. Without an alias, Python 2
files would be forced to use `from __future__ import print_function`
even if they already used print statements, or else a long invocation
like `getattr(__builtin__, 'print')`.

Due to optimizations for Python locals, direct local and nonlocal
assignment statements cannot be emulated as functions, but Atom can
substitute for nonlocals in many cases. For the same reason, direct
local and nonlocal `del` statements are not supported, but `del` is
partially supported with delitem from drython.core. (delattr() is
already a builtin)

The augmented assignment statements, += -= *= /= %= &= |= ^= <<= >>= **=
//=, are partially supported with the operator module combined with
Atom.set() and assign_attr()/assign_item() from core.

Assignment statements, =, are partially supported with let(), and by
using Atom.set() or assign_attr()/assign_item(), without the optional
operator.

Use the metaclass directly to substitute for `class`, for example
  X = type('X', (A, B), dict(a=1))
is the same as
  class X(A, B): a = 1

A substitute for `def` is not provided here, but `lambda` is a viable
alternative now that most statements are available as expressions.
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

from importlib import import_module
import sys

from drython.core import entuple, efset, partition, Empty


class LabeledException(Exception):
    def handle(self, label=None):
        """ re-raise self if label doesn't match. """
        if self.label is None or self.label == label:
            return
        else:
            raise self

    def __init__(self, label=None):
        self.label = label
        raise self


class LabeledResultException(LabeledException):
    def __init__(self, result=None, *results, **label):
        assert set(label.keys()) <= efset('label')
        if results:
            self.result = entuple(result, *results)
        else:
            self.result = result
        LabeledException.__init__(self, label.get('label', None))


_exclude_from__all__ = set(globals().keys())
__test__ = {}


def _private():
    class PassType(object):
        """
        A no-operation empty thunk; returns None.
        Pass can substitute for `pass` where a statement substitution requires
        a thunk. (A thunk is a 0-arg func.) Pass() also works anywhere `pass`
        does, because None does, and in some places `pass` does not,
        like
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


class Break(LabeledResultException):
    """
    a substitute for the break statement.

    This breaks out of While and For, by raising itself.
    >>> try:
    ...     Break()
    ...     assert False
    ... except Exception as ex:
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


class Continue(LabeledException):
    """
    a substitute for the continue statement.

    This continues a While or For, by raising self.
    >>> try:
    ...     Continue()
    ...     assert False
    ... except Exception as ex:
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
    Cascading if. The args are paired. Pairs are checked in order.
    If the left evaluates to true, the right is called. If all are false,
    Else is called.
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

    Recall that `a if b else c` is already an expression. These can be nested,
    but Elif may be easier to use for deep nesting.
    """
    assert len(thunks) % 2 == 0
    assert set(Else.keys()) <= frozenset(['Else'])
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
            elif type(ex.__init__) != type(Exception().__init__):  # class or instance?
                ex = ex()
            ex.__context__ = None
        raise ex
    raise
""")
    Raise.__doc__ = _doc
    del _doc


class Return(LabeledResultException):
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
    assert set(ElseFinally.keys()) <= frozenset(['Else', 'Finally'])
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


class Atom(object):
    """
    a locked boxed mutable variable, assignable in expressions.

    >>> spam = Atom('eggs')  # initial value (required)
    >>> spam
    Atom('eggs')

    unbox with .e (element) attr
    >>> spam.e
    'eggs'

    get() also works
    >>> spam.get()
    'eggs'

    can assign using .set(), either directly or by modifying current
    value with an operator, which is atomic.
    >>> from operator import sub
    >>> spam.set(44)
    44
    >>> spam.set(2, sub)  # actually any binary callable will work
    42
    >>> spam.set('eggs')
    'eggs'
    >>> spam.e
    'eggs'
    """

    def __init__(self, e):

        from threading import Lock

        lock = Lock()

        e = [e]

        def var_set(new, oper=None):
            """
            sets Atom's element. Optionally augment assignments with oper.
            set() is locked for thread safety, however direct access to
            .e is not locked, so foo.set(1, operator.add) is an atomic
            increment, but foo.set(foo.e + 1) is not.

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
                if oper:
                    e[0] = oper(e[0], new)
                else:
                    e[0] = new
                res = e[0]
            return res

        self.set = var_set
        self.get = lambda: e[0]  # readonly

    @property
    def e(self):
        return self.get()

    @e.setter
    def e(self, new):
        raise AttributeError("Use .set() to assign to a Atom, not .e = ...")

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
    ...     Print(spam.set(-1,add)))
    3
    2
    1
    0
    >>> spam.set(1)
    1
    >>> While(spam.get, lambda:
    ...   Print(spam.set(-1,add)),
    ... Else=lambda:
    ...   'done')
    0
    'done'
    >>> While(lambda: True, lambda:
    ...   Print(spam.set(1,add)) if spam.e < 2 else Break(),
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


    Unlike with, With supports only one guard, but as pointed out in the
    documentation, a with statement with multiple guards is equivalent to
    nested withs anyway, so

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


def let(body, args=(), kwargs=Empty, label=None):
    """
    immediately calls body.
    can catch a Return exception and returns its result.
    Used for expression-local variables and closures.
    This can fill in for some uses of the '=' assignment statements.
    >>> let(lambda x=4,y=3: x+y)
    7
    >>> let(lambda x='*'*7: x+'spam'+x)
    '*******spam*******'

    Default parameters don't support everything assign statements do.
    Unpack tuples using the args key instead.
    >>> triple = (1,2,3)
    >>> let(args=triple, body=lambda a,b,c: Print(c,b,a))
    3 2 1

    Unpack dicts using the kwargs key.
    >>> association = {'foo': 2}
    >>> let(kwargs=association, body=lambda foo: foo)
    2
    """
    try:
        return body(*args, **kwargs)
    except Return as r:
        r.handle(label)
        return r.result


def do(*body):
    """
    returns its last argument.
    >>> do(1,1+1,1+1+1)
    3

    To keep all arguments, use a tuple instead of a do.
    >>> (1,1+1,1+1+1)
    (1, 2, 3)

    do is used to combine several expressions into one by sequencing,
    for side-effects. Python guarantees sequential evaluation of arguments:
    https://docs.python.org/3/reference/expressions.html#evaluation-order
    >>> spam = do(Print('side'),Print('effect'),'suppressed',42)
    side
    effect
    >>> spam
    42
    """
    return body[-1] if body else Empty


__all__ = [e for e in globals().keys() if not e.startswith('_') if e not in _exclude_from__all__]
