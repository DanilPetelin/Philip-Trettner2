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
from drython.statement import Atom, Raise, Print

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

    S-expressions are mappings, and can be created from mappings.
    >>> spam = S**{0:Print, 1:'a', 2:'b', 3:'c', 'sep':'; '}
    >>> spam()
    a; b; c
    >>> spam['sep']
    '; '

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
            return self.args[key]

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
        return chain(range(len(self.args)), self.kwargs)

    def __len__(self):
        return len(self.args) + len(self.kwargs)

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    @staticmethod
    def from_mapping(mapping):
        if isinstance(mapping, SExpression):
            return mapping
        args, kwargs = args_kwargs(mapping)
        return S(*args, **kwargs)

    def s_eval(self, scope):
        if not self:
            return self
        try:
            func = s_eval_in_scope(self.args[0], scope)
            if hasattr(func, '_macro_'):
                return s_eval_in_scope(func(*self.args[1:], **self.kwargs), scope)
            return func(
                # generators CAN Unpack with *,
                # but they mask TypeError messages due to Python bug!
                # so we make it a tuple for better errors.
                *tuple(s_eval_in_scope(a, scope) for a in self.args[1:]),
                **{k: s_eval_in_scope(v, scope) for k, v in self.kwargs.items()})
        except BaseException as be:
            Raise(SExpressionException('when evaluating\n' + repr(self)), From=be)

    def __repr__(self):
        if len(self.args) == 2 and len(self.kwargs) == 0:
            if self[0] == quote and isinstance(self[1], SQuotable):
                return '+' + repr(self[1]).replace('\n', '\n ')
            if self[0] == unquote and isinstance(self[1], SUnquotable):
                return '~' + repr(self[1]).replace('\n', '\n ')
        indent = '\n  '
        return "S({0})".format(
            (',' + indent).join(
                (
                    ((',' + indent).join(map(lambda a: repr(a).replace('\n', indent), self.args)),)
                    if self.args else ()
                ) + (
                    ('**{0}'.format(repr(self.kwargs).replace('\n', indent)),)
                    if self.kwargs else ()
                )
            )
        )

    def __call__(self, **kwargs):
        return self.s_eval(kwargs)

    def __pos__(self):
        return S(quasiquote, self)

    def uncons(self):
        """
        separates the function part from the args part, and returns them as a tuple.
        >>> S(Print,1,2,3,sep=':').uncons()
        (<built-in function print>, S(1,
          2,
          3,
          **{'sep': ':'}))
        """
        return self.args[0], S(*self.args[1:], **self.kwargs)

    def unkwons(self):
        """
        splits off an arbitrary kwarg as a kv-tuple, and returns them as a tuple
        >>> S(Print,1,2,3,sep=':').unkwons()
        (('sep', ':'), S(<built-in function print>,
          1,
          2,
          3))
        """
        cdr = dict(self.kwargs)
        car = cdr.popitem()
        return car, S(*self.args,**cdr)


def concat(*sexprs):
    return S(*chain.from_iterable(s.args for s in sexprs),
             **dict(chain.from_iterable(s.kwargs.items() for s in sexprs)))

def cons(func, sexpr):
    """
    inserts a function for an argument-only S-expression.
    Can also build up arguments one-by-one.
    >>> cons(Print,cons(1,cons(2,None)))
    S(<built-in function print>,
      1,
      2)
    """
    if sexpr:
        return S(func,*sexpr.args,**sexpr.kwargs)
    return S(func)

def kwons(k, v, sexpr):
    """
    inserts a keyword argument into an S-expression.
    >>> kwons('sep',':',S(Print,1,2))()
    1:2

    symbols also work.
    >>> kwons(S.sep,':',S(Print,1,2))()
    1:2

    remember to quote to prevent early evaluation in S-expressions.
    >>> S(kwons,+S.sep,':',+S(Print,1,2))()()
    1:2
    """
    d = dict(sexpr)
    d[k] = v
    return SExpression.from_mapping(d)


@macro
def quasiquote(sexpr):
    r"""
    Used for code templates, especially in macros.

    Unquote undoes a quasiquote.
    >>> S(quasiquote, ~S.a)(a=42)
    42

    quasiquote acts like quote if there's no unquoting
    >>> S(quasiquote, S.a)()
    S.a

    used as a template.
    >>> S(quasiquote, S(Print,1,~S.a,~S.b))(a=2,b=3)
    S(<built-in function print>,
      1,
      2,
      3)
    >>> S(quasiquote, S(Print,1,~S.a,~S.b))(a=2,b=3)()
    1 2 3

    The + acts as a quasiquote on S-expressions.
    The - is a splicing unquote, for complex macro templates.
    >>> template = (
    ...     +S(Print,
    ...        -+S(1,~S.a,~S.b,sep=':'),  # templates may contain templates.
    ...        4,
    ...        -+S(end=~S.end),  # order is irrelevant for kwarg splicing.
    ...        5)
    ... )
    >>> template(a=2,b=3,end='$\n')()
    1:2:3:4:5$
    >>> template(a=20,b=30,end='$$\n')()
    1:20:30:4:5$$

    unquote also works on keyword arguments.
    >>> S(quasiquote, S(Print,1,2,sep=~S.sep))(sep=':')()
    1:2

    """
    if isinstance(sexpr, SExpression) and sexpr:
        if sexpr.args:
            car, cdr = sexpr.uncons()
            # ? `~X ; (quasiquote (unquote X))
            # -> X
            if car == unquote:
                return cdr[0]
            # ? `(~@(X Y Z) . cdr) ; (quasiquote ((splice-unquote (X Y Z)) . cdr))
            # -> (X Y Z . `cdr) ; (concat (X Y Z) (quasiquote cdr))
            if isinstance(car,SExpression) and car[0] == unquote_splice:
                # todo: support arbitrary maps/iterables
                return S(concat,car[1],quasiquote(cdr))
            # ? `(car . cdr) ; (quasiquote (car . cdr))
            # -> '(`car . `cdr) ; (cons (quasiquote car) (quasiquote cdr))
            return S(cons, quasiquote(car), quasiquote(cdr))
        if sexpr.kwargs:
            (k,v), cdr = sexpr.unkwons()
            return S(kwons, k, quasiquote(v), quasiquote(cdr))
    else:
        # ? `X ; (quasiquote X)
        # -> 'X ; (quote X)
        return S(quote, sexpr)

class unquote(object):
    r"""
    unquotes an element in a quasiquoted S-expression. Usually written as ~S...

    unquote works on S-expressions and Symbols, in any position in a quasiquoted form.
    >>> from drython.macros import *
    >>> from operator import add
    >>> sexp = S(do,
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
    >>> sexp.args  # atoms appear in the same order as written
    (<built-in function print>, 1, 42, 3)
    >>> sexp.kwargs == dict(sep=':',end='$\n')  # kwargs also work!
    True
    >>> sexp()  # the function position too.
    1:42:3$
    """
    def __init__(self, item):
        raise TypeError("unquote outside of quasiquote for unquoted %s" % repr(item))

    # @staticmethod
    # def s_on_unquote(item, scope, level):
    #     if level == 0:
    #         return (item,), Empty
    #     args, kwargs = try_unquote(item, scope, level-1)
    #     return (S(unquote, ))



def unquote_splice(item):
    r"""
    inserts arguments into a quasiquoted form. Usually written as -S...

    generally works on iterables.
    >>> from drython.macros import *
    >>> args = (1,2,3)
    >>> sexp = S(do,+S(Print, 0.0, -S.args, 4.4)).s_eval(globals())
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
    >>> S(do,S(setq,S.x,+S(1,2,3,sep=':')),
    ...   +S(Print, 0.0, -S.x, -S(entuple, 44,55), 6.6, end='$\n'))()()
    0.0:1:2:3:44:55:6.6$

    this is because an S-expression is a Mapping.
    int keys are the args, str keys are the kwargs.
    >>> S(do,
    ...   S(setq,S.x,{0:1,1:2,'end':'$\n'}, S.sep, ':'),  # store a dict in variable S.x
    ...   +S(-+S(Print,0),  # quote to use sexpr as mapping and unquote_splice it
    ...      -+S(sep=~S.sep),  # kwargs don't have to be at the end.
    ...      -S.x,  # evaluates to the dict
    ... ))()()  # eval the do, then the do's result
    0:1:2$
    >>> S(do,+S(Print,11,-+S(0, 42,  sep=~S(add,':',':')),33))()()
    11::0::42::33

    double unquoting
    >>> S(do,+S(do,+S(Print, ~~S.items)))(items=(1,2,3))
    """
    raise TypeError("unquote splice outside of quasiquote for spliced %s" % repr(item))



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
    _gensym_counter = Atom(0)

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

        def __pow__(self, mapping):
            return SExpression.from_mapping(mapping)

        def __getattribute__(self, attr):
            return Symbol(attr)

    return SSyntax()


S = _private()
del _private


def flatten_sexpr(sexpr):
    """
    recursively return all values in an S-expression as a list.
    """
    res = []
    for v in sexpr.values():
        if isinstance(v, SExpression):
            res.extend(flatten_sexpr(v))
        else:
            res.append(v)
    return res
