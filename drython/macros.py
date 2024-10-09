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
from functools import wraps
from drython.statement import Print

from collections import Mapping

from drython.core import partition, identity, Empty, entuple
from drython.s_expression import S, macro, s_eval_in_scope
from drython.statement import Elif, progn, Raise


# macros.py depends on core.py, s_expression.py, and statement.py
# macros.py does not currently require stack.py
@macro
def s_eval(body):
    return SEval(body)


class SEval(object):
    def __init__(self, body):
        self.body = body

    def s_eval(self, scope):
        if hasattr(self.body, 's_eval'):
            res = self.body.s_eval(scope)
            if hasattr(res, 's_eval'):
                return res.s_eval(scope)
            return res
        return self.body


class Scope(Mapping):
    def __len__(self):
        return len(self.vars)

    def __iter__(self):
        return iter(self.vars)

    def __init__(self, parent, local_variables=None):
        self.parent = parent
        self.vars = local_variables or {}
        self.nonlocals = set()

    def __getitem__(self, name):
        try:
            return self.vars[name]
        except KeyError:
            try:
                return self.parent[name]
            except TypeError as err:
                Raise(NameError('name %s is not defined in scope' % repr(name)), From=err)
            except KeyError as err:
                Raise(NameError('name %s is not defined in scope' % repr(name)), From=err)

    def __setitem__(self, name, val):
        if name in self.nonlocals:
            try:
                self.parent[name] = val
            except KeyError as err:
                Raise(NameError('nonlocal %s not found' % repr(name)), From=err)
            except TypeError as err:
                Raise(NameError('nonlocal %s not found' % repr(name)), From=err)
        else:
            self.vars[name] = val

    # noinspection PyPep8Naming
    def Nonlocal(self, *names):
        self.nonlocals |= set(names)


class SSetQ(object):
    def __init__(self, pairs):
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


class SLambda(object):
    def __init__(self, body, required=(), optional=(), star=None, stars=None):
        def _s_eval_helper(scope):
            assert len(optional) % 2 == 0
            pairs = tuple(partition(optional))
            keys, defaults = zip(*pairs) if pairs else ((), ())
            # no gensyms in eval, so ban word.
            assert 'locals' not in frozenset(required) | frozenset(keys) | {star, stars}
            defaults = S(entuple, *defaults).s_eval(scope)

            _sentinel = object()
            func = eval('''lambda {required}{optional}{star}{stars}: locals()'''.format(
                required=''.join(map('{0}, '.format, required)),
                optional=''.join(map('{0}=_sentinel, '.format, keys)),
                star='*%s,' % star if star else '',
                stars='**' + stars if stars else ''), dict(_sentinel=_sentinel))

            @wraps(func)
            def Lambda(*args, **kwargs):
                bindings = dict(zip(keys, defaults))
                for k, v in func(*args, **kwargs).items():
                    if v != _sentinel:
                        bindings[k] = v
                return S(progn, *body).s_eval(Scope(scope, bindings))

            return Lambda

        self._s_eval_helper = _s_eval_helper

    def s_eval(self, scope):
        return self._s_eval_helper(scope)


@macro
def fn(required, optional, *body, **stargs):
    """
    an anonymous function.

    >>> foo = S(fn,[S.a, S.b], [S.c, 'c',  S.d, 'd'],
    ...         S(Print,S.a,S.b,S.c,S.d),
    ...         S(Print,S.args),
    ...         S(Print,S.kwargs),
    ...       star=S.args, stars=S.kwargs)()
    >>> foo(1, c=2, b=3, q=4)
    1 3 2 d
    ()
    {'q': 4}
    >>> foo(1,2,3,4,5,6,q=7)
    1 2 3 4
    (5, 6)
    {'q': 7}
    """
    return SLambda(body, required, optional, **stargs)


@macro
def mac(required, optional, *body, **stargs):
    return S(s_eval, S(macro, SLambda(body, required, optional, **stargs)))


@macro
def defn(name, required, optional, *body, **stargs):
    return S(setq, name, S(fn, required, optional, *body, **stargs))


@macro
def defmacro(name, required, optional, *body, **stargs):
    return S(setq, name, S(mac, required, optional, *body, **stargs))


@macro
def let_n(pairs, *body):
    """
    lambda with default arguments that immediately calls itself.

    >>> from operator import add
    >>> S(let_n, (S.a, 1, S.b, S(add, 1, 1)),
    ...   S(Print, S.a, S.b))()
    1 2
    """
    return S(S(fn, (), pairs, S(progn, *body)))


@macro
def let1(symbol, value, *body):
    """
    1-arg lambda that immediately calls itself with the given value.

    >>> from operator import add
    >>> S(let1, S.a, S(add, 1, 1),
    ...   S(Print, S.a))()
    2
    """
    return S(S(L1, symbol, S(progn, *body)), value)


# S(defmacro, S.defmacro_g_, (), (),
#   S(Lt, (S.syms, foo),
#     S(defmacro, S.name.u, S.args.u,
#       S(Lt, S(map,
#               S(L1, S.s,
#                 S(S.s.u, S(gensym, S(subseq,
#                                      S(symbol_name S.s), ).u)).q)).u)).q)
# , star=S.args, stars=S.kwargs).s_eval(globals())

class SLambda0(object):
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
    return SLambda0(S(progn, *body))


class SLambda1(object):
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
    return SLambda1(symbol, S(progn, *body))


class SLambda2(object):
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
    return SLambda2(x, y, S(progn, *body))


class SLambdaA(object):
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
    return SLambdaA(args, S(progn, *body))


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
#     return SLambda(symbols, S(progn, *body), varg, kwonlys, kwvarg, defaults)





class SNonlocal(object):
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
def If(boolean, then, Else=None):
    """
    >>> from operator import add, sub
    >>> S(If, S(sub, 1, 1), S(Print, 'then'))()
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
    Else = Else.get('Else', None)
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
    _sentinel = S(None)  # used only for is check

    global thr, thrt
    # noinspection PyShadowingNames
    @macro
    def thr(x, first=_sentinel, *rest):
        # TODO: doctest threading
        if first is _sentinel:
            return x
        return thr(S(first.func, x, *first.args, **first.kwargs), *rest)

    # noinspection PyShadowingNames
    @macro
    def thrt(x, first=_sentinel, *rest):
        # TODO: doctest threading_tail
        if first is _sentinel:
            return x
        return thrt(S(first.func, *(first.args + (x,)), **first.kwargs), *rest)


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


# # s_eval_in_scope may have made this obsolete
# class Quote(object):
#     __slots__ = ('item',)
#
#     def __init__(self, item):
#         self.item = item
#
#     def s_eval(self, scope):
#         return self.item
#
#     def __repr__(self):
#         return 'Quote(%s)' % repr(self.item)
#
#     @classmethod
#     def of(cls, item):
#         """
#         Unlike the usual __init__(), of() will not
#         quote the item if it is already s-evaluable
#         """
#         if hasattr(item, 's_eval'):
#             return item
#         return cls(item)
