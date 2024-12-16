# Copyright 2016 Matthew Egan Odendahl
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
This module exports a set of expression replacement functions.

`In` substitutes for generator expressions (thus comprehensions also).

`generator` substitutes for `yield from` and `yield` in cases where
it would be incompatible with the statement module.

Operator functions are already available in Python's included
`operator` module, so they are not provided here.

Unlike statements, expressions already work in lambdas and eval,
so why replace them too?

Besides being easier to use with higher-order functions, the stack
and s-expression modules work primarily with function calls, so these
substitutes have uses in metaprogramming. In many cases you can use
expressions directly anyway, or convert a non-call expression to a
call with a lambda, but sometimes you need to manipulate the code of
the expression itself, in which case it must be made of calls to
begin with.

The simple case of addition illustrates the three styles.
>>> from core import identity
>>> from s_expression import S
>>> from operator import add

When used directly it's like a constant as far as S is concerned.
>>> S(identity,1+2)()
3

Wrap in lambda and you can change the arguments
>>> S(lambda x,y:x+y,1,2)()
3

function call version is more natural for s-expressions
>>> S(add,1,2)()
3

A more advanced case with generator expressions.
>>> from core import entuple; from macro import L1

Direct use acts like a constant
>>> S(identity,[(x,y) for x in (1,2) for y in 'abc'])()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

lambda version is adjustable with arguments.
>>> S(lambda z:[(x,y) for x in (1,2) for y in z],'abc')()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]
>>> S(list,  # function call version using expression.In
...   S(In,(1,2),S(L1,S.x,
...       S(In,'abc',S(L1,S.y,
...           S(entuple,S(entuple,S.x,S.y)))))))()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

Why use the function call version when it's so much harder? Besides
the new `whilst` feature, the main advantage here is that you can
simplify it with a macro.
>>> from s_expression import macro
>>> @macro
... def genx(expr,*specs):
...     if specs:
...         return S(In,specs[1],S(L1,specs[0],S(genx,expr,*specs[2:])))
...     else:
...         return S(entuple,expr)

Now we've got generator s-expressions with arguments in familiar
Python order.
>>> S(list,
...   S(genx, S(entuple, S.x, S.y), S.x, (1, 2), S.y, 'abc'))()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

A more advanced macro could include Python's other features like `if`
filters and unpacking. But more importantly, since you can
metaprogram this, you can add new features in the macro that raw
Python lacks, like whilst.
"""

import threading
import weakref
from functools import wraps
import sys

from drython.statement import Atom

if sys.version_info[0] == 2:
    import Queue as Q
else:
    import queue as Q


def In(target_list, comp_lambda):
    """
    Generator expressions made of function calls. Similar to the list
    monad in functional languages.

    The lexical scoping rules for lambda require the variable term to
    be last--unlike Python's comprehensions which put that first. To
    enable nesting of In, the comp_lambda must always return an
    iterable, even for the innermost In.

    `In` is a generator expression substitute, but it can also
    substitute for list comprehensions by wrapping with list(),
    as in Python:
    >>> [c+d for c in 'abc' for d in 'xyz']  # list comprehension
    ['ax', 'ay', 'az', 'bx', 'by', 'bz', 'cx', 'cy', 'cz']

    generator expression acting as the above list comprehension
    >>> list(c+d for c in 'abc' for d in 'xyz')
    ['ax', 'ay', 'az', 'bx', 'by', 'bz', 'cx', 'cy', 'cz']

    Two `In` functions acting as the above generator expression
    acting as the list comprehension above that.
    >>> list(In('abc', lambda c:
    ...          In('xyz', lambda d:
    ...              (c+d,)  # comp_lambda ALWAYS returns an iterable
    ... )))
    ['ax', 'ay', 'az', 'bx', 'by', 'bz', 'cx', 'cy', 'cz']

    dictionary and set comprehensions work similarly:
    >>> ({'a', 'b', 'c'} ==
    ...  {c for c in 'abc'} ==
    ...  set(c for c in 'abc') ==
    ...  set(In('abc', lambda c: (c,))))
    True
    >>> ({'one': 1} ==
    ...  {k:v for k,v in [('one',1)]} ==
    ...  dict((k,v) for k,v in [('one',1)]))
    True

    The dict translation is a bit trickier. Note the tuple-in-tuple
    ((k,v),) and star(), similar to statement.For()
    >>> from drython.core import star
    >>> dict(In([('one',1)], star(lambda k, v: ((k,v),) )))
    {'one': 1}
    """
    # The double for/yield is a flatten. I would have used
    # return itertools.chain.from_iterable(map(comp_lambda,target_list))
    # but whilst raises StopIteration, and chain can't handle it.
    for target in target_list:
        for x in comp_lambda(target):
            yield x


# the name "While" was already taken.
def whilst(b, x):
    """
    Like using a takewhile in comprehensions. It aborts the remainder
    of the iterable.

    But unlike a StopIteration, the remaining other loops continue.
    >>> from itertools import takewhile
    >>> [(x,y) for x in takewhile(lambda x:x<3,range(10))
    ...  for y in takewhile(lambda y:y<2,range(10))]
    [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]
    >>> list(In(range(10),lambda x:
    ...     whilst(x<3, In(range(10), lambda y:
    ...         whilst(y<2,((x,y),))))))
    [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]

    Notice that y has to be bound twice in the
    list-comprehension/takewhile version, but not using In/whilst.
    >>> [x+y for x in 'abc' for y in takewhile(lambda y: x!=y,'zabc')]
    ['az', 'bz', 'ba', 'cz', 'ca', 'cb']
    >>> list(In('abc',lambda x:
    ...          In('zabc',lambda y:
    ...              whilst(x!=y, (x+y,) ))))
    ['az', 'bz', 'ba', 'cz', 'ca', 'cb']

    This is different than if (or `when` inside `In`), which keeps
    checking
    >>> [x+y for x in 'abc' for y in 'zabc' if x!=y]
    ['az', 'ab', 'ac', 'bz', 'ba', 'bc', 'cz', 'ca', 'cb']
    """
    if b:
        return x
    else:
        raise StopIteration


def when(b, x):
    """
    Like Python's `if` in comprehensions.

    Named for Clojure's :when keyword, which has the same function in
    its comprehensions.

    >>> list(x+y for x in 'zazbzcz' if x!='z' for y in 'abc' if x!=y)
    ['ab', 'ac', 'ba', 'bc', 'ca', 'cb']
    >>> list(In('zazbzcz', lambda x:
    ...     when(x!='z', In('abc', lambda y:
    ...        when(x!=y, (x+y,) )))))
    ['ab', 'ac', 'ba', 'bc', 'ca', 'cb']
    """
    return x if b else ()


def generator(f):
    """
    Coroutine expression decorator

    The generator decorator injects the yield point function as the
    first argument, conventionally named `Yield`. Because it's named,
    it can cut though nested generators without `yield from`
    >>> @generator
    ... def foo(Yield):
    ...     Yield(1)
    ...     def subgen():
    ...         Yield(2)
    ...     subgen()
    ...     subgen()
    >>> list(foo())
    [1, 2, 2]

    The generator decorator can also do coroutines like the following.
    >>> def echo():
    ...     reply = yield
    ...     while True:
    ...         reply = yield reply
    >>> my_echo = echo()
    >>> my_echo.send(None)
    >>> my_echo.send(1)
    1
    >>> my_echo.send(2)
    2

    The @generator version of the above works the same way.
    >>> @generator
    ... def echo2(Yield):
    ...     reply = Yield()
    ...     while True:
    ...         reply = Yield(reply)
    >>> my_echo2 = echo2()
    >>> my_echo2.send(None)
    >>> my_echo2.send(1)
    1
    >>> my_echo2.send(2)
    2

    Now you can make coroutines out of pure expressions with the help
    of the statement module. This is the expression-only equivalent
    of the generator above.
    >>> from drython.statement import While,let,Atom,loop
    >>> echo3 = generator(lambda Yield:
    ...     let(lambda reply=Atom(Yield()):
    ...         While(lambda:True, lambda:
    ...             reply.swap(Yield))))()
    >>> echo3.send(None)
    >>> echo3.send(1)
    1
    >>> echo3.send(2)
    2

    and the more concise version using loop.
    >>> echo4 = generator(lambda Yield:
    ...     loop(lambda recur, reply=Yield():
    ...         recur(Yield(reply)))())()
    >>> echo4.send(None)
    >>> echo4.send(1)
    1
    >>> echo4.send(2)
    2
    """
    # Just for id. This can be shared between instances.
    raise_signal = object()
    @wraps(f)
    def wrapper(*args, **kwargs):
        yield_q = Q.Queue(maxsize=2)
        send_q = Q.Queue(maxsize=2)

        # takes from send_q
        def Yield(arg=None):
            yield_q.put(arg)
            res = send_q.get()
            if res is raise_signal:
                raise send_q.get()
            return res

        def run():
            try:
                f(Yield, *args, **kwargs)
                raise StopIteration
            except BaseException as be:
                yield_q.put_nowait(raise_signal)
                yield_q.put_nowait(be)


        t = threading.Thread(target=run,name='@generator')
        t.daemon = True
        _terminator = Atom(None)

        def genr():
            # kills zombie thread when this is gc'd
            thread_terminator = _terminator

            t.start()

            # takes from yield_q
            while True:
                yielded = yield_q.get()
                if yielded is raise_signal:
                    raise yield_q.get()
                try:
                    sent = (yield yielded)
                except BaseException as be:
                    send_q.put(raise_signal)
                    send_q.put(be)
                else:
                    send_q.put(sent)

        the_generator = genr()

        def terminate(ref):
            send_q.put_nowait(raise_signal)
            send_q.put_nowait(GeneratorExit)
        _terminator.reset(weakref.ref(the_generator, terminate))

        return the_generator

    return wrapper

