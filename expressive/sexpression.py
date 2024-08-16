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
S-expression for Python, with macro support.

Usage:
from expression.sexpression import S
"""

# sexpression.py does not depend on other modules in this package
# future versions may safely depend on core.py and statement.py

class SExpression:
    """
    S-expressions are executable data structures for metaprogramming.

    An S object represents a potential function call.

    The function isn't actually called until invocation
    of the .eval() method, which will also .eval() any
    nested S objects before applying the function.
    >>> from operator import add, mul
    >>> spam = S(add,20,4)
    >>> spam
    S(<built-in function add>,
      20,
      4)
    >>> spam.eval()  # same as >>> add(20,4)
    24
    >>> spam = S(add,S(mul,4,10),2)
    >>> spam.eval()
    42

    Even the function argument can be a nested S-expression
    >>> S(S(lambda a,b: a and b, add,mul),2,3).eval()
    6
    >>> S(S(lambda a,b: a or b, add,mul),2,3).eval()
    5

    Keywords also work
    >>> S(print,1,2,3,sep='::').eval()
    1::2::3

    .eval() treats functions with the @macro decorator specially.
    These are given any nested S objects unevaluated, and return a
    new object to be evaluated.
    >>> from macros import IF
    >>> S(IF, True, S(print,'yes'), S(print,'no')).eval()
    yes
    >>> S(IF, False, S(print,'yes'), S(print,'no')).eval()
    no

    For comparison, note that a non-macro function gets any nested
    S objects pre-evaluated.
    >>> S(lambda b,t,e=None: t if b else e,
    ...   True, S(print,'yes'), S(print,'no')).eval()
    yes
    no

    .eval() will not peek into other data structures to evaluate
    nested S objects. You must evaluate them explicitly, or use
    an S expression to create the data structure.

    This doesn't print 'test'.
    >>> identity = lambda x: x
    >>> S(identity,[S(print,'test')]).eval()
    [S(<built-in function print>,
      'test')]

    This does, since it uses another S-expression to make the list.
    >>> from core import List
    >>> S(identity,S(List,S(print,'test'))).eval()
    test
    [None]

    Explicit evaluation also works.
    >>> S(identity,[S(print,'test').eval()]).eval()
    test
    [None]

    """

    def __init__(self, func, *args, **kwargs):
        self.wfunc = Quote.of(func)
        self.func = func
        self.wargs = tuple(Quote.of(a) for a in args)
        self.args = args
        self.wkwargs = {k: Quote.of(v) for k, v in kwargs.items()}
        self.kwargs = kwargs

    def eval(self, scope=None):
        func = self.wfunc.eval(scope)
        if hasattr(func, '__macro__'):
            # return try_eval(func(*self.args, **self.kwargs), scope)
            form = func(*self.args, **self.kwargs)
            return form.eval(scope) if hasattr(form,'eval') else form
        return func(
            *(a.eval(scope) for a in self.wargs),
            **{k: v.eval(scope) for k, v in self.wkwargs.items()})

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


class Quote:
    __slots__ = ('item',)

    def __init__(self, item):
        self.item = item

    def eval(self, scope):
        return self.item

    def __repr__(self):
        return 'Quote(%s)' % repr(self.item)

    @classmethod
    def of(cls, item):
        if hasattr(item,'eval'):
            return item
        return cls(item)

def _private():
    from collections import UserString
    from keyword import kwlist as _keyword_set

    _keyword_set = set(_keyword_set)


    # noinspection PyShadowingNames
    class SymbolType(UserString, str):
        """
        Symbols for S-expressions.

        A Symbol represents a potential Python identifier.
        >>> spam = 1
        >>> nosymbol = S(print,spam)
        >>> nosymbol  # spam already resolved to 1
        S(<built-in function print>,
          1)
        >>> withsymbol = S(print,S.spam)
        >>> withsymbol  # S.spam is still a symbol
        S(<built-in function print>,
          S.spam)
        >>> nosymbol.eval()
        1

        Symbols require a containing scope
        >>> withsymbol.eval(globals())
        1
        >>> spam = 2
        >>> nosymbol.eval(globals())  # doesn't change
        1
        >>> withsymbol.eval(globals())
        2
        >>> withsymbol.eval(dict(spam=42))  # value depends on scope
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

        def eval(self, scope={}):  # default {} cannot be mutated
            """ looks up itself in scope """
            try:
                return scope[self]
            except KeyError as ex:
                pass
            except TypeError as ex:
                pass
            raise SymbolError(
                'Symbol %s is not bound in the given scope' % repr(self)
            ) from ex

    _gensym_counter = 0

    def gensym(prefix=''):
        nonlocal _gensym_counter
        _gensym_counter +=1
        return SymbolType('#:{0}${1}'.format(prefix, str(_gensym_counter)))

    return SymbolType, gensym

SymbolType = None
gensym = None
SymbolType, gensym = _private()
del _private


def _private():
    class S_Syntax:
        def __call__(self, func, *args, **kwargs):
            return SExpression(func, *args, **kwargs)

        def __getattribute__(self, attr):
            return SymbolType(attr)

    return S_Syntax()


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
