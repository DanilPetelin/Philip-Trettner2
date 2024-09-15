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

supports import *

These correspond to Python statements, but are usable as expressions,
including (for example) in eval and lambda. As higher-order functions,
these substitutes can be composed, curried, returned, and passed as
arguments, unlike the statements they emulate, which must stand alone.

Despite convention for Python function names, the functions Assert,
Break, Continue, Elif/Else, For/Else, Import/From, Pass, Raise/From,
let/Return, Try/Except/Else/Finally, With, and While/Else are
capitalized to avoid conflicts with the original Python keywords.

The functional style works better with statements replaced by
expressions, but be aware that some statement replacements (like For)
always return None and must act through side effects.

Functions for the keywords `False`, `None`, `True`, `and`, `if`,
`in`, `is`, `lambda`, `not`, `or`, and `yield` are not provided because
they are already expressions. Similarly for most operators.

Due to optimizations for Python locals, direct local and nonlocal
assignment statements cannot be emulated as functions, but Var can
substitute for nonlocals in many cases. For the same reason, direct
local and nonlocal `del` statements are not supported, but `del` is
partially supported with delitem. (delattr() is already a builtin)

The augmented assignment statements, += -= *= /= %= &= |= ^= <<= >>= **=
//=, are partially supported with the operator module combined with
assign_attr(), assign_item(), and Var.set().

Assignment statements, =, are partially supported with let(), and by
using assign_attr(), assign_item(), and Var.set()
without the optional operator.

Use the metaclass directly to substitute for `class`, for example
  X = type('X', (A, B), dict(a=1))
is the same as
  class X(A, B): a = 1

A substitute for `def` is not provided here, but `lambda` is a viable
alternative now that most statements are available as expressions.
Multiple sequential expressions are available in lambda via progn.
Multiple exits are available via let/progn/Return()

See stack.Def and macros.Lx for two alternative `def` substitutes.
"""
from __future__ import absolute_import, division, print_function
# To avoid circular dependencies in this package,
# statement.py shall depend only on the core.py module


from drython.core import entuple, efset, partition, Empty

_exclude_from__all__ = set(globals().keys())
__test__ = {}

def _private():
    class PassType:
        """
        A no-operation empty thunk; returns None.
        Pass can substitute for `pass` where a statement substitution requires
        a thunk. (A thunk is a 0-arg func.) Pass() also works anywhere `pass`
        does, because None does, and in some places `pass` does not,
        like
        >>> (lambda: Pass())()
        """

        def __call__(self):
            return None

        def __repr__(self):
            return 'Pass'

    __test__[PassType.__name__] = PassType.__doc__

    return PassType()


Pass = _private()
del _private


# noinspection PyPep8Naming
def Assert(boolean):
    """
    Wraps an assert statement.
    >>> Assert(1+1 == 2)
    >>> Assert(1+1 == 7)
    Traceback (most recent call last):
      File "<pyshell#x>", line 1, in <module>
        Assert(False)
      File "statement.py", line 41, in Assert
        assert boolean
    AssertionError

    Unlike naked assert statements,
    Assert() is allowed anywhere expressions are.
    When assert is disabled, Assert() simply returns None.
    """
    assert boolean


def _private():
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

    global Break

    class Break(LabeledException):
        """
        a substitute for the break statement.
        This breaks out of While and For, by raising self.
        >>> try:
        ...     Break()
        ...     assert False
        ... except Exception as ex:
        ...     print(repr(ex))
        Break()

        Unlike while and for, While and For support labels
        to break targeted outer loops from within inner loops.

        >>> For(range(4), lambda i:
        ...     For(range(4), lambda j:
        ...         (Break() if i==j else Pass(),
        ...          print(i, j))))
        1 0
        2 0
        2 1
        3 0
        3 1
        3 2
        >>> For(range(1, 4), lambda i:
        ...     For(range(4), lambda j:
        ...         (Break("outer") if i==j else Pass(),
        ...          print(i, j))),
        ...     label="outer")
        1 0
        """

    global Continue

    class Continue(LabeledException):
        """
        a substitute for the continue statement.
        This continues a While or For, by raising self.
        >>> try:
        ...     Continue()
        ...     assert False
        ... except Exception as ex:
        ...     print(repr(ex))
        Continue()
        
        Unlike while and for, While and For support labels
        to continue a targeted outer loop from within inner loops.
        If the label exists, but doesn't match, the Continue is
        raised again.
        
        >>> For(range(4), lambda i:
        ...     For(range(4), lambda j:
        ...         (Continue("outer") if i==j else Pass(),
        ...          print(i,j))),
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
        ...          print(i,j))))
        0 1
        0 2
        1 0
        1 2
        2 0
        2 1
        """

    global Return

    class Return(LabeledException):
        """
        Aborts an expression early, but keeps a result value.
        Must be wrapped in a let().
        >>> let(lambda: progn(
        ...  1,
        ...  2,
        ...  3,))
        3
        >>> let(lambda: progn(
        ...  1,
        ...  Return(2),
        ...  3,))
        2

        Like `return` an empty Return() returns None.
        >>> let(lambda: progn(
        ...  1,
        ...  Return(),
        ...  3,))

        Like `return`, multiple Return values result in a tuple.
        >>> let(lambda: progn(
        ...  1,
        ...  Return(1,2,3),
        ...  3,))
        (1, 2, 3)

        Can return through multiple let()s using a label.
        >>> let(label='outer', body=lambda a=1,d=4: progn(
        ...   let(lambda b=42,c=3: progn(
        ...     a,
        ...     Return(b,label='outer'),
        ...     c,)),
        ...   d,))
        42
        """

        def __init__(self, result=None, *results, **label):
            assert set(label.keys()) <= efset('label')
            if results:
                self.result = (result,) + results
            else:
                self.result = result
            LabeledException.__init__(self, label.get('label', None))


# IntelliJ requires individual top-level assignments to detect globals
Break = None
Continue = None
Return = None

_private()  # Creates Break, Continue, Return
del _private

# a Smalltalk-like implementation of Lisp's COND.
# noinspection PyPep8Naming
def Elif(*thunks, **Else):
    """
    Cascading if. The args are paired. Pairs are checked in order.
    If the head evaluates to true, the second is called. If no heads are true,
    Else is called.
    >>> Elif()  # Else defaults to Pass
    >>> Elif(Pass, lambda:1)  # Pass() is None
    >>> Elif(lambda:True, lambda:1)
    1
    >>> Elif(Pass, lambda:print('a'),
    ...      Else=lambda:print('b'))
    b
    >>> Elif(Pass, lambda:print('a'),
    ...      Pass, lambda:print('b'))
    >>> Elif(lambda:True, lambda:print('a'),
    ...      Pass, lambda:print('b'))
    a
    >>> Elif(Pass, lambda:1,
    ...      lambda:print('a'), lambda:2,  # head has to be checked.
    ...      Pass, lambda:3,
    ...      Else=lambda:4)
    a
    4
    >>> Elif(lambda:print('a'), lambda:2,  # print returns None
    ...      lambda:3, lambda:4,  # nonzero is truthy
    ...      lambda:print('skipped?'), lambda:print('skipped?'),
    ...      Else=lambda:print('skipped?'))
    a
    4

    Recall that `if` is already an expression. These can be nested,
    but Elif may be easier to use for deep nesting.
    """
    assert len(thunks) % 2 == 0
    assert set(Else.keys()) <= frozenset(['Else'])
    for predicate, thunk in zip(*2 * (iter(thunks),)):
        if predicate():
            return thunk()
    return Else.get('Else', Pass)()



# noinspection PyPep8Naming,PyShadowingNames
def For(iterable, func, Else=Pass, label=None):
    """
    Unpacks each element from iterable and applies func to it.
    Unlike map() (and like `for`) For is strict, not lazy;
    it is not a generator and evaluation begins immediately.
    The element is not unpacked for a func with a single
    positional arg, which makes For behave more like `for`.

    func must be 1-argument
    >>> For({'a':'A'}.items(), lambda pair:
    ...         print(pair))
    ('a', 'A')

    Use the star function for unpacking
    >>> from drython.core import star
    >>> For({'key':'value'}.items(), star(lambda k, v:
    ...         (print(k),
    ...          print(v))))
    key
    value

    For can nest
    >>> For('ab', lambda i:
    ...     For('AB', lambda j:
    ...         print(i, j)))
    a A
    a B
    b A
    b B

    For also has an optional Else thunk, and supports labeled
    Break and Continue.
    >>> For(range(99), lambda i:
    ...       print(i) if i<4 else Break(),
    ...     Else=lambda:
    ...       print("not found"))
    0
    1
    2
    3
    >>> For(range(2), lambda i:
    ...       print(i) if i<4 else Break(),
    ...     Else=lambda:
    ...       print("not found"))
    0
    1
    not found
    """
    try:
        for e in iterable:
            try:
                func(e)
            except Continue as c:
                c.handle(label)
    except Break as b:
        b.handle(label)
        return  # skip Else() on Break
    Else()


def _private():
    from importlib import import_module

    global Import

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
        >>> abc = Import('collections.abc')  # import collections.abc as abc
        >>> hasattr(abc,'Set')
        True

        # from collections.abc import enset
        >>> Set = Import('Set', From='collections')
        >>> Set == abc.Set
        True

        # from .stack import Stack, op
        >>> Stack, op = Import('Stack', 'op', From='.stack', package='drython')
        >>> Stack(1,2,op(sub)).peek()
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


Import = None
_private()
del _private


def Raise(ex=None, From=Ellipsis):
    if ex:
        if From is not Ellipsis:
            if ex.__class__ == type:
                ex = ex()
            # raise ex from From
            ex.__cause__ = From
        raise ex
    raise


import sys
if sys.version_info[0] >= 3:
    exec("""\
def Raise(ex=None, From=Ellipsis):
    if ex:
        if From is not Ellipsis:
            raise ex from From
        raise ex
    raise
""")
del sys


# _private()
# del _private

Raise.__doc__ = \
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
    ...     print('zde!')
    ...     Raise()
    Traceback (most recent call last):
        ...
    ZeroDivisionError: division by zero

    raise ... from is also supported, even experimentally in 2.7
    >>> Raise(ZeroDivisionError, From=None)
    Traceback (most recent call last):
        ...
    ZeroDivisionError

    >>> try:
    ...     Raise(ZeroDivisionError, From=StopIteration())
    ... except ZeroDivisionError as zde:
    ...     print(zde.__cause__)
    """

def Try(thunk, *Except, **ElseFinally):
    """
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
    ...     ZeroDivisionError, lambda zdr: progn(
    ...         print(zdr),
    ...         'returns: take a limit!',),
    ...     Finally=lambda:
    ...         print('finally!'),
    ...     Else=lambda:
    ...         print('returns: or else!'))
    division by zero
    finally!
    'returns: take a limit!'

    Try() evaluates to the else part if provided.
    >>> Try(lambda:
    ...         0/1,  # allowed
    ...     ZeroDivisionError, lambda zdr: progn(
    ...         print(zdr),
    ...         'take a limit!',),
    ...     Finally=lambda:
    ...         print('finally!'),
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
    ...         print('by ZeroDivisionError'),
    ...     Exception, lambda x:
    ...         print('by Exception'),)
    by ZeroDivisionError
    >>> Try(lambda:
    ...         1/0,
    ...     Exception, lambda x:
    ...         print('by Exception'),
    ...     ZeroDivisionError, lambda zdr:
    ...         print('by ZeroDivisionError'),)
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


# TODO: doctest While, labeled/unlabeled break/continue
# noinspection PyPep8Naming
def While(predicate, thunk, label=None, Else=Pass):
    """
    >>> from operator import add
    >>> spam = Var(4)
    >>> While(lambda:spam.e,lambda:print(spam.set(-1,add)))
    3
    2
    1
    0
    >>> spam.set(1)
    1
    >>> While(lambda: spam.e,
    ...   lambda: print(spam.set(-1,add)),
    ...   Else=lambda: print('done'))
    0
    done
    >>> While(lambda: True,
    ...   lambda: print(spam.set(1,add)) if spam.e < 2 else Break(),
    ...   Else=lambda: print('not possible'))
    1
    2

    """

    try:
        while predicate():
            try:
                thunk()
            except Continue as c:
                c.handle(label)
    except Break as b:
        b.handle(label)
        return
    Else()


class Var:
    """
    a boxed mutable variable, which can be assigned to inside
    expressions.
    >>> spam = Var('eggs')  # initial value (required)
    >>> spam
    Var('eggs')

    unbox with .e (element) attr
    >>> spam.e
    'eggs'

    can assign using .set(), either directly or by modifying current
    value with an operator
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
            sets Var's element. Optionally augment assignments with oper.
            set() is locked for thread safety, however direct access to
            .e is not locked, so foo.set(1, operator.add) is a thread-
            safe increment, but foo.set(foo.e + 1) is not.
            The return value is set inside the lock, to make it
            consistent with the update.
            """
            # Threading with primitive locks is generally a bad idea.
            # since race conditions are impossible to test properly.
            # The only testing alternative is mathematical proof.
            # Best keep this block as simple as possible.
            # Var is a useful alternative to primitive locks
            # in many cases.
            with lock:
                if oper:
                    e[0] = oper(e[0], new)
                else:
                    e[0] = new
                res = e[0]
            return res

        self.set = var_set
        self._get = lambda: e[0]  # readonly

    @property
    def e(self):
        return self._get()

    @e.setter
    def e(self, new):
        raise AttributeError("Use .set() to assign to a Var, not .e = ...")

    def __repr__(self):
        return 'Var(%s)' % repr(self.e)


# noinspection PyPep8Naming
def With(guard, func):
    """
    wraps a with statement; applies func to the result of guard in the
    context of guard.

    Unlike with, With supports only one guard, but as pointed out in the
    documentation, a with statement with multiple guards is equivalent to
    nested withs anyway.

    with A() as a, B() as b:
            suite

    is equivalent to

    with A() as a:
        with B() as b:
            suite

    Thus, nested Withs will work the same way:
    With(A,lambda a:
        With(B,lambda b:
            progn(...)))
    """
    # TODO: doctest With
    with guard() as g:
        return func(g)


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
    >>> progn(delitem(globals(), 'spam'), None)
    >>> try:
    ...    spam
    ...    assert False
    ... except NameError as ne:
    ...    print(repr(ne))
    NameError("name 'spam' is not defined",)
    """
    del obj[index]
    return obj





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
    >>> let(args=triple, body=lambda a,b,c: print(c,b,a))
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


def progn(*body):
    """
    returns its last argument.
    >>> progn(1,1+1,1+1+1)
    3

    To keep all arguments, use a tuple instead of a progn.
    >>> (1,1+1,1+1+1)
    (1, 2, 3)

    progn is used to combine several expressions into one by sequencing,
    for side-effects. Python guarantees sequential evaluation of arguments:
    https://docs.python.org/3/reference/expressions.html#evaluation-order
    >>> spam = progn(print('side'),print('effect'),'suppressed',42)
    side
    effect
    >>> spam
    42
    """
    return body[-1]





__all__ = [e for e in globals().keys() if not e.startswith('_') if e not in _exclude_from__all__]


