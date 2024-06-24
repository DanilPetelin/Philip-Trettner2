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
S-expressions and related functions.
"""


__author__ = 'Matthew Egan Odendahl'


class SExpression:
    """
    S-expression for Python, with macros.

    An S object represents a potential function call.
    The function isn't actually called until invocation
    of the .eval() method, which will also .eval() any
    nested S objects before applying the function.
    >>> from operator import add, mul
    >>> spam = S(add,20,4)
    >>> spam
    S(<built-in function add>, *(20, 4))
    >>> spam.eval()
    24
    >>> spam = S(add,S(mul,4,10),2)
    >>> spam.eval()
    42

    Even the function argument can be a nested S-expression
    >>> S(S(lambda a,b:a and b,add,mul),2,3).eval()
    6
    >>> S(S(lambda a,b:a or b,add,mul),2,3).eval()
    5

    Keywords also work
    >>> S(print,1,2,3,sep='::').eval()
    1::2::3

    S expressions are executable data structures--both code and data.
    .eval() treats functions with the @macro decorator specially.
    These are given any nested S objects unevaluated, and return a
    new S object to be evaluated; potentially rewriting custom
    domain-specific language forms to executable Python code. An
    if macro is a simple example:
    >>> If = lambda scope,b,t,e=None: t if try_eval(b,scope) else e
    >>> If.__macro__ = None
    >>> S(If, True, S(print,'yes'), S(print,'no')).eval()
    yes
    >>> S(If, False, S(print,'yes'), S(print,'no')).eval()
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
    >>> S(lambda x:x,[S(print,'test')]).eval()
    [S(<built-in function print>, *('test',))]

    This does, since it uses another S-expression to make the list.
    >>> S(lambda x:x,S(lambda *es:list(es),S(print,'test'))).eval()
    test
    [None]

    Explicit evaluation also works.
    >>> S(lambda x:x,[S(print,'test').eval()]).eval()
    test
    [None]

    """

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def eval(self, scope=()):
        func = try_eval(self.func, scope)
        if hasattr(func, '__macro__'):
            return try_eval(func(scope, *self.args, **self.kwargs), scope)
        return func(
            *(try_eval(a, scope) for a in self.args),
            **{k: try_eval(v, scope) for k, v in self.kwargs.items()})

    def __repr__(self):
        return "S({0}{1}{2})".format(
            repr(self.func),
            ', *'+repr(self.args) if self.args else '',
            ', **'+repr(self.kwargs) if self.kwargs else '')


class SymbolError(NameError):
    pass


def _private():
    from collections import UserString
    from keyword import kwlist as _keyword_set
    _keyword_set = set(_keyword_set)

    # noinspection PyShadowingNames
    class SymbolType(UserString, str):
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
            return 'S.'+self.data

        def eval(self, scope=()):
            try:
                return scope[self.data]
            except KeyError as ke:
                raise SymbolError(
                    'Symbol %s is not bound in the given scope' % repr(self))

    return SymbolType

SymbolType = _private()
del _private


def _private():
    class S_Syntax:
        def __call__(self, func, *args, **kwargs):
            return SExpression(func,*args,**kwargs)

        def __getattribute__(self,attr):
            return SymbolType(attr)

    return S_Syntax()

S = _private()
del _private


def try_eval(s, scope=()):
    try:
        return s.eval(scope)
    except AttributeError:
        return s  # anything without an eval() evals to itself.


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
if __name__ == "__main__": import doctest; doctest.testmod()
