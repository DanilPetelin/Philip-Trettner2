# Drython #
**Or, Don't-repeat-yourself Python**

Drython is a metaprogramming library for Python.
Metaprogramming is writing programs that write programs---a
powerful technique for *abstracting* away repetitive code.

Programmers make abstractions constantly. Functions are abstractions. Classes are abstractions.
But sometimes it's not enough.
If you find yourself writing boilerplate "design patterns" again and again,
then you're not using powerful enough abstractions.
You need metaprogramming.
Don't repeat yourself.
Drython can help.

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
(The DRY principle applies to any kind of data, *especially* the executable kind!)

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

    import ast
    print(ast.dump(ast.parse('''print("Hello, World!")''')))
    # Module(body=[Expr(value=Call(func=Name(id='print', ctx=Load()), args=[Str(s='Hello, World!')], keywords=[], starargs=None, kwargs=None))])

Reading AST is easier than writing it (malformed AST can segfault CPython),
but if it took that much for a simple `print('Hello, World!')`,
you can imagine it gets complex fast.
Unfortunately, bytecode and abstract syntax trees are implementation details subject to change
between Python versions and implementations.

There's an easier way. Drython provides *executable* data structures that are both simpler than AST,
and are easier to work with than text.
Drython specifically avoids using ast and bytecode manipulation,
so it's portable across implementations, including CPython2.7/3.1+, PyPy, Jython, and IronPython.

## Drython's statement module ##

Can you re-implement a simple if-statement in Python?
I mean without writing a text compiler or interpreter, or modifying Python itself?
Sure, you don't have to, Python has a perfectly good if-statement already, but can you?
A DSL might need a three-way numeric if-statement (-/+/0), or something like a switch/case.
Yes, you can use the boilerplate cascading-elif pattern instead
for any of your complex branching needs, but that's not an abstraction, is it?
You have to re-write the logic imitating the switch/case (or what-have-you)
**every single time**.
If you can't make a simple `if` substitute,
how can you expect to make a complex one when you need it?

You might not think Python can do it, but it's actually trivial in Smalltalk.
"If" isn't a statement in Smalltalk to begin with.
It's a method. On the booleans.

```Smalltalk
result := a > b
    ifTrue:[ 'greater' ]
    ifFalse:[ 'not greater' ]
```

The `:=` is just an assignment.
The `a > b` part evaluates to either true or false, just like Python.
The `[]` isn't a list; it's a **code block**.
The true boolean has an `iftrue:iffalse:` method that always executes the then-block,
but false has a different method *with the same name* that only executes the else-block.
Is that cool or what? Yes, `iftrue:iffasle` is one method, not two, an interesting quirk of Smalltalk is that
the arguments can go inside of the method name. There are also completely separate `iftrue:` and
`iffalse:` methods that take one argument each.

We can achieve a very similar effect in Python.
You can't modify builtins, but a method is just a function that takes the instance as its first
argument, which by convention we call `self`.


```Python
result = (lambda self, *, ifTrue=None, ifFalse=None: (ifFalse, ifTrue)[bool(self)])(
a > b,
    ifTrue='greater',
    ifFalse='not greater',
)
```

But there's a problem. This only works on values. What if we want effects?

```Python
(lambda self, *, ifTrue=None, ifFalse=None: (ifFalse, ifTrue)[bool(self)])(
a > b,
    ifTrue=print('greater'),
    ifFalse=print('not greater'),
)
```

Clearly, this won't work! It prints both messages.

Too bad Python doesn't have those blocks things, or re-implementing `if` would be easy. Or does it?

Actually, a code block is just an anonymous function.
Python could do something similar with `def`.

```Python
my_if = lambda self, *, ifTrue=None, ifFalse=None: (ifFalse, ifTrue)[bool(self)]()  # note the ()

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

You could implement `iftrue:` as a decorator instead,
```Python
>>> iftrue = lambda b: lambda f: f() if b else None
>>> @iftrue(10 > 5)
... def result():
...     print("greater")
...     return "greater"
greater
>>> result
'greater'
```
but how do you pass in a second function for `iftrue:iffalse`?
You actually can do this with decorators, you just need to decorate two functions.
But decorators only accept one function, right? Just combine them with a class and decorate that.
You don't even need an instance:
```Python
>>> decr_if = lambda b: lambda c: c.iftrue() if b else c.iffalse()
>>> @decr_if(10 > 5)
... class result:
...     def iftrue():
...         print("greater")
...         return "greater"
...     def iffalse():
...         print("not greater")
...         return "not greater"
greater
>>> result
'greater'
```
Decorators are pretty useful.
You could easily implement the 3-way if like this. But how would you implement a switch/case
with decorators? Not so easy, is it?

Python does have anonymous inline functions though, with `lambda`.
```Python
my_if(a > b,
    ifTrue=lambda: print('greater'),
    ifFalse=lambda: print('not greater'),
)
```
Much prettier. Too bad `lambda` can't have multiple expressions, or this might actually work.
Or can it?

What if you had an expression that contained multiple expressions,
and executed them one-by-one in order?
You do. It's a tuple literal. Think of the commas as semicolons and you get the idea.

What if you just want to `return` the value of the last expression,
instead of a tuple of all of them?
Declare a tuple and immediately index it `(...)[-1]`?
The included `do` function does exactly this, and also doesn't crash if its args tuple is empty.

```Python
>>> my_if(10 > 5,
...     ifTrue=lambda: do(
...         print('greater'),
...         'greater',
...     ),
...     ifFalse=lambda: do(
...         print('not greater'),
...         'not greater',
...     ),
... )
greater
'greater'
```
It's no worse than the decorator version in terms of length, but this version is an expression.
That means you can put the whole thing in a function call or a lambda body and it still works,
unlike the decorator version, which is made of statements. You could also take an arbitrary
number of lambdas using a `*args` parameter to make more complex control structures like a
switch/case. This is much more difficult with decorators.

Unfortunately, lambdas in Python can't contain statements,
so even with `do` they can't work as general code bocks.
Or can they?

With drython's statement module, they can.

The statement module contains expression substitutes for every
Python statement that isn't already an expression.
They work in lambdas.
They work in `eval()`.
They're pretty handy in drython's executable data structures,
which therefore don't need to handle statement code.
This makes them a lot simpler than AST, and therefore easier to use.

Ready to write that three-way if?

***Congratulations,*** you've just learned new abstractions!
You can extend Python's syntax without changing the grammar and write your DSL in that.
No need to write your own compiler or interpreter, because it's still just Python.
Ready for the next step?

## s-expressions ##

Tired of writing `lambda ...: let(lambda:do(...,Return()))` when you just needed an anonymous
function?
That sure sounds like a boilerplate code problem.
You need better abstractions again.

Wouldn't it be easier if you could write functions that get their arguments unevaluated?
Then you wouldn't need to wrap everything in lambdas.
Lisp can do it with macros. Python can do it too, with drython.

An s-expression is an abstracted function *call*.
You create an s-expression instance with a function and its arguments.

```Python
S(print, "Hello,", "World!")
```

But the call doesn't happen until you invoke its `s_eval()` method,
at which point it calls `s_eval()` on all its s-evaluable arguments
(typically nested s-expressions), and then applies the function to the results.

With this recursive evaluation and the statement replacements from the statement module,
it is possible to write entire programs as nested s-expressions.
Think of s-expressions as a simpler kind of abstract syntax trees.

```Python
>>> S(print, S("Hello,".upper), S("World!".lower)).s_eval({})
HELLO, world!
```

Note the dictionary in the `s_eval` call.
s-expressions have their own scope for delayed evaluation of `Symbol`s.
For a module-level s-expression, you might want to pass in the `globals()`,
which will make them available as the equivalent symbol.
```Python
>>> spam = 7
>>> S(print, S.spam).s_eval(globals())  # S.spam is the same as Symbol('spam')
7
>>> S(setq, S.spam, 42).s_eval(globals())  # globals() is writable.
>>> spam
42
```

You can also use an s-expression as a kind of lambda. Calling one directly will call `s_eval` with
the kwargs dict.

```Python
>>> S(print, S.x, S.y, 3, sep=S.sep)(x=1, y=2, sep=':')
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

## the stack module ##

`Def` is an alternative way to write anonymous functions.
It is another executable data structure in the tradition of stack languages like Forth,
Factor, and Joy.

A Stack represents a composition of special
functions called *stack combinators* and their associated data.

Because stack combinators must accept a stack and return a stack, they are easy to combine into new
combinators, just by listing them one after another.
Typically they pop some arguments off the Stack and push the result on the return Stack

Unlike s-expressions which must be s-evaluated, combinators execute immediately when pushed on a
Stack. However,
a list containing combinators isn't a Stack, even when the list itself is an element on a Stack.

These lists are a kind of quoted program. Some combinators take such programs as arguments.
This is similar to the way Smalltalk takes code blocks, so control structures (and therefore DSLs)
can be implemented as combinators in an analogous way.
See the `ifte` combinator in the `stack` module's companion `combinators` module for an example.

Stack programs are interoperable with ordinary Python programs.

The `run` combinator can execute any Python function using arguments from the stack.

    Python
    >>> Stack([1,2,3],dict(sep='::'),print,run)
    1::2::3
    Stack(None,)

Including, of course, any statement replacement function from the `statement` module.

The `op` function takes a Python function and returns a combinator.

The `Def` class does the opposite.
The `Def` constructor is a stack program, that is, a sequence of combinators
(and any associated data).
The resulting function (a callable instance of `Def`) takes its arguments as the initial Stack,
applies the stored Stack program to that, then returns the top element of the Stack.

    Python
    >>> from operator import mul
    >>> square = Def(dup, mul)  # duplicate, then multiply
    >>> square(4)
    16
    >>> square(7)
    49
    >>> square  # unlike an ordinary Python function, the repr is readable.
    Def(dup, op(mul))


