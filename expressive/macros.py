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

"""


__author__ = 'Matthew Egan Odendahl'


from sexpression import S, try_eval


def macro(func):
    """
    Marks the func as a macro.
    In S-expressions, macros are given any S-expressions
    unevaluated, then the result is evaluated.
    """
    func.__macro__ = None
    return func


@macro
def LAMBDA(scope, symbols, body):
    """
    >>> from operator import add
    >>> plus = S(LAMBDA,(S.x,S.y),S(add,S.x,S.y))
    >>> S(plus,40,2).eval()
    42
    >>> S(plus,20,4).eval()
    24
    """
    def res(*vals,**kwvals):
        # new local scope based on current scope
        local = dict(scope)
        # update with arguments
        local.update({s.data:v for s, v in zip(symbols, vals)})
        return body.eval(local)
    return res


@macro
def IF(scope, B, Then, *rest):
    if try_eval(B, scope):
        return Then
    if len(rest) == 0:
        return None
    if len(rest) == 1:
        return rest[0]
    return IF(*rest)


@macro
def DOT(scope, obj, *names):
    """
    attribute and index/key access macro
    >>> 'quux'[-1]
    'x'
    >>> S(DOT,'quux',[-1]).eval()
    'x'
    >>> ['foo','bar','baz'][1][-1]
    'r'
    >>> S(DOT,['foo','bar','baz'],[1],[-1]).eval()
    'r'
    >>> str.join
    <method 'join' of 'str' objects>
    >>> S(DOT,str,S.join).eval()
    <method 'join' of 'str' objects>
    """
    res = obj
    for n in names:
        res = res[n[0]] if isinstance(n, list) else getattr(res, n)
    return res


def _private():
    _sentinel = S(None)  # used only for is check

    @macro
    def THREAD(scope, x, first=_sentinel, *rest):
        # TODO: doctest THREAD
        if first is _sentinel:
            return x
        return THREAD(S(first.func,x,*first.args,**first.kwargs),*rest)

    @macro
    def THREAD_TAIL(scope, x, first=_sentinel, *rest):
        # TODO: doctest THREAD_TAIL
        if first is _sentinel:
            return x
        return THREAD(S(first.func,*(first.args+(x,)),**first.kwargs),*rest)

    return THREAD, THREAD_TAIL

THREAD = None
THREAD_TAIL = None
THREAD, THREAD_TAIL = _private()
del _private

@macro
def AND(scope, first=True, *rest):
    """
    returns the first false argument. Shortcuts evaluation of the
    remaining S expressions.
    >>> S(AND).eval()
    True
    >>> S(AND,'yes').eval()
    'yes'
    >>> S(AND,False).eval()
    False
    >>> S(AND,S(str,1),True,"yes",S(print,'shortcut?'),S(print,'nope')).eval()
    shortcut?
    """
    first = try_eval(first, scope)
    if not rest:
        return first
    if not first:
        return first
    return AND(scope, *rest)

@macro
def OR(scope, first=None, *rest):
    """
    returns the first true argument. Shortcuts evaluation of the
    remaining S expressions.
    >>> S(OR).eval()
    >>> S(OR,'yes').eval()
    'yes'
    >>> S(OR,[]).eval()
    []
    >>> S(OR,[],'yes').eval()
    'yes'
    >>> S(OR,[],'',False,S(print,'shortcut?'),'yes?',S(print,'nope')).eval()
    shortcut?
    'yes?'
    """
    first = try_eval(first, scope)
    if not rest:
        return first
    if first:
        return first
    return OR(scope, *rest)


if __name__ == "__main__": import doctest; doctest.testmod()
