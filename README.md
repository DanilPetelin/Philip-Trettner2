# Drython (Don't-repeat-yourself Python)

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

The secret to metaprogramming is treating code as just another kind of data.

Python already includes some metaprogramming facilities.
For example, Python can write text files, including .py files, which it can then import as modules.
Python can also create strings, including strings containing Python code, which it can execute with
the `exec()` function.
Sometimes this approach is appropriate, but manipulating text as correct
Python code can be difficult and error-prone.
Compiling text is also rather slow.

Alternatives to text manipulation include manipulation of Python bytecodes
(not for the faint of heart),
and manipulation of abstract syntax trees using the `ast` module, which is arcane, but usable:

    import ast
    print(ast.dump(ast.parse('''print("Hello, World!")''')))
    # Module(body=[Expr(value=Call(func=Name(id='print', ctx=Load()), args=[Str(s='Hello, World!')], keywords=[], starargs=None, kwargs=None))])

Reading AST is easier than writing it (malformed AST can segfault Python),
but if it took that much for a simple `print('Hello, World!')`,
you can imagine it gets complex fast.
Unfortunately, bytecode and abstract syntax trees are implementation details subject to change
between Python versions and implementations.

There's an easier way. Drython provides *executable* data structures that are both simpler than AST,
and are easier to work with than text.
Drython specifically avoids using ast and bytecode manipulation,
so it's portable across implementations.

## Drython's statement module ##

Can you re-implement a simple if-statement in Python?
I mean without writing an interpreter or compiler, or modifying Python itself?
Sure, you don't have to, Python has a perfectly good if-statement already, but can you?
A DSL might need a three-way if-statement (-/+/0), or something like a switch-case.
Yes, you can use the boilerplate cascading-elif pattern instead
for any of your complex branching needs, but that's not an abstraction, is it?
You have to re-write the logic imitating the switch-case (or what-have-you).
Every. Single. Time.
If you can't make a simple `if` substitute,
how can you expect to make a complex one when you need it?

You might not think Python can do it, but it's actually trivial in Smalltalk.
"If" isn't a statement in Smalltalk to begin with.
It's a method. On the booleans. In pseudo-Smalltalk-Python it would be something like this:

    Python
    (foo < bar).iftrue_iffalse({
        # then-code here
    }, {
        # else-code here
    })

The `(foo < bar)` part evaluates to either `True` or `False` depending if
`foo` is less then `bar` just like in normal Python.
The `{}` isn't a dictionary; it's a code block.
The `True` boolean has an `iftrue_iffalse` method that always executes the then-block,
but `False` has a different version of `iftrue_iffalse` that only executes the else-block.
Is that cool or what?
Too bad Python doesn't have those blocks, or re-implementing `if` would be easy. Or does it?

Actually, a code block is just an anonymous function.
Python calls it `lambda`.
Unfortunately, lambdas in Python can't contain statements, or this could work in Python too.
Or can they?

With drython, they can.

Drython's statement module contains function substitutes for every
Python statement that isn't already an expression.
They work in lambdas.
They work in `eval()`.
They're pretty handy in drython's executable data structures,
which therefore only have to use expressions.
This makes them a lot simpler than AST, and therefore easier to use.

Too bad `lambda` can't have multiple expressions, or this might actually work.
Or can it?
What if you had an expression that contained multiple expressions,
and executed them one-by-one in order?
You do. It's a tuple literal.
What if you just want to return the value of the last statement,
instead of all of them?
Use drython's `progn` function instead, also found in the statement module.

Ready to write that `if`? (If not, look at the `Elif()` function in the statement module for hints.)
Congratulations, you've just learned new abstractions.
You can extend Python's syntax and write your DSL in that.
No need to write your own compiler or interpreter, because it's still just Python.
Ready for the next step?

## s-expressions ##

Tired of writing `lambda: progn(...)` over and over again in the shiny new
DSL you implemented after reading the last section?
Tired of writing `lambda ...: let(lambda:progn(...,Return()))` when you just needed an anonymous
function?
That sure sounds like a boilerplate code problem.
You need better abstractions again.

Wouldn't it be easier if you could write functions that get their arguments unevaluated?
Then you wouldn't need to wrap everything in lambdas.
Lisp can do it with macros. Python can do it too, with drython.

An S-expression is an abstracted function *call*.
You create an S-expression instance with a function and its arguments.

    Python
    S(print, "Hello,", "World!")

But the call doesn't happen until you invoke its `s_eval()` method,
at which point it calls `s_eval()` on all its s-evaluable arguments
(typically nested S-expressions), and then applies the function to the results.

    Python
    >>> S(print, S("Hello,".upper), S("World!".lower)).s_eval()
    HELLO, world!

With this recursive evaluation and the statement replacements from the statement module,
it is possible to write entire programs as nested S-expressions.
Think of S-expressions as a simpler kind of abstract syntax trees.

If the S-expression's function is a *macro*,
then it gets any s-evaluable arguments unevaluated,
and returns (typically) an s-evaluable for evaluation.
In other words, macros can re-write code.

So you can define "if" like this:

    Python
    @macro
    def If(boolean, then, Else=None):
        return S(s_eval,
                 S((Else, then).__getitem__,
                   S(bool,
                     boolean)))

The above macro rewrites the code into an S-expression that indexes a pair (2-tuple)
using the test part coerced into a boolean,
(remember `True == 1` and `False == 0` in Python) and then `s_eval`s the selected S-expression.

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

The `do` combinator can execute any Python function using arguments from the stack.

    Python
    >>> Stack([1,2,3],dict(sep='::'),print,do)
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


