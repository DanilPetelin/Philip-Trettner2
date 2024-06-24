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

Despite convention for Python function names, the functions Assert,
Break, Continue, Elif/Else, For/Else, Import/From, Pass, Raise,
Try/Except/Else/Finally, With, and While/Else are capitalized to avoid
conflicts with the original Python keywords.

The functional style works better with statements replaced by
expressions, but be aware that some statement replacements (like For)
always return None and must act through side effects.

Functions for the keywords `False`, `None`, `True`, `and`, `as`, `if`,
`in`, `is`, `lambda`, `not`, `or`, and `yield` are not provided because
they are already expressions. Similarly for most operators.

Due to optimizations for Python locals, direct local and nonlocal
assignment statements cannot be emulated as functions, but Var can
substitute for nonlocals in many cases. For the same reason, direct
local and nonlocal `del` statements are not supported, but `del` is
partially supported with delitem. (delattr() is already a builtin)

The augmented assignment statements, += -= *= /= %= &= |= ^= <<= >>= **=
//=, are partially supported with the operator module combined with
assign_attr(), assign_item(), and Var.assign().

Assignment statements, =, are partially supported with let(), and by
using assign_attr(), assign_item(), and Var.assign()
without the optional operator.

Use the metaclass directly to substitute for `class`
  X = type('X', (A, B), dict(a=1))
is the same as
  class X(A, B): a = 1

A substitute for `def` is not provided, but `lambda` is a viable
alternative now that most statements are available as expressions.
Multiple sequential expressions are available in lambda via progn.
Multiple exits are available via let/progn/Return()
"""


__author__ = 'Matthew Egan Odendahl'


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
    Assert is allowed anywhere expressions are.
    But as an expression returning a value, it
    cannot simply be removed. Add the line
      Assert = None
    at the top of your file to turn off Assert.
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

    # noinspection PyShadowingNames
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

    # noinspection PyShadowingNames
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
        def __init__(self, result=None, *results, label=None):
            if results:
               self.result = (result,)+results
            else:
                self.result = result
            super().__init__(label=label)

    return Break, Continue, Return
# IntelliJ requires individual assignments for globals to show up in Structure tab
Break = None
Continue = None
Return = None
Break, Continue, Return = _private()
del _private

# a Smalltalk-like implementation of Lisp's COND.
# noinspection PyPep8Naming
def Elif(*thunks, Else=Pass):
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
    'a'
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
    4

    Recall that `if` is already an expression. These can be nested,
    but Elif may be easier to use for deep nesting.
    """
    assert len(thunks) % 2 == 0
    for predicate, thunk in zip(*2 * (iter(thunks),)):
        if predicate():
            return thunk()
    return Else()


def _private():
    from inspect import signature
    from inspect import Parameter

    _positional = (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)

    # noinspection PyPep8Naming,PyShadowingNames
    def For(iterable, func, Else=Pass, *, label=None):
        """
        Unpacks each element from iterable and applies func to it.
        Unlike map() (and like `for`) For is strict, not lazy;
        it is not a generator and evaluation begins immediately.
        The element is not unpacked for a func with a single
        positional arg, which makes For behave more like `for`.

        With normal unpacking
        >>> For({'a':'A'}.items(), lambda k, v:
        ...         (print(k),
        ...          print(v)))
        a
        A
        
        Without unpacking for a 1-arg func
        >>> For({'a':'A'}.items(), lambda pair:
        ...         print(pair))
        ('a', 'A')

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
        params = signature(func).parameters
        try:
            # check for 1-arg positional func
            if len(params) == 1 and next(iter(params.items()))[1].kind in _positional:
                for e in iterable:
                    try:
                        func(e)  # doesn't unpack
                    except Continue as c:
                        c.handle(label)
            else:
                for e in iterable:
                    try:
                        func(*e)  # note the *
                    except Continue as c:
                        c.handle(label)
        except Break as b:
            b.handle(label)
            return  # skip Else() on Break
        Else()

    return For


For = _private()
del _private


# TODO: doctest python3 relative imports?
def _private():
    from importlib import import_module

    # noinspection PyPep8Naming,PyShadowingNames
    def Import(item, package=None, *, From=None):
        if From:
            return getattr(import_module(From, package), item)
        else:
            return import_module(item, package)

    return Import


Import = _private()
del _private


# noinspection PyPep8Naming
def Raise(ex):
    """
    raises an exception.
    Unlike a naked raise statement, this works anywhere
    an expression is allowed, which has some unexpected uses:
    >>> from itertools import count
    >>> list(i if i<10 else Raise(StopIteration) for i in count())
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    """
    raise ex

# TODO: doctest Try
# noinspection PyPep8Naming
def Try(thunk, *Except, Else=None, Finally=Pass):
    try:
        res = thunk()
    except BaseException as ex:
        for k in Except:
            if(isinstance(ex,k)):
                return Except[k](ex)
        else:
            raise ex
    else:
        if Else:
            res = Else()
    finally:
        Finally()
    return res

# TODO: doctest While, labeled/unlabeled break/continue
# noinspection PyPep8Naming
def While(predicate, thunk, label=None, *, Else=Pass):
    """
    >>> from operator import add
    >>> spam = Var(4)
    >>> While(lambda:spam.e,lambda:print(spam.assign(-1,add)))
    Var(3)
    Var(2)
    Var(1)
    Var(0)
    >>> spam.assign(1)
    Var(1)
    >>> While(lambda: spam.e,
    ...   lambda: print(spam.assign(-1,add)),
    ...   Else=lambda: print('done'))
    Var(0)
    done
    >>> While(lambda: True,
    ...   lambda: print(spam.assign(1,add).e) if spam.e < 2 else Break(),
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
    """ a boxed mutable variable, which can be assigned to inside expressions. """

    def __init__(self, e):
        """
        >>> spam = Var('eggs')
        >>> spam
        Var('eggs')
        >>> spam.e
        'eggs'
        """
        self.e = e

    def assign(self, e, oper=None):
        """
        sets Var's element. Optionally augment assignments with oper.
        >>> from operator import add
        >>> spam = Var(40)
        >>> spam.assign(2, add)
        Var(42)
        >>> spam.assign('eggs')
        Var('eggs')
        """
        if oper:
            self.e = oper(self.e, e)
        else:
            self.e = e
        return self

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
    returns obj for chaining.

    does a simple replacement if no operator is specified

    usually used in combination with the operator module,
    though any appropriate binary function may be used.
    >>> from operator import add
    >>> spam = lambda:None
    >>> assign_attr(assign_attr(spam,'eggs',40),'eggs',2,add).eggs
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


def let(body, *, args=(), kwargs={}, label=None):
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
        return body(*args,**kwargs)
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
    for side-effects. Python guarantees sequential evaluation of arguments.
    >>> spam = progn(print('side'),print('effect'),'suppressed',42)
    side
    effect
    >>> spam
    42
    """
    return body[-1]


if __name__ == "__main__": import doctest; doctest.testmod()

