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
Symbolic-expression for Python, with macro support.

Typical module import:

    from drython.s_expression import S

S is a prefix for both symbols and s-expressions
Symbol: `S.foo`,
S-expression: `S(Print,'foo')`.
"""
# s_expression may safely depend on .core and .statement

from __future__ import absolute_import, division
from itertools import chain, count
from keyword import iskeyword
from operator import add
from collections import Mapping
import sys
from drython.core import SEvaluable

if sys.version_info[0] == 2:
    # noinspection PyUnresolvedReferences,PyCompatibility
    from UserString import UserString
else:
    from collections import UserString

from drython.core import Empty, entuple
from drython.statement import Var, Raise, Print

# defines an interface used by SExpression, so belongs here, not in macros.py
def macro(func):
    """
    Marks the func as a macro.
    In S-expressions, macros are given any S-expressions
    unevaluated, then the result is evaluated.
    """
    func._macro_ = None
    return func


class SUnquotable(object):
    def __invert__(self):
        return S(unquote, self)

    def __neg__(self):
        return S(unquote_splice, self)


class SQuotable(SUnquotable):
    def __pos__(self):
        return S(quote, self)


@macro
def quote(item):
    return Quote(item)


class Quote(SEvaluable, SQuotable):
    def __init__(self, item):
        self.item = item

    def __repr__(self):
        return 'Quote(%s)' % repr(self.item)

    def s_eval(self, scope):
        return self.item


@macro
def unquote(item):
    r"""
    unquotes an element in a quasiquoted S-expression. Usually written as ~S...

    unquote works on S-expressions and Symbols, in any position in a quasiquoted form.
    >>> from drython.macros import *
    >>> from operator import add
    >>> sexp = S(progn,
    ...          S(setq,
    ...            S.foo,Print,
    ...            S.x,1,
    ...            S.y,':'),
    ...          +S(~S.foo,
    ...             ~S.x,
    ...             42,
    ...             ~S(add,S.x,2),
    ...             sep=~S.y,
    ...             end=~S(add,'$','\n')))()
    >>> sexp.fargs  # atoms appear in the same order as written
    (<built-in function print>, 1, 42, 3)
    >>> sexp.kwargs == dict(sep=':',end='$\n')  # kwargs also work!
    True
    >>> sexp()  # the function position too.
    1:42:3$
    """
    return Unquote(item)


class Unquote(SQuotable):
    PREFIX = '~'

    def __init__(self, item):
        self.item = item

    def __repr__(self):
        if isinstance(self.item, SUnquotable):
            return self.PREFIX + repr(self.item).replace('\n', '\n ')
        else:
            return '<{0} {1}>'.format(self.__class__.__name__, repr(self.item))

    def s_unquote(self, scope):
        return self.item.s_eval(scope)

        # def s_eval(self, scope):
        #     raise TypeError("Unquote outside of Quasiquote")


class UnquoteSplice(Unquote):
    PREFIX = '-'


@macro
def unquote_splice(item):
    r"""
    inserts arguments into a quasiquoted form. Usually written as -S...

    generally works on iterables.
    >>> from drython.macros import *
    >>> args = (1,2,3)
    >>> sexp = S(progn,+S(Print, 0.0, -S.args, 4.4)).s_eval(globals())
    >>> sexp
    S(<built-in function print>,
      0.0,
      1,
      2,
      3,
      4.4)
    >>> sexp()
    0.0 1 2 3 4.4

    also works on quoted S-expressions, keyword args too!
    >>> S(progn,S(setq,S.x,+S(1,2,3,sep=':')),
    ...   +S(Print, 0.0, -S.x, -S(entuple, 44,55), 6.6, end='$\n'))()()
    0.0:1:2:3:44:55:6.6$

    this is because an S-expression is a Mapping.
    int keys are the args, str keys are the kwargs.
    >>> S(progn,
    ...   S(setq,S.x,{0:1,1:2,'end':'$\n'}),  # store a dict in variable S.x
    ...   +S(-+S(Print,0),  # quote to use sexpr as mapping and unquote_splice it
    ...      -+S(sep=':'),  # kwargs don't have to be at the end.
    ...      -S.x,  # evaluates to the dict
    ... ))()()  # eval the progn, then the progn's result
    0:1:2$
    """
    return UnquoteSplice(item)


def args_kwargs(data):
    args = []
    kwargs = Empty
    try:
        for i in count():
            args.append(data[i])
    except IndexError:
        pass
    except KeyError:
        pass
    if isinstance(data, Mapping):
        kwargs = {k: v for k, v in data.items() if not isinstance(k, int)}
    return args, kwargs


def s_unquote_in_scope(element, scope):
    if isinstance(element, SExpression) and element:
        if element[0] == unquote:
            element = element.s_eval(scope)
        elif element[0] == unquote_splice:
            element = element.s_eval(scope).s_unquote(scope)
            return args_kwargs(element)
    if hasattr(element, 's_unquote'):
        return (element.s_unquote(scope),), Empty
    return (element,), Empty


# def s_unquote_in_scope(element, scope):
#     if isinstance(element, SExpression) and element.func == unquote:
#         element = element.s_eval(scope)
#     if hasattr(element, 's_unquote'):
#         return element.s_unquote(scope)
#     return element


def s_eval_in_scope(element, scope):
    """
    Evaluates the element in the given scope using its s_eval method, if present.
    Otherwise returns the element unevaluated.

    >>> from operator import sub
    >>> s_eval_in_scope(S(sub,S.x,S.y), dict(x=10,y=3))
    7

    integers are not s-evaluable, so evaluate to themselves.
    >>> s_eval_in_scope(10-7, globals())
    3
    """
    if hasattr(element, '_s_evaluable_') and isinstance(element, SEvaluable):
        return element.s_eval(scope)
    return element


class SExpressionException(Exception):
    pass


class SExpression(Mapping, SEvaluable, SUnquotable):
    """
    S-expressions are executable data structures for metaprogramming.

    An SExpression object represents a potential function call.

    The function isn't actually called until invocation
    of the .s_eval() method, which will also .s_eval() any
    nested SEvaluable objects before applying the function.
    >>> from operator import add, mul
    >>> spam = S(add,20,4)
    >>> spam
    S(<built-in function add>,
      20,
      4)
    >>> spam.s_eval({})  # same as >>> add(20,4)
    24
    >>> spam()  # S-expressions are also callable
    24

    represents >>> add(mul(4, 10), 2)  # 4*10 + 2
    >>> spam = S(add,S(mul,4,10),2)
    >>> spam()
    42

    Even the function argument can be a nested S-expression
    >>> S(S(lambda a,b: a and b, add,mul),2,3)()
    6
    >>> S(S(lambda a,b: a or b, add,mul),2,3)()
    5

    Keywords also work
    >>> S(Print,1,2,3,sep='::')()
    1::2::3

    Important: SExpression will not peek into other data structures to evaluate
    nested SEvaluable objects. You must evaluate them explicitly, or use
    an S-expression to create the data structure.

    This doesn't print 'test'.
    >>> identity = lambda x: x
    >>> S(identity,[S(Print,'test')])()
    [S(<built-in function print>,
      'test')]

    This does, since it uses another S-expression to make the list.
    >>> from drython.core import enlist
    >>> S(identity,S(enlist,S(Print,'test')))()
    test
    [None]

    Explicit evaluation also works.
    >>> S(identity,[S(Print,'test').s_eval(globals())]).s_eval(globals())
    test
    [None]

    SExpression treats functions with the @macro decorator specially.
    These are given any nested S objects unevaluated, and return a
    new object to be evaluated.
    >>> from drython.macros import If
    >>> S(If, True, S(Print,'yes'), S(Print,'no'))()
    yes
    >>> S(If, False, S(Print,'yes'), S(Print,'no'))()
    no

    For comparison, note that a non-macro function gets any nested
    S objects pre-evaluated.
    >>> S(lambda b,t,e=None: t if b else e,
    ...   True, S(Print,'yes'), S(Print,'no'))()
    yes
    no
    """

    def __getitem__(self, key):
        try:
            return self.kwargs[key]
        except KeyError:
            return self.fargs[key]

    def __iter__(self):
        """
        >>> foo = S(Print,'a','b','c',sep='::')
        >>> foo()
        a::b::c
        >>> tuple(foo)
        (0, 1, 2, 3, 'sep')
        >>> tuple(foo.items())
        ((0, <built-in function print>), (1, 'a'), (2, 'b'), (3, 'c'), ('sep', '::'))
        """
        return chain(range(len(self.fargs)), self.kwargs)

    def __len__(self):
        return len(self.fargs) + len(self.kwargs)

    def __init__(self, *args, **kwargs):
        self.fargs = args
        self.kwargs = kwargs

    @staticmethod
    def from_mapping(mapping):
        args, kwargs = args_kwargs(mapping)
        return S(*args, **kwargs)

    def s_eval(self, scope):
        if not self:
            return self
        try:
            func = s_eval_in_scope(self.fargs[0], scope)
            if hasattr(func, '_macro_'):
                return s_eval_in_scope(func(*self.fargs[1:], **self.kwargs), scope)
            return func(
                # generators CAN Unpack with *,
                # but they mask TypeError messages due to Python bug!
                # so we make it a tuple for better errors.
                *tuple(s_eval_in_scope(a, scope) for a in self.fargs[1:]),
                **{k: s_eval_in_scope(v, scope) for k, v in self.kwargs.items()})
        except BaseException as be:
            Raise(SExpressionException('when evaluating\n' + repr(self)), From=be)

    def __repr__(self):
        if len(self.fargs) == 2 and len(self.kwargs) == 0:
            if self[0] == quote and isinstance(self[1], SQuotable):
                return '+' + repr(self[1]).replace('\n', '\n ')
            if self[0] == unquote and isinstance(self[1], SUnquotable):
                return '~' + repr(self[1]).replace('\n', '\n ')
        indent = '\n  '
        return "S({0})".format(
            (',' + indent).join(
                (
                    ((',' + indent).join(map(lambda a: repr(a).replace('\n', indent), self.fargs)),)
                    if self.fargs else ()
                ) + (
                    ('**{0}'.format(repr(self.kwargs).replace('\n', indent)),)
                    if self.kwargs else ()
                )
            )
        )

    def __call__(self, **kwargs):
        return self.s_eval(kwargs)

    def s_unquote(self, scope):
        args = []
        kwargs = {k: s_unquote_in_scope(v, scope)[0][0] for k, v in self.kwargs.items()}
        for a in self.fargs:
            arg, kwarg = s_unquote_in_scope(a, scope)
            args.extend(arg)
            kwargs.update(kwarg)
        return S(*args, **kwargs)

    # def s_unquote(self, scope):
    #     return S(
    #         s_unquote_in_scope(self.func, scope),
    #         *tuple(s_unquote_in_scope(a, scope) for a in self.args),
    #         # *tuple(chain(s_unquote_splice_in_scope(a, scope) for a in self.args)),
    #         **{k: s_unquote_in_scope(v, scope) for k, v in self.kwargs.items()})

    def __pos__(self):
        return S(quasiquote, self)


class Quasiquote(Quote):
    def s_eval(self, scope):
        return self.item.s_unquote(scope)

    def __repr__(self):
        return '+' + repr(self.item).replace('\n', '\n ')


@macro
def quasiquote(sexpr):
    return Quasiquote(sexpr)


# TODO: doctest unquote/splice
# TODO: test double quoted
# the quasiquote expression
#
# `(foo ,bar ,@quux)
#
# stands for
#
# (append (list 'foo) (list bar) quux)
#
# which produces the following when evaluated:
#
# '(foo 2 3 4)


class SymbolError(NameError):
    pass


class Symbol(UserString, str, SEvaluable, SQuotable):
    """
    Symbols for S-expressions.

    A Symbol represents a potential Python identifier.
    >>> spam = 1
    >>> Print(spam)
    1
    >>> no_symbol = S(Print,spam)
    >>> no_symbol  # spam already resolved to 1
    S(<built-in function print>,
      1)
    >>> with_symbol = S(Print,S.spam)
    >>> with_symbol  # S.spam is still a symbol
    S(<built-in function print>,
      S.spam)
    >>> no_symbol()
    1

    Symbols require a containing scope
    >>> with_symbol.s_eval(globals())
    1
    >>> spam = 8

    doesn't change, was baked-in
    >>> no_symbol.s_eval(globals())
    1

    8 == globals()['spam']
    >>> with_symbol.s_eval(globals())
    8

    value depends on scope
    >>> with_symbol.s_eval(dict(spam=42))
    42
    >>> with_symbol(spam=42)  # same as above
    42

    Macros get Symbols unevaluated. Unevaluated Symbols work like strings.
    So macros can also rewrite Symbols
    >>> S.quux + S.norf
    S.quuxnorf
    """

    def __repr__(self):
        """
        >>> S.x
        S.x
        >>> S._foo
        S._foo
        >>> S.fo + S.r
        Symbol('for')
        >>> Symbol('1') + S.foo
        Symbol('1foo')
        """
        # and self.isidentifier(): <- not in 2.7
        if (not iskeyword(self)
            and (self[0].isalpha() or self[0] == '_')
            and (len(self) == 1 or self[1:].replace('_', 'X').isalnum())):
            return 'S.' + self.data
        return 'Symbol(%s)' % repr(self.data)

    def s_eval(self, scope=Empty):
        """ looks up itself in scope """
        try:
            return scope[self]
        except KeyError:
            Raise(SymbolError(
                'Symbol %s is not bound in the given scope' % repr(self)
            ), From=None)


def _private():
    _gensym_counter = Var(0)

    # noinspection PyGlobalUndefined
    global gensym

    # noinspection PyRedeclaration,PyUnusedLocal
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
        Symbol('<#1>')
        >>> gensym(S.foo)  # foo prefix
        Symbol('<foo#2>')
        >>> gensym(S.foo)  # not the same symbol as above
        Symbol('<foo#3>')
        >>> gensym('foo')  # strings also work.
        Symbol('<foo#4>')
        """

        return Symbol(
            '<{0}#{1}>'.format(prefix, str(_gensym_counter.set(1, add))))


_private()
del _private


def _private():
    class SSyntax(object):
        """
        prefix for creating S-expressions and Symbols.
        see help('drython.s_expression') for further details.
        """
        __slots__ = ()

        def __call__(self, *args, **kwargs):
            return SExpression(*args, **kwargs)

        def __getattribute__(self, attr):
            return Symbol(attr)

    return SSyntax()


S = _private()
del _private


def flatten_sexpr(sexpr):
    res = []
    for v in sexpr.values():
        while isinstance(v, SExpression.Quasiquote):
            v = v.item
        if isinstance(v, SExpression):
            res.extend(flatten_sexpr(v))
        else:
            res.append(v)
    return res
