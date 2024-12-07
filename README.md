# Drython #
**Don't-Repeat-Yourself Python**

Drython is a metaprogramming library for Python.
Metaprogramming is writing programs that write programs--a
powerful technique for abstracting away repetitive code.

Programmers make abstractions constantly. Functions are abstractions. Classes are abstractions.
But sometimes it's not enough.
If you find yourself writing boilerplate "design patterns" again and again,
then you're not using powerful enough abstractions.
You need metaprogramming.

## Metaprogramming ##

Often, the metaprogramming technique involves creating a miniature domain-specific language (DSL),
tailor-fit to the problem at hand. One might think the addition of a DSL makes the program harder
to understand, but if it makes the program a tenth as long as it would have been without it,
(not unusual), then it's worth it.

Python already includes some metaprogramming facilities.
Using decorators to modify functions is a limited example.
Using metaclasses to rewrite class declarations is a more powerful example.

But Python has more general metaprogramming capabilities.
The secret to metaprogramming is treating code as just another kind of data.
(The DRY principle applies to any kind of data, *especially* the executable kind.)

For example, Python can write text files, including .py files, which it can then import as modules.

Any programming language with access to the filesystem and a compiler could theoretically do this.
Python can also create strings, including strings containing Python code, which it can execute with
the `exec()` function.
Sometimes this approach is appropriate, indeed,
some of the Python standard library (like namedtuple) uses this technique.
But manipulating text as Python code can be difficult and error-prone.
Compiling text is also rather slow.

Alternatives to text manipulation include manipulation of Python bytecodes
(not for the faint of heart),
and manipulation of abstract syntax trees using the `ast` module, which is arcane, but usable:
```Python
import ast
print(ast.dump(ast.parse(r'''print("Hello, World!")''')))
# Module(body=[Expr(value=Call(func=Name(id='print', ctx=Load()), args=[Str(s='Hello, World!')], keywords=[], starargs=None, kwargs=None))])
```
Reading AST is easier than writing it (malformed AST can segfault CPython),
but if it took that much for a simple `print('Hello, World!')`,
you can imagine it gets complex fast.
Unfortunately, bytecode and abstract syntax trees are implementation details subject to change
between Python versions and implementations.

There's an easier way. Drython provides *executable* data structures that are both simpler than AST,
and are easier to work with than text.
Drython specifically avoids using ast and bytecode manipulation,
so it's portable across implementations, including CPython2.7/3.1+, PyPy, Jython, and IronPython.

## The Statement Module ##

Can you re-implement a simple if-statement in Python?
I mean without writing a text compiler or interpreter, or modifying Python itself?
Sure, you don't have to, Python has a perfectly good if statement already, but can you?

A DSL might need a three-way numeric if statement (-/+/0), or something like a switch/case.
Yes, you can use the boilerplate cascading-elif pattern instead
for any of your complex branching needs, but that's not an abstraction, is it?
You have to re-write the logic imitating the switch/case (or what-have-you)
**every single time**.
If you can't make a simple `if` substitute,
how can you expect to make more advanced language components you might need for a DSL?

You might not think Python can do it, but it's actually trivial in Smalltalk.
"If" isn't a statement in Smalltalk to begin with.
It's a method. On the booleans.

```Smalltalk
result := a > b
    ifTrue:[ 'greater' ]
    ifFalse:[ 'not greater' ]
```

The `:=` is just an assignment (like Python's `=`).
The `a > b` part evaluates to either true or false, just like Python.
The `[]` isn't a list; it's a **code block**.
The true boolean has an `ifTrue:ifFalse:` method that always executes the then-block,
but false has a different method *with the same name* that only executes the else-block. Polymorphic dispatch.
Is that cool or what? Yes, `ifTrue:iffasle:` is one method, not two. An interesting quirk of Smalltalk is that
the arguments can go inside of the method name. There are also completely separate `ifTrue:` and
`ifFalse:` methods that take one argument each.

We can achieve a very similar effect in Python.
You can't modify builtins, but a method is just a function that takes the instance as its first
argument, which by convention we call `self`.


```Python
result = (lambda self, *, ifTrue=None, ifFalse=None: ifTrue if self else ifFalse)(
a > b,
    ifTrue='greater',
    ifFalse='not greater',
)
```

But there's a problem. This only works on values. What if we want effects?

```Python
(lambda self, *, ifTrue=None, ifFalse=None: ifTrue if self else ifFalse)(
a > b,
    ifTrue=print('greater'),
    ifFalse=print('not greater'),
)
```

Clearly, this won't work! It prints *both* messages, since the print functions get evaluated before the if lambda
can do anything about it.

Smalltalk uses the code blocks to prevent evaluation.
Too bad Python doesn't have those blocks things, or re-implementing `if` would be easy. Or does it?

Actually, a code block is just an anonymous function.
Python could do something similar with `def`.

```Python
my_if = lambda self, *, ifTrue=None, ifFalse=None: (ifTrue if self else ifFalse)()

def anon_1():
    print('greater')

def anon_2():
    print('not greater')

my_if(a > b,
    ifTrue=anon_1,
    ifFalse=anon_2,
)
```

But these functions are passed by name, so they're not really anonymous, are they?
The code is also not inside the control "statement" anymore, so it's kind of harder to read.

You could implement `ifTrue:` as a decorator instead,
```Python
>>> iftrue = lambda b: lambda f: f() if b else None
>>> @iftrue(10 > 5)
... def result():
...     print("was true")
...     return "greater"
was true
>>> result
'greater'

```
Notice that a decorator doesn't *have* to return a wrapped function.
In this case it called its function to return a string instead of wrapping it.
Python's decorators can only take one argument (the function `result` above),
so how could we possibly also pass in a boolean (the expression `10 > 5`)?
This is possible using a common Python trick:
use a factory function (`iftrue`) to create a *new* decorator with the arguments already built in--on the fly.
That's why there's a double lambda. It's the inner lambda that got the `result` function.
Drython's `core` module has a `decorator` decorator to simplify this process:
```Python
>>> from drython.core import decorator
>>> @decorator
... def iftrue(block, boolean):
...     if boolean:
...         return block()
...
>>> @iftrue(10 > 5)
... def result():
...     print("was true")
...     return "greater"
...
was true
>>> result
'greater'

```
But how do you pass in a second function for `ifTrue:ifFalse:`? Not possible?
You actually *can* do this with decorators, you just need to decorate *two* functions.
But decorators only accept one function, right? Just combine them with a class and decorate that.
You don't even need an instance if you get the functions directly from the class dict:
```Python
>>> @decorator
... def decr_if(blocks, boolean):
...     blocks = vars(blocks)
...     if boolean:
...         return blocks['iftrue']()
...     else:
...         return blocks['iffalse']()
>>> @decr_if(10 > 5)
... class result:
...     def iftrue():  # no self
...         print("was true")
...         return "greater"
...     def iffalse():
...         print("wasn't true")
...         return "not greater"
was true
>>> result
'greater'

```
Decorators are pretty useful.

As an aside, you don't even have to access the function directly from the class dict in Python 3.
The function doesn't have any args (no `self`), so it doesn't get converted to a method (unlike Python 2)
so without reassigning `blocks` you can access raw functions via a dot as normal, like
```Python
return blocks.iftrue()
```
Drython's core module has an `attrs` class that lets you access a dictionary via dot syntax (like in Lua), so you could
also do this in Python 2 if you instead use the line
```Python
blocks = attrs(vars(blocks))
```

You could easily implement the 3-way if like this.
But how would you implement a control strucure that takes an arbitrary number of blocks,
like switch/case, with decorators? Not so easy, right?

We need real, inline, anonymous functions. Python does have those though, with `lambda`.
```Python
my_if(a > b,
    iftrue=lambda: print('was true'),
    iffalse=lambda: print("wasn't true"),
)
```
Much prettier. Too bad `lambda` only gets one line, or this might actually work.

Actually, with Drython, it does work.

What if you had an expression that contained multiple expressions,
and executed them one-by-one in order?
Wouldn't lambda be a lot more useful?

You do. It's a tuple. Think of the commas as semicolons and you get the idea.

What if you just want to return the value of the last expression,
instead of a tuple of all of them?
Declare a tuple and immediately index it. `(...)[-1]`
Drython's `do` function does exactly this, and also doesn't crash if its `args` tuple is empty.

```Python
>>> from drython.statement import do, Print
>>> my_if = lambda self, iftrue=None, iffalse=None: (iftrue if self else iffalse)()
>>> result = my_if(10 > 5,
...              iftrue=lambda: do(
...                  Print('was true'),
...                  'greater',
...              ),
...              iffalse=lambda: do(
...                  Print("wasn't true"),
...                  'lesser',
...              ),
...          )
was true
>>> result
'greater'

```
It's no worse than the decorator version in terms of length, but this version is an *expression*.
That means you can put the whole thing in a function call or a lambda body and it still works,
unlike the decorator version, which is made of *statements*.

A control structure could also take an arbitrary number of lambdas using a `*args` parameter to make more complex
things like a switch/case. This is much more difficult with decorators.

Unfortunately, lambdas in Python can't contain *statements*,
so even with `do` they can't work as general code bocks, right?

With Drython's `statement` module, they *can*.

The statement module contains expression substitutes for every
Python reserved word that isn't already an expression or doesn't have an expression equivalent.
They work in lambdas.
They work in `eval`.
They're pretty handy in Drython's executable data structures,
which therefore don't need to handle statement code.
This makes them a lot simpler than AST, and therefore easier to use.

Ready to write that three-way if?

You've just learned new metaprogramming abstractions.
You can extend Python's syntax without changing the grammar and write your DSL in that.
No need to write your own compiler or interpreter, because it's still just Python.
Ready for the next step?

## The Stack Module ##

`Def`, from Drython's `stack` module, is an alternative way to write anonymous functions.
It is an executable data structure in the tradition of stack languages like Forth,
Factor, and Joy.

A `Stack` represents a composition of special
functions called *stack combinators* and their associated data.

Because stack combinators must accept a stack and return a stack, they are easy to combine into new
combinators, just by listing them one after another.
Combinators execute immediately when pushed on a stack.
Typically they pop some arguments off the stack and push the result on the return stack

Any Python callable (Including the `statement` module's callables!)
is interpreted as a stack combinator.
By default that takes one iterable off the stack as arguments, and pushes the result.
```Python
>>> from drython.stack import Stack
>>> Stack([1,2,3],Print)
1 2 3
Stack(None,)

```
Or, if the top element is a mapping, then a default combinator will take the top two elements,
using the mapping for the keyword arguments.
```Python
>>> Stack([1,2,3],dict(sep='::'),Print)
1::2::3
Stack(None,)

```
You can, of course, call a function with no arguments if the iterable on top is empty.
An empty mapping is likewise harmless, but the iterable is required.

A callable decorated with `@combinator` doesn't use this default conversion and
must explicitly accept and return a stack object. This gives it access to every item on the stack,
but it's rare to use more than the top four, and uncommon to even use four.

Drython's `combinator` module has many of these nondefault combinators,
including all possible stack permutation functions of depth four or less.
The code that generates them is an interesting example of Python's string metaprogramming. Check it out.

It's easy to see what stack programs are doing by using `Stack.trace`.
This is just like `Stack.push`, but it prints every step.
Here's an example with the `dup` and `bi` combinators
```Python
>>> from drython.stack import *; from drython.combinator import *; from operator import mul
>>> Stack(3).trace(dup,bi,mul)  # duplicate, then binary multiply
Stack(3,) << dup
Stack(3, 3) << bi
Stack((3, 3),) << <built-in function mul>
Stack(9,)

```
Here, `mul` is an ordinary Python function with the default interpretation.

The `Def` constructor takes a stack program, that is, a sequence of combinators (and any associated data).
The resulting function (a callable instance of `Def`) uses a stack internally.
The internal stack initiallay has the args tuple and kwargs dict (in that order), from the function call.
So a call like `x(1,2,foo=3)` results in `Stack((1,2,),{'foo':3})` initially.
Then the `Def` call pushes its combinator sequence onto this argument stack, and returns the top element that results.

You can get at the `(1, 2)` arguments using the `pop` combinator (which removes the top element) and the
very important `Ic` (I-combinator), which dumps an iterable's elements on the stack.
```Python
>>> Stack((1,2),{'foo':3}).trace(pop,Ic)
Stack((1, 2), {'foo': 3}) << pop
Stack((1, 2),) << Ic
Stack(1, 2)

```
A nice thing about stack combinators is that you can copy-paste entire phrases and it mostly just works.
Only the *top* of the stack has to match up.
We can combine these two traced programs with `Def` to get a working `square` function.
```Python
>>> square = Def(pop,Ic,dup,bi,mul)
>>> square(4)
16
>>> square.trace(4)
Stack((4,), {}) << pop
Stack((4,),) << Ic
Stack(4,) << dup
Stack(4, 4) << bi
Stack((4, 4),) << <built-in function mul>
Stack(16,).peek()
16
>>> square(7)
49
>>> square  # unlike an ordinary Python function, the repr is readable.
Def(pop, Ic, dup, bi, <built-in function mul>)
>>> square[0]  # a Def is a type of tuple
pop
>>> square[2:-1]
(dup, bi)

```

You can create new combinators from phrases of existing combinators (instead of from scratch with `@combinator`)
by using `@Phrase`
```Python
>>> @Phrase(pop,Ic)
... def pic(): """ for starting a simple Def, ignores kwargs and dumps args on the stack"""
>>> @Phrase(bi,mul)
... def mul2(): """ multiples the top two elements and pushes the result. """

```
Now you can use them in new stack programs
```Python
>>> cube = Def(pic,dup,dup,mul2,mul2)
>>> cube(3)
27
>>> cube
Def(pic, dup, dup, mul2, mul2)

```
The astute reader may wonder why we've gone back to decorators when we went to so much trouble to make everything an expression.
It seems like a step backwards.
Shouldn't we make a way to make anonymous functions from phrases from within a stack program?

The `@Phrase` decorator is just used for phrases with docstrings declared at the top level of a module.
You actually already have anonymous function capability:
Compose a list of combinators on the stack. That's it. That's your anonymous function.
Invoke it with `Ic`.
If you can manipulate lists of combinators programmatically, *then you can write stack programs programmatically.*
This is metaprogramming. Code that writes code.

These lists are a kind of quoted program. Some combinators take such programs as arguments.
This is similar to the way Smalltalk takes code blocks, so control structures (and therefore DSLs)
can be implemented as combinators in an analogous way.
See the `ifte` combinator in the `stack` module's companion `combinators` module for a familiar example.

## s-expressions ##

Tired of writing `lambda ...: let(lambda:do(...,Return()))` when you just needed an anonymous
function?
Sure, stack programs are a powerful alternative to lambda, but they can't introduce new variables like lambda can.
That sure sounds like a boilerplate code problem.
You need better abstractions again.

Wouldn't it be easier if you could write functions that get their arguments unevaluated?
Then you wouldn't need to wrap everything in lambdas.
Lisp can do it with macros. Python can do it too, with Drython.

An s-expression represents a function *call*.
You create an s-expression instance with a function and its arguments.

```Python
>>> from drython.s_expression import S
>>> S(Print, "Hello,", "World!")
S(<built-in function print>,
  'Hello,',
  'World!')

```

But the call doesn't happen until you invoke its `s_eval()` method,
at which point it calls `s_eval()` on all its s-evaluable arguments
(typically nested s-expressions), and then applies the function to the results.

With this recursive evaluation and the statement replacements from the statement module,
it is possible to write entire programs as nested s-expressions.
Think of s-expressions as a simpler kind of abstract syntax trees.

```Python
>>> S(Print, S("Hello,".upper), S("World!".lower)).s_eval({})
HELLO, world!

```

Note the dictionary in the `s_eval` call.
s-expressions have their own scope for delayed evaluation of `Symbol`s.
For a module-level s-expression, you might want to pass in the `globals()`,
which will make them available as the equivalent symbol.
```Python
>>> from drython.macro import setq
>>> spam = 7
>>> S(Print, S.spam).s_eval(globals())  # S.spam is the same as Symbol('spam')
7
>>> S(setq, S.spam, 42).s_eval(globals())  # globals() is writable.
>>> spam
42

```

You can also use an s-expression as a kind of lambda. Calling one directly will call `s_eval` with
the kwargs dict.

```Python
>>> S(Print, S.x, S.y, 3, sep=S.sep)(x=1, y=2, sep=':')
1:2:3

```

If the s-expression's function is a *macro*,
then it gets any s-evaluable arguments unevaluated,
and returns (typically) an s-evaluable for evaluation.
In other words, macros can re-write code.

So you can define "if" like this:

```Python
@macro
def If(boolean, then, Else=None):
    return S(s_eval,
             S((Else, then).__getitem__,
               S(bool,
                 boolean)))
```

The above macro rewrites the code into an s-expression that indexes a pair (2-tuple)
using the test part coerced into a boolean,
(remember `True == 1` and `False == 0` in Python) and then `s_eval`s the selected s-expression.

S-expression macros are a very powerful metaprogramming technique.
Especially powerful once you start using macros to write macros.
It's Lisp's "secret sauce".
And they're great for creating DSLs.

The s-expression module has a companion `macros` module which
includes many useful basic macros to get you started.

## The Expression Module ##
The expression module has a generator expression replacement, and an experimental `yield` replacement.

Unlike statements, expressions already work in lambdas and eval,
so why replace them too?

Besides being easier to use with higher-order functions, the `stack`
and `s-expression` modules work primarily with function calls, so these
substitutes have uses in metaprogramming. In many cases you can use
expressions directly anyway, or convert a non-call expression to a
call with a lambda, but sometimes you need to manipulate the code of
the expression itself, in which case it must be made of calls to
begin with.

Direct use acts like a constant in s-expressions (like a Lisp reader macro),
since it's evaluated before even macros can get to it.
```Python
>>> from core import identity, entuple
>>> from s_expression import S
>>> S(identity,[(x,y) for x in (1,2) for y in 'abc'])()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

```
On the other hand, the `lambda` version is adjustable with arguments at eval time.
```Python
>>> S(lambda z:[(x,y) for x in (1,2) for y in z],'abc')()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

```
This is the function call version of the above using `expression.In`
```Python
>>> from drython.expression import In
>>> S(list,
...   S(In,(1,2),S(L1,S.x,
...       S(In,'abc',S(L1,S.y,
...           S(entuple,S(entuple,S.x,S.y)))))))()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

```
Why use the function call version when it's so much harder? Besides
the new `expression.whilst` feature, the main advantage here is that you can
simplify it with a macro.
```Python
>>> from s_expression import macro
>>> from macro import L1
>>> @macro
... def genx(expr,*specs):
...     if specs:
...         return S(In,specs[1],S(L1,specs[0],S(genx,expr,*specs[2:])))
...     else:
...         return S(entuple,expr)

```
Now we've got generator s-expressions with arguments in familiar
Python order.
```Python
>>> S(list,
...   S(genx, S(entuple, S.x, S.y), S.x, (1, 2), S.y, 'abc'))()
[(1, 'a'), (1, 'b'), (1, 'c'), (2, 'a'), (2, 'b'), (2, 'c')]

```
A more advanced macro could include Python's other features like `if`
filters and unpacking. But more importantly, since you can
metaprogram this, you can add new features in the macro that raw
Python lacks, like whilst.

