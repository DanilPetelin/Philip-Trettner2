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
S-expression for Python, with symbol and macro support.

Module usage:
from expression.s_expression import S
"""

# s_expression.py does not depend on other modules in this package
# future versions may safely depend on core.py and statement.py
from abc import ABCMeta, abstractmethod
from operator import add

from statement import Var


class SEvaluable(metaclass=ABCMeta):
    @abstractmethod
    def s_eval(self, scope):
        pass


class SExpression(SEvaluable):
    """
    S-expressions are executable data structures for metaprogramming.

    An S object represents a potential function call.

    The function isn't actually called until invocation
    of the .s_eval() method, which will also .s_eval() any
    nested SEvaluable objects before applying the function.
    >>> from operator import add, mul
    >>> spam = S(add,20,4)
    >>> spam
    S(<built-in function add>,
      20,
      4)
    >>> spam.s_eval()  # same as >>> add(20,4)
    24
    >>> spam = S(add,S(mul,4,10),2)  # represents >>> add(mul(4, 10), 2)  # 4*10 + 2
    >>> spam.s_eval()
    42

    Even the function argument can be a nested S-expression
    >>> S(S(lambda a,b: a and b, add,mul),2,3).s_eval()
    6
    >>> S(S(lambda a,b: a or b, add,mul),2,3).s_eval()
    5

    Keywords also work
    >>> S(print,1,2,3,sep='::').s_eval()
    1::2::3

    Important: SExpression will not peek into other data structures to evaluate
    nested SEvaluable objects. You must evaluate them explicitly, or use
    an S-expression to create the data structure.

    This doesn't print 'test'.
    >>> identity = lambda x: x
    >>> S(identity,[S(print,'test')]).s_eval()
    [S(<built-in function print>,
      'test')]

    This does, since it uses another S-expression to make the list.
    >>> from drython.core import List
    >>> S(identity,S(List,S(print,'test'))).s_eval()
    test
    [None]

    Explicit evaluation also works.
    >>> S(identity,[S(print,'test').s_eval()]).s_eval()
    test
    [None]

    SExpression treats functions with the @macro decorator specially.
    These are given any nested S objects unevaluated, and return a
    new object to be evaluated.
    >>> from drython.macros import If
    >>> S(If, True, S(print,'yes'), S(print,'no')).s_eval()
    yes
    >>> S(If, False, S(print,'yes'), S(print,'no')).s_eval()
    no

    For comparison, note that a non-macro function gets any nested
    S objects pre-evaluated.
    >>> S(lambda b,t,e=None: t if b else e,
    ...   True, S(print,'yes'), S(print,'no')).s_eval()
    yes
    no

    """

    def __init__(self, func, *args, **kwargs):
        # non-SEvaluables are quoted so they s_eval to themselves
        self.qfunc = Quote.of(func)
        self.qargs = map(Quote.of, args)
        self.qkwargs = {k: Quote.of(v) for k, v in kwargs.items()}
        # keep unquoted data for __repr__ and macros
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def s_eval(self, scope=None):
        func = self.qfunc.s_eval(scope)
        if hasattr(func, '__macro__'):
            # return try_eval(func(*self.args, **self.kwargs), scope)
            form = func(*self.args, **self.kwargs)
            return form.s_eval(scope) if isinstance(form, SEvaluable) else form
        return func(
            *(a.s_eval(scope) for a in self.qargs),
            **{k: v.s_eval(scope) for k, v in self.qkwargs.items()})

    def __repr__(self):
        indent = '\n  '
        return "S({0}{1}{2})".format(
            repr(self.func),
            ',' + indent + (',' + indent).join(
                map(lambda a: repr(a).replace('\n', indent), self.args))
            if self.args else '',
            ',{0}**{1}'.format(indent, repr(self.kwargs).replace('\n', indent))
            if self.kwargs else '')


class SymbolError(NameError):
    pass


class Quote(SEvaluable):
    __slots__ = ('item',)

    def __init__(self, item):
        self.item = item

    def s_eval(self, scope):
        return self.item

    def __repr__(self):
        return 'Quote(%s)' % repr(self.item)

    @classmethod
    def of(cls, item):
        """
        Unlike the usual __init__(), of() will not
        quote the item if it is already SEvaluable
        """
        if isinstance(item, SEvaluable):
            return item
        return cls(item)


def _private():
    from collections import UserString
    from keyword import kwlist as _keyword_set

    _keyword_set = set(_keyword_set)


    # noinspection PyShadowingNames
    class SymbolType(UserString, str, SEvaluable):
        """
        Symbols for S-expressions.

        A Symbol represents a potential Python identifier.
        >>> spam = 1
        >>> no_symbol = S(print,spam)
        >>> no_symbol  # spam already resolved to 1
        S(<built-in function print>,
          1)
        >>> with_symbol = S(print,S.spam)
        >>> with_symbol  # S.spam is still a symbol
        S(<built-in function print>,
          S.spam)
        >>> no_symbol.s_eval()
        1

        Symbols require a containing scope
        >>> with_symbol.s_eval(globals())
        1
        >>> spam = 8

        doesn't change, was baked-in
        >>> no_symbol.s_eval(globals())
        1

        globals()['spam'] == 8
        >>> with_symbol.s_eval(globals())
        8

        value depends on scope
        >>> with_symbol.s_eval(dict(spam=42))
        42

        Macros get Symbols unevaluated. Unevaluated Symbols work like strings.
        So macros can also rewrite Symbols
        >>> S.quux + S.norf
        S.quuxnorf
        """

        def __init__(self, name):
            super().__init__(name)
            # self.__name__ = 'SymbolType'

        def __repr__(self):
            """
            >>> S.foo
            S.foo
            >>> S.fo + S.r
            SymbolType('for')
            >>> '1' + S.foo
            SymbolType('1foo')
            """
            if not self.data.isidentifier() or self.data in _keyword_set:
                return 'SymbolType(%s)' % repr(self.data)
            return 'S.' + self.data

        from types import MappingProxyType

        def s_eval(self, scope=MappingProxyType({})):
            """ looks up itself in scope """
            try:
                return scope[self]
            except KeyError as ex:
                raise SymbolError(
                    'Symbol %s is not bound in the given scope' % repr(self)
                ) from ex
            except TypeError as ex:
                raise SymbolError(
                    'Symbol %s is not bound in the given scope' % repr(self)
                ) from ex

    return SymbolType


SymbolType = _private()
del _private


def _private():
    _gensym_counter = Var(0)

    # noinspection PyShadowingNames
    def gensym(prefix=''):
        """
        generates a unique Symbol. Gensyms are not valid identifiers,
        but they are valid dictionary keys.

        A gensym is only unique per import of this module, when the
        gensym counter is initialized. It should not be relied upon for
        uniqueness across a network, nor in serialized persistent storage.
        gensym() locks the counter update for thread safety.

        Python normally only imports a module once and caches the
        result for any further import attempts, but this can be
        circumvented.

        gensyms are typically used by macros to avoid conflicts
        with other symbols in the environment.

        gensyms have an optional prefix for improved error messages
        and macro debugging. The suffix is the gensym count at creation.

        >>> gensym()
        SymbolType('#:$1')
        >>> gensym(S.foo)  # foo prefix
        SymbolType('#:foo$2')
        >>> gensym(S.foo)  # not the same symbol as above
        SymbolType('#:foo$3')
        >>> gensym('foo')  # strings also work.
        SymbolType('#:foo$4')
        """

        return SymbolType(
            '#:{0}${1}'.format(prefix, str(_gensym_counter.set(1, add))))

    return gensym


gensym = _private()
del _private


def _private():
    class SSyntax:
        """
        prefix for creating S-expressions and Symbols.
        see help('drython.sexpression') for further details.
        """

        def __call__(self, func, *args, **kwargs):
            return SExpression(func, *args, **kwargs)

        def __getattribute__(self, attr):
            return SymbolType(attr)

    return SSyntax()


S = _private()
del _private


# defines an interface used by SExpression, so belongs here, not in macros.py
def macro(func):
    """
    Marks the func as a macro.
    In S-expressions, macros are given any S-expressions
    unevaluated, then the result is evaluated.
    """
    func.__macro__ = None
    return func

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
