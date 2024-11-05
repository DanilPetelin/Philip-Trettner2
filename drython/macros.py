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

# TODO: docstring macros.py
from __future__ import absolute_import, division
from collections import MutableMapping
from functools import wraps
from itertools import chain

from drython.statement import Print
from drython.core import partition, identity, entuple, SEvaluable, interleave, apply
from drython.s_expression import S, macro, s_eval_in_scope, flatten_sexpr, gensym, Symbol
from drython.statement import Elif, do, Raise

__test__ = {}

# macros.py depends on core.py, s_expression.py, and statement.py
# macros.py does not currently require stack.py
@macro
def s_eval(body):
    return SEval(body)


class SEval(SEvaluable):
    def __init__(self, body):
        self.body = body

    def s_eval(self, scope):
        if hasattr(self.body, '_s_evaluable_') and isinstance(self.body, SEvaluable):
            res = self.body.s_eval(scope)
            if hasattr(self.body, '_s_evaluable_') and isinstance(res, SEvaluable):
                return res.s_eval(scope)
            return res
        return self.body


class ScopeError(NameError, KeyError):
    pass


class Scope(MutableMapping):
    def __len__(self):
        return len(self.vars)

    def __iter__(self):
        return iter(self.vars)

    def __init__(self, parent, local=None):
        assert all(isinstance(x, str) for x in parent.keys())
        self.parent = parent
        self.vars = local or {}
        assert all(isinstance(x, str) for x in self.vars.keys())
        self.nonlocals = set()

    def __getitem__(self, name):
        try:
            return self.vars[name]
        except KeyError:
            try:
                return self.parent[name]
            except KeyError as ke:
                Raise(ScopeError('name %s not found in Scope' % repr(name)), From=ke)

    def __setitem__(self, name, val):
        assert isinstance(name, str)
        if name in self.nonlocals:
            try:
                self.parent[name] = val
            except KeyError as ke:
                Raise(ScopeError('nonlocal %s not found' % repr(name)), From=ke)
        else:
            self.vars[name] = val

    def __delitem__(self, name):
        if name in self.nonlocals:
            try:
                del self.parent[name]
            except KeyError as ke:
                Raise(ScopeError('nonlocal %s not found' % repr(name)), From=ke)

    def __repr__(self):
        return ('Scope(local={1}, parent={0})'.format(self.parent, self.vars)
                + ('.Nonlocal({0})'.format(self.nonlocals) if self.nonlocals else ''))

    # noinspection PyPep8Naming
    def Nonlocal(self, *names):
        self.nonlocals |= set(names)
        return self


class ScopeGetter(SEvaluable):
    def s_eval(self, scope):
        return scope


@macro
def scope():
    return ScopeGetter()


class SSetQ(SEvaluable):
    def __init__(self, pairs):
        assert len(pairs) % 2 == 0
        self.pairs = partition(pairs)

    def s_eval(self, scope):
        for k, v in self.pairs:
            scope[k] = s_eval_in_scope(v, scope)


@macro
def setq(*pairs):
    """
    >>> from operator import add
    >>> S(setq,
    ...   S.spam,1,
    ...   S.eggs,S(add,
    ...            1,
    ...            S.spam)).s_eval(globals())
    >>> spam
    1
    >>> eggs
    2
    """
    return SSetQ(pairs)


class SLambda(SEvaluable):
    def __init__(self, body, required=(), optional=(), star=None, stars=None):
        def _s_eval_helper(scope):
            assert len(optional) % 2 == 0
            pairs = tuple(partition(optional))
            keys, defaults = zip(*pairs) if pairs else ((), ())
            defaults = S(entuple, *defaults).s_eval(scope)

            _sentinel = object()
            func = eval(
                '''lambda {0}:__builtins__['locals']()'''.format(
                    ','.join(
                        ((','.join(required),) if required else ())
                        + ((','.join(
                            map('{0}=_'.format, keys)),) if keys else ())
                        + (('*%s' % star,) if star else ())
                        + (('**' + stars,) if stars else ()))),
                dict(_=_sentinel, __builtins__=dict(locals=locals)))

            @wraps(func)
            def Lambda(*args, **kwargs):
                bindings = dict(zip(keys, defaults))
                for k, v in func(*args, **kwargs).items():
                    if v != _sentinel:
                        bindings[k] = v
                return S(do, *body).s_eval(Scope(scope, bindings))

            return Lambda

        self._s_eval_helper = _s_eval_helper

    def s_eval(self, scope):
        return self._s_eval_helper(scope)


@macro
def fn(required, optional, star, stars, *body):
    """
    an anonymous function.

    >>> foo = S(fn, [S.a, S.b], [S.c, 'c',  S.d, 'd'], S.args, S.kwargs,
    ...         S(Print, S.a, S.b, S.c, S.d),
    ...         S(Print, S.args),
    ...         S(Print, S.kwargs),)()
    >>> foo(1, c=2, b=3, q=4)
    1 3 2 d
    ()
    {'q': 4}
    >>> foo(1,2,3,4,5,6,q=7)
    1 2 3 4
    (5, 6)
    {'q': 7}
    """
    return SLambda(body, required, optional, star, stars)


@macro
def mac(required, optional, star, stars, *body):
    return S(s_eval, S(macro, SLambda(body, required, optional, star, stars)))


@macro
def defn(name, required, optional, star, stars, *body):
    return S(do,
             S(setq, name, S(fn, required, optional, star, stars,
                             *body)),
             name, )


@macro
def defmac(name, required, optional, star, stars, *body):
    return S(do,
             S(setq, name, S(mac, required, optional, star, stars,
                             *body)),
             name, )


@macro
def let_n(pairs, *body):
    """
    lambda with given locals that immediately calls itself.

    >>> from operator import add
    >>> S(let_n, (S.a, 1, S.b, S(add, 1, 1)),
    ...   S(entuple, S.a, S.b))()
    (1, 2)
    """
    return S(S(L0, S(setq, *pairs), S(do, *body)))


@macro
def let1(symbol, value, *body):
    """
    1-arg lambda that immediately calls itself with the given value.

    >>> from operator import add
    >>> S(let1, S.a, S(add, 1, 1),
    ...   S(Print, S.a))()
    2
    """
    return S(S(L1, symbol, S(do, *body)), value)


# S(defmacro, S.defmacro_g_, (), (),
#   S(Lt, (S.syms, foo),
#     S(defmacro, S.name.u, S.args.u,
#       S(Lt, S(map,
#               S(L1, S.s,
#                 S(S.s.u, S(gensym, S(subseq,
#                                      S(symbol_name S.s), ).u)).q)).u)).q)
# , star=S.args, stars=S.kwargs).s_eval(globals())

class SLambda0(SEvaluable):
    def __init__(self, body):
        self.body = body

    def s_eval(self, scope):
        def l0():
            return self.body.s_eval(Scope(scope))

        return l0


# noinspection PyPep8Naming
@macro
def L0(*body):
    """ 0-argument lambda, simple and fast. New scope, but no binding. """
    return SLambda0(S(do, *body))


class SLambda1(SEvaluable):
    def __init__(self, symbol, body):
        self.body = body
        self.symbol = symbol

    def s_eval(self, scope):
        def l1(arg):
            return self.body.s_eval(Scope(scope, {self.symbol: arg}))

        return l1


# noinspection PyPep8Naming
@macro
def L1(symbol, *body):
    """ 1-argument lambda, simple and fast. """
    return SLambda1(symbol, S(do, *body))


class SLambda2(SEvaluable):
    def __init__(self, x, y, body):
        self.body = body
        self.x = x
        self.y = y

    def s_eval(self, scope):
        def l2(x, y):
            return self.body.s_eval(Scope(scope, {self.x: x, self.y: y}))

        return l2


# noinspection PyPep8Naming
@macro
def L2(x, y, *body):
    """ 2-argument lambda; a simple and fast binary operator. """
    return SLambda2(x, y, S(do, *body))


class SLambdaA(SEvaluable):
    def __init__(self, args, body):
        self.body = body
        self.args = args

    def s_eval(self, scope):
        def la(*args):
            return self.body.s_eval(Scope(scope, {self.args: args}))

        return la


# noinspection PyPep8Naming
@macro
def La(args, *body):
    return SLambdaA(args, S(do, *body))

# # symbols, vargs, kwonly, kwvargs
# # noinspection PyPep8Naming
# @macro
# def Lx(symbols, *body, varg=None, kwonlys=(), kwvarg=None, defaults=()):
#     """
#     lambda expression.
#     >>> from operator import add
#     >>> plus = S(Lx, (S.x, S.y), S(add, S.x, S.y))
#     >>> S(plus, 40, 2).s_eval()
#     42
#     >>> S(plus, 20, 4).s_eval()
#     24
#     """
#     # TODO: test varg, kwonlys, kwvarg, defaults
#     return SLambda(symbols, S(do, *body), varg, kwonlys, kwvarg, defaults)




defmac_g_ = None
S(defmac, S.defmac_g_, (S.name, S.required, S.optional, S.star, S.stars), (), S.body, None,
  S(let1, S.syms, S(frozenset,
                    S(filter,
                      lambda x: isinstance(x, Symbol) and x.startswith('g_'),
                      # S(L1, S.x,
                      #   S(And,
                      #     S(isinstance, S.x, Symbol),
                      #     S(S(dot,S.x,S.startswith), 'g_'))),
                      # flatten_sexpr is only for sexpr, not tuples, so make one w/apply.
                      S(flatten_sexpr, S(apply, S, star=S.body)))),
    +S(defmac, ~S.name, ~S.required, ~S.optional, ~S.star, ~S.stars,
       ~S(Print, S.syms),
       S(let_n, ~S(tuple, S(chain.from_iterable, S(map,
                                                   lambda x: (x, gensym(x)),
                                                   # S(L1, S.x,
                                                   #   S(entuple, S.x, S(gensym, S.x.data))),
                                                   S.syms))),
         -S.body, )))).s_eval(globals())
defmac_g_.__doc__ = """\
defines a macro with automatic gensyms for symbols starting with g_

>>> expensive_get_number = lambda: do(Print("spam"),14)
>>> S(do,
...   S(defmac, S.triple_1, [S.n],[],0,0,
...   +S(sum,S(entuple,~S.n,~S.n,~S.n))),
...   S(S.triple_1, S(S.expensive_get_number))).s_eval(globals())
spam
spam
spam
42
>>> S(do,
...   S(defmac_g_, S.triple_2, [S.n],[],0,0,
...     S(Raise,S(Exception,S(repr,S(scope)))),
...     +S(do,
...        S(setq, ~S.g_n, ~S.n),
...        S(sum,S(entuple,~S.g_n,~S.g_n,~S.g_n)))),
...   S(S.triple_2, S(S.expensive_get_number))).s_eval(globals())
"""
# => (defn expensive-get-number [] (print "spam") 14)
# => (defmacro triple-1 [n] `(+ n n n))
# => (triple-1 (expensive-get-number))  ; evals n three times!
# spam
# spam
# spam
# 42
#
# You can avoid this with a gensym:
#
# => (defmacro/g! triple-2 [n] `(do (setv ~g!n ~n) (+ ~g!n ~g!n ~g!n)))
# => (triple-2 (expensive-get-number))  ; avoid repeats with a gensym
# spam
# 42
# (defmacro/g! nif [expr pos zero neg]
# `(let [[~g!res ~expr]]
# (cond [(pos? ~g!res) ~pos]
# [(zero? ~g!res) ~zero]
# [(neg? ~g!res) ~neg])))
# (print (nif (inc -1) 1 0 -1))


class SNonlocal(SEvaluable):
    def __init__(self, symbols):
        self.symbols = symbols

    def s_eval(self, scope):
        scope.Nonlocal(*self.symbols)


# noinspection PyPep8Naming
@macro
def Nonlocal(*symbols):
    return SNonlocal(symbols)


# class SThunk(object):
#     def __init__(self, body):
#         self.body = body
#
#     def s_eval(self, scope=None):
#         return lambda: s_eval_in_scope(self.body, scope)
#
#
# @macro
# def thunk(body):
#     """ only delays evaluation, does not even create a new scope. """
#     return SThunk(body)


# noinspection PyPep8Naming
@macro
def If(boolean, then, Else=S()):
    """
    >>> from operator import add, sub
    >>> S(If, S(sub, 1, 1), S(Print, 'then'))()
    S()
    >>> S(If, S(add, 1, 1), S(Print, 'then'))()
    then
    >>> S(If, S(add, 1, 1),
    ...   S(Print, 'then'),
    ...   S(Print, 'else'))()
    then
    >>> S(If, S(sub, 1, 1),
    ...   S(Print, 'then'),
    ...   S(Print, 'else'))()
    else
    """
    return S(s_eval,
             S((Else, then).__getitem__,
               S(bool,
                 boolean)))


# noinspection PyPep8Naming
@macro
def cond(*rest, **Else):
    assert Else.keys() <= frozenset(['Else'])
    Else = Else.get('Else', S())
    return S(Elif,
             *map(lambda x: S(identity,
                              x),
                  rest),
             Else=S(identity,
                    Else))


# @macro
# def AND(first=True, *rest):
#     """
#     returns the first false argument. Shortcuts evaluation of the
#     remaining S expressions.
#     >>> S(AND).eval()
#     True
#     >>> S(AND,'yes').eval()
#     'yes'
#     >>> S(AND,False).eval()
#     False
#     >>> S(AND,S(str,1),True,"yes",S(Print,'shortcut?'),S(Print,'nope')).eval()
#     shortcut?
#     """
#     return S(IF,first,S(EVAL,S(AND,*rest)),first)
#
# @macro
# def OR(scope, first=None, *rest):
#     """
#     returns the first true argument. Shortcuts evaluation of the
#     remaining S expressions.
#     >>> S(OR).eval()
#     >>> S(OR,'yes').eval()
#     'yes'
#     >>> S(OR,[]).eval()
#     []
#     >>> S(OR,[],'yes').eval()
#     'yes'
#     >>> S(OR,[],'',False,S(Print,'shortcut?'),'yes?',S(Print,'nope')).eval()
#     shortcut?
#     'yes?'
#     """
#     first = try_eval(first, scope)
#     if not rest:
#         return first
#     if first:
#         return first
#     return OR(scope, *rest)


@macro
def dot(obj, *names):
    """
    attribute and index/key access macro
    >>> 'quux'[-1]
    'x'
    >>> S(dot,'quux',[-1])()
    'x'
    >>> ['foo','bar','baz'][1][-1]
    'r'
    >>> S(dot,['foo','bar','baz'],[1],[-1])()
    'r'
    >>> str.join.__name__
    'join'
    >>> S(dot,str,S.join,S.__name__)(join='error!')
    'join'
    """
    res = obj
    for n in names:
        # the unattached subscripts [i] are actually lists, so n[0]
        res = res[n[0]] if isinstance(n, list) else getattr(res, n)
    return res


def _private():
    _sentinel = object()  # used only for is check

    global thr, thrt
    # noinspection PyShadowingNames
    @macro
    def thr(x, first=_sentinel, *rest):
        """
        >>> spam = "backwards. is sentence This"
        >>> S(thr, spam.replace("backwards", "forwards").split(), S(reversed), S(' '.join))()
        'This sentence is forwards.'
        """
        # TODO: doctest threading
        if first is _sentinel:
            return x
        return thr(S(first[0], x, *first.args[1:], **first.kwargs), *rest)

    # noinspection PyShadowingNames
    @macro
    def thrt(x, first=_sentinel, *rest):
        # TODO: doctest threading_tail
        if first is _sentinel:
            return x
        return thrt(S(first[0], *(first.args[1:] + (x,)), **first.kwargs), *rest)


thr = None
thrt = None

_private()
del _private

# def GENX(func,iterable,predicate):
# TODO: genexprs


# def Def

# TODO: port Hy builtins/core?


# TODO: comprehension macros

# def compose1(f,g):
#     return lambda *args,**kwargs: f(g(*args,**kwargs))
#
# def compose(f,g):
#     return lambda *args,**kwargs: f(*g(*args,**kwargs))

# @macro
# def Lambda(arg,body):
#     return eval('lambda %s:body'%arg)

# TODO: doctests
# import doctest; doctest.testmod()
