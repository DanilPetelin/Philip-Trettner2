# Copyright 2015, 2016 Matthew Egan Odendahl
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

    from drython.s_expression import S, _S

S is a prefix for both symbols and s-expressions
Symbol: `S.foo`,
S-expression: `S(Print,'foo')`.
Quote with `-`.
`_S(foo)` is an alias for `S(quasiquote, S(foo))`.
The `~` unquotes as in Clojure; `+` unquotes and splices.
"""
# s_expression may safely depend on .core and .statement

from __future__ import absolute_import, division
from itertools import chain, count
from keyword import iskeyword
from operator import add
from collections import Mapping
import logging as lg

lg.basicConfig(filename='s_expression.py',
               # level=lg.DEBUG,
               )
import sys

import collections

from drython.core import SEvaluable

if sys.version_info[0] == 2:
    # noinspection PyUnresolvedReferences,PyCompatibility
    from UserString import UserString
else:
    from collections import UserString

from drython.core import Empty, entuple, edict
from drython.statement import Atom, Raise, Print


# defines an interface used by SExpression, so belongs here, not in macro.py
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

    def __pos__(self):
        return S(unquote_splice, self)


class SQuotable(SUnquotable):
    def __neg__(self):
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
    except LookupError:
        pass
    if isinstance(data, Mapping):
        kwargs = {k: v for k, v in data.items() if not isinstance(k, int)}
    return args, kwargs


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


class SExpression(Mapping, SEvaluable, SQuotable):
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
    >>> spam.s_eval({})  # same as add(20,4)
    24
    >>> spam()  # S-expressions are also callable
    24

    represents add(mul(4, 10), 2)  # 4*10 + 2
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
    >>> from drython.macro import If
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
                lg.debug("expanding macro...\n%s\n", self)
                element = func(*self.args[1:], **self.kwargs)
                lg.debug("...sexpr headed by [%s] reports macro expanded to:\n%s\n", self[0], element)
                return s_eval_in_scope(element, scope)
            return func(
                # generators CAN Unpack with *,
                # but they mask TypeError messages due to Python bug!
                # so we make it a tuple for better errors.
                *tuple(s_eval_in_scope(a, scope) for a in self.args[1:]),
                **{k: s_eval_in_scope(v, scope) for k, v in self.kwargs.items()})
        except BaseException as be:
            Raise(SExpressionException('when evaluating\n' + repr(self)), From=be)
            # finally:
            #     pass

    # def __repr__(self):
    #     return "S(*"+repr(self.args)+", **"+repr(self.kwargs)+")"
    def __repr__(self):
        if len(self.args) == 2 and len(self.kwargs) == 0:
            if self[0] == quasiquote and (isinstance(self[1], SExpression) or isinstance(self[1], Symbol)):
                return '_' + repr(self[1]).replace('\n', '\n ')
            if self[0] == quote and isinstance(self[1], SQuotable):
                return '-' + repr(self[1]).replace('\n', '\n ')
            if self[0] == unquote_splice and isinstance(self[1], SUnquotable):
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
        kwar = cdr.popitem()
        return kwar, S(*self.args, **cdr)


def concat(*data):
    """
    Combines argument data, both positional and keyword, into an S-expression.
    >>> data = (S(1,2,3),S(4,5,6,foo=7),dict(bar=8, baz=88),(9,10,11))
    >>> concat(*data).args
    (1, 2, 3, 4, 5, 6, 9, 10, 11)
    >>> concat(*data).kwargs == dict(foo=7, bar=8, baz=88)
    True
    """
    lg.debug("concat:%s", data)
    args, kwargs = zip(*map(args_kwargs, data))
    return S(*(chain.from_iterable(args)), **{k: v for d in kwargs for k, v in d.items()})


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
        return S(func, *sexpr.args, **sexpr.kwargs)
    return S(func)


def kwons(k, v, sexpr):
    """
    kwarg cons. Inserts a keyword argument into an S-expression.
    >>> kwons('sep',':',S(Print,10,20))()
    10:20

    symbols also work as keywords.
    # >>> kwons(S.sep,':',S(Print,10,20))()
    10:20

    explicit positional index also works.
    >>> kwons(2,'twenty',S(Print,10,20))()  # replace a positional argument
    10 twenty
    >>> kwons(3,30,S(Print,10,20))()  # next positional argument
    10 20 30
    >>> kwons(0,entuple,S(Print,10,20))()  # replace Print at index 0
    (10, 20)

    remember to quote symbols to prevent early evaluation in S-expressions.
    # >>> S(kwons,-S.sep,':',_S(Print,10,20))()()
    10:20
    """
    # TODO: make symbols work?
    d = dict(sexpr)
    d[k] = v
    return SExpression.from_mapping(d)


def make_sexpr(*args, **kwargs):
    return S(*args, **kwargs)


@macro
def quasiquote(sexpr):
    r"""
    Used for code templates, especially in macros.

    Unquote undoes a quasiquote.
    >>> S(quasiquote, ~S.a)(a=42)
    42

    quasiquote can act like quote on s-evaluation
    >>> _S.a()  # same as S(quasiquote, S.a)()
    S.a
    >>> (-S.a)()  # normal quote `-`; same as S(quote, S.a)()
    S.a

    used as a template.
    >>> _S(Print,1,~S.a,~S.b)(a=2,b=3)
    S(<built-in function print>,
      1,
      2,
      3)
    >>> _S(Print,1,~S.a,~S.b)(a=2,b=3)()
    1 2 3

    unquote even works on keyword arguments.
    >>> _S(Print,1,2,sep=~S.sep)(sep=':')()
    1:2

    The _S is a quasiquoted S-expression.
    The + is a splicing unquote, for complex macro templates.
    >>> template = (
    ...     _S(Print,
    ...        +_S(1,~S.a,~S.b,sep=':'),  # templates may contain templates.
    ...        4,
    ...        +_S(end=~S.end),  # order is irrelevant when splicing in kwargs.
    ...        5)
    ... )
    >>> template(a=2,b=3,end='$\n')()
    1:2:3:4:5$
    >>> template(a=20,b=30,end='$$\n')()
    1:20:30:4:5$$

    splicing also works on symbols.
    >>> _S(Print,+S.args)(args=S(1,2,3,sep=':'))()
    1:2:3
    """
    # if isinstance(sexpr, SExpression) and sexpr:
    #     if sexpr.args:
    #         car, cdr = sexpr.uncons()
    #         # ? `~X ; (quasiquote (unquote X))
    #         # -> X
    #         if car == unquote:
    #             return cdr[0]
    #         # ? `(~@(X Y Z) . cdr) ; (quasiquote ((splice-unquote (X Y Z)) . cdr))
    #         # -> (X Y Z . `cdr) ; (concat (X Y Z) (quasiquote cdr))
    #         if isinstance(car,SExpression) and car[0] == unquote_splice:
    #             return S(concat, car[1], quasiquote(cdr))
    #         # ? `(car . cdr) ; (quasiquote (car . cdr))
    #         # -> '(`car . `cdr) ; (cons (quasiquote car) (quasiquote cdr))
    #         return S(cons, quasiquote(car), quasiquote(cdr))
    #     if sexpr.kwargs:
    #         (k,v), cdr = sexpr.unkwons()
    #         return S(kwons, k, quasiquote(v), quasiquote(cdr))
    # else:
    #     # ? `X ; (quasiquote X)
    #     # -> 'X ; (quote X)
    #     return S(quote, sexpr)
    lg.debug("quasiquoting:\n%s", sexpr)
    return qq_expand(sexpr)


def qq_step(x):
    lg.debug("qq_step:\n%s", x)
    if not x:
        lg.debug("qq_step got %s, aborting.", x)
        return x
    if x.args:  # not a tag. Step through list.
        car, cdr = x.uncons()
        lg.debug("qq_step unconsed (%s . %s)", car, cdr)
        lg.debug("qq_step splicing")
        splice = qq_splice(car)
    elif x.kwargs:
        kwar, cdr = x.unkwons()
        lg.debug("qq_step unkwonsed (%s : %s)", kwar, cdr)
        lg.debug("qq_step splicing")
        splice = S(edict, kwar[0], qq_expand(kwar[1]))
    lg.debug("qq_step expanding")
    expand = qq_expand(cdr)
    lg.debug("qq_step concatenating")
    out = S(concat, splice, expand)
    lg.debug("qq_step return:\n%s", out)
    return out


def qq_expand(x):
    lg.debug("qq_expand:\n%s", x)
    if isinstance(x, SExpression):
        if len(x.args) == 2:  # might be a tag, let's check
            tag, data = x[0], x[1]
            if tag == unquote:
                lg.debug("qq_expand found unquote; return:\n%s", data)
                return data
            if tag == unquote_splice:
                raise SExpressionException("Naked splice")
            if tag == quasiquote:
                lg.debug("qq_expand found quasiquote...")
                out = qq_expand(qq_expand(data))
                lg.debug("...qq_expand found quasiquote; return:\n%s", out)
                return out
        lg.debug("qq_expand no tag in sexpr stepping...")
        out = qq_step(x)
        lg.debug("...qq_expand no tag in sexpr; return:\n%s", out)
        return out
    # must be an atom. Quote it.
    lg.debug("qq_expand found atom <%s>...", x)
    out = S(quote, x)
    lg.debug("...qq_expand found atom; return:\n%s", out)
    return out


# """
# (define (qq-expand x)
#   (cond ((tag-comma? x)
#          (tag-data x))
#         ((tag-comma-atsign? x)
#          (error "Illegal"))
#         ((tag-backquote? x)
#          (qq-expand
#            (qq-expand (tag-data x))))
#         ((pair? x)
#          `(append
#             ,(qq-expand-list (car x))
#             ,(qq-expand (cdr x))))
#         (else `',x)))

def qq_splice(x):
    lg.debug("qq_splice:\n%s", x)
    if isinstance(x, SExpression):
        if len(x.args) == 2:  # might be a tag
            tag, data = x[0], x[1]
            if tag == unquote:
                out = S(make_sexpr, data)
                lg.debug("qq_splice found unquote; return:\n%s", out)
                return out  # no splice. Return to concat in a tuple.
            if tag == unquote_splice:
                lg.debug("qq_splice found unquote_splice; return:\n%s", data)
                return data  # spliced. Return to concat directly.
            if tag == quasiquote:  # nested/next level
                lg.debug("qq_splice found quasiquote...")
                out = qq_splice(quasiquote(data))
                lg.debug("...qq_splice found quasiquote; return:\n%s", out)
                return out
        lg.debug("qq_splice no tag in sexpr stepping...")
        out = S(make_sexpr, qq_step(x))
        lg.debug("...qq_splice no tag in sexpr; return:\n%s", out)
        return out
    # must be an atom. Return to concat in a tuple
    # return x,
    # return S(quote,x),
    lg.debug("qq_splice found atom <%s>...", x)
    out = S(quote, S(x))
    lg.debug("...qq_splice found atom; return:\n%s", out)
    return out


# (define (qq-expand-list x)
#   (cond ((tag-comma? x)
#          `(list ,(tag-data x)))
#         ((tag-comma-atsign? x)
#          (tag-data x))
#         ((tag-backquote? x)
#          (qq-expand-list
#            (qq-expand (tag-data x))))
#         ((pair? x)
#          `(list
#             (append
#               ,(qq-expand-list (car x))
#               ,(qq-expand (cdr x)))))
#         (else `'(,x))))
# """

class unquote(object):
    r"""
    unquotes an element in a quasiquoted S-expression. Usually written as ~S...

    unquote works on S-expressions and Symbols, in any position in a quasiquoted form.
    >>> from drython.macro import *
    >>> from drython.s_expression import *
    >>> sexp = S(do,
    ...          S(setq,
    ...            S.foo,Print,
    ...            S.x,1,
    ...            S.y,':'),
    ...          _S(~S.foo,
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


def unquote_splice(item):
    r"""
    inserts arguments into a quasiquoted form. Usually written as +S...

    generally works on iterables.
    >>> from drython.macro import *
    >>> from drython.s_expression import *
    >>> args = (1,2,3)
    >>> sexp = S(do,_S(Print, 0.0, +S.args, 4.4)).s_eval(globals())
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
    >>> S(do,S(setq,S.x,_S(1,2,3,sep=':')),
    ...   _S(Print, 0.0, +S.x, +S(entuple, 44,55), 6.6, end='$\n'))()()
    0.0:1:2:3:44:55:6.6$

    this is because an S-expression is a Mapping.
    int keys are the args, str keys are the kwargs.
    >>> S(do,
    ...   S(setq,S.x,{0:1,1:2,'end':'$\n'}, S.sep, ':'),  # store a dict in variable S.x
    ...   _S(+_S(Print,0),  # quote to use sexpr as mapping and unquote_splice it
    ...      +_S(sep=~S.sep),  # kwargs don't have to be at the end.
    ...      +S.x,  # evaluates to the dict
    ... ))()()  # eval the do, then the do's result
    0:1:2$
    >>> S(do,_S(Print,11,+_S(0, 42,  sep=~S(add,':',':')),33))()()
    11::0::42::33

    double unquoting
    >>> S(do,_S(do,_S(Print, ~~S.items)))(items=(1,2,3))()()
    (1, 2, 3)

    splice unquoted
    >>> S(do,_S(do,_S(Print, +~S.items)))(items=(1,2,3))()()
    1 2 3
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


class Symbol(SEvaluable, SQuotable, str):
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
            return 'S.' + str(self)
        return 'Symbol(%s)' % repr(str(self))

    def __add__(self, other):
        return Symbol(str.__add__(self,other))

    def s_eval(self, scope=Empty):
        """ looks up itself in scope """
        try:
            return scope[str(self)]
        except KeyError:
            Raise(SymbolError(
                'Symbol %s is not bound in the given scope' % repr(self)
            ), From=None)


# This is just a stub so the IDE can find it.
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
    raise Exception("called gensym stub instead of the real thing.")
    # the real thing is in the private closure below.


def _private():
    _gensym_counter = Atom(0)

    # noinspection PyGlobalUndefined
    global gensym

    __doc__ = gensym.__doc__

    # noinspection PyRedeclaration,PyUnusedLocal
    def gensym(prefix=''):
        return Symbol(
            '<{0}#{1}>'.format(prefix, str(_gensym_counter.swap(add, 1))))

    gensym.__doc__ = __doc__  # keeps the docstring for the repl


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

        # def __getitem__(self, *args):pass

        def __getattribute__(self, attr):
            return Symbol(attr)

    return SSyntax()


S = _private()
del _private


def _private():
    class QqSSyntax(object):
        """
        prefix for creating quasiquoted S-expressions and Symbols.
        see help('drython.s_expression') for further details.
        """
        __slots__ = ()

        def __call__(self, *args, **kwargs):
            return S(quasiquote, S(*args, **kwargs))

        def __pow__(self, mapping):
            return S(quasiquote, SExpression.from_mapping(mapping))

        # def __getitem__(self, *args):pass

        def __getattribute__(self, attr):
            return S(quasiquote, Symbol(attr))

    return QqSSyntax()


_S = _private()
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


__all__ = ['_S'] + [e for e in globals().keys() if not e.startswith('_')]  # if e not in _exclude_from__all__]
