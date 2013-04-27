Algebraic Datatypes and Pattern Matching for Python
===================================================

This project was inspired by Racket's `define-type / type-case`
mechanism and [David Beazley's 
Metaprogramming](http://pyvideo.org/video/1716/python-3-metaprogramming) 
PyCon talk.

This README can be run as a doctest:
    `python -m doctest README.md`

A List of Integers
------------------
A very simple example.

```python
>>> from adt import ADT, Require
>>> class List(ADT):
...    pass

>>> class Nil(List):
...    pass

>>> class Cons(List):
...    car = Require(int)
...    cdr = Require(List)

>>> Cons(1, Nil())
Cons(car=1, cdr=Nil())

>>> Cons('foo', Nil())
Traceback (most recent call last):
TypeError: expected type <class 'int'>, got <class 'str'>

```

Constructors that take no arguments return singletons:

```python
>>> Nil() is Nil()
True

>>> Cons(1, Nil()) is Cons(1, Nil())
False

>>> Cons(1, Nil()) == Cons(1, Nil())
True

```

A Heterogeneous List
--------------------

```python
>>> from adt import Anything
>>> class List(ADT):
...     pass

>>> class Nil(List):
...     pass

>>> class Cons(List):
...     car = Anything()
...     cdr = Require(List)

>>> Cons('foo', Cons('bar', Nil()))
Cons(car='foo', cdr=Cons(car='bar', cdr=Nil()))

>>> Cons(1, Cons('a', Nil()))
Cons(car=1, cdr=Cons(car='a', cdr=Nil()))

>>> Cons(1, 2)
Traceback (most recent call last):
TypeError: expected type <class '__main__.List'>, got <class 'int'>

```

Pattern Matching with Algebraic Types
-------------------------------------

### Bindings ###

Bindings are used to create patterns with named slots that are bound
during matching.

```python
>>> from adt import Binding
>>> Binding('a')
Binding('a')

>>> Binding('3')
Traceback (most recent call last):
TypeError: not a valid Python identifier: '3'

```

A simple example of capturing values during matching:

```python
>>> b = Binding # A short name, for convenience.
>>> pattern = Cons(b('a'), Cons(b('b'), b('c')))
>>> pattern
Cons(car=Binding('a'), cdr=Cons(car=Binding('b'), cdr=Binding('c')))

>>> lst = Cons(1, Cons(2, Nil()))

>>> from adt import match, MatchFailed
>>> match(pattern, lst)
CapturedValues(a=1, b=2, c=Nil())

>>> lst = Nil()
>>> match(Cons(b('car'), Nil()), lst)
Traceback (most recent call last):
adt.MatchFailed: expected Cons(car=Binding('car'), cdr=Nil()), got Nil()

```

ADT constructors can stand in for pattern elments and
automatically bind their arguments.

```python
>>> match(Cons, Cons(1, Nil()))
CapturedValues(car=1, cdr=Nil())

```

Pattern Matching with Regular Expressions
-----------------------------------------

Patterns can include regular expressions. Named groups will
bind the matched values to the respective names.

```python
>>> import re
>>> tele_re = re.compile(r"(?P<area_code>\d{3})-"
...                      r"(?P<exchange>\d{3})-"
...                      r"(?P<subscriber>\d{4})")

>>> match(tele_re, "123-456-7890")
CapturedValues(area_code='123', exchange='456', subscriber='7890')

>>> pattern = Cons(tele_re, Cons(b('name'), Nil()))
>>> value = Cons('555-867-5309', Cons('Jenny', Nil()))
>>> match(pattern, value)
CapturedValues(area_code='555', exchange='867', subscriber='5309', name='Jenny')

```

Pattern Matching with Mapping Types
-----------------------------------

Patterns can include dictionaries or other mapping types to
be matched against mapping types in the value.

If the pattern is an ordered dictionary, values will be
captured in the order given. Otherwise the order will be
determined by sorting the keys.

```python
>>> from collections import OrderedDict
>>> pattern = OrderedDict([('a', 1), ('list', Cons), ('foo', b('foo_value'))])
>>> match(pattern, {'a': 1, 'list': Cons(1, Nil()), 'foo': 'bar', 'b': 2})
CapturedValues(car=1, cdr=Nil(), foo_value='bar')

>>> pattern = {'a': 1, 'list': Cons, 'foo': b('foo_value')}
>>> match(pattern, {'a': 1, 'list': Cons(1, Nil()), 'foo': 'bar', 'b': 2})
CapturedValues(foo_value='bar', car=1, cdr=Nil())

>>> match(pattern, {'a': 1, 'foo': 2, 'b': 3})
Traceback (most recent call last):
adt.MatchFailed: pattern has key 'list' which is not in value

```

Pattern Matching with Sequence Types
------------------------------------

```python
>>> pattern = [1, b('second'), 3, b('fourth')]
>>> match(pattern, (1, 2, 3, 4))
CapturedValues(second=2, fourth=4)

>>> match(pattern, (1,2,3))
Traceback (most recent call last):
adt.MatchFailed: pattern and value had different lengths

>>> match(('a', 'b', 'c', 'd'), "abcd")
CapturedValues()

```

### Rest Bindings ###

When matching a sequence, rest bindings can be used to
capture all remaining elements of a sequence as an iterable.

```python
>>> from adt import BindingRest
>>> pattern = [0,1,2,BindingRest('rest')]
>>> result = match(pattern, range(6))
>>> result # doctest: +ELLIPSIS
CapturedValues(rest=<generator object rest at ...>)

>>> list(result.rest)
[3, 4, 5]

>>> from itertools import islice
>>> result = match(pattern, range(10**100))
>>> list(islice(result.rest, 10))
[3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

```

Ignored Bindings
----------------

Constructing bindings from an empty string (the only
non-Python-identifier accepted) results in a slot that does not
capture any value. This is useful for "don't care" values.

```python
>>> match(Binding('foo'), 'bar')
CapturedValues(foo='bar')

>>> match(Binding(''), 'baz')
CapturedValues()

```

Making an ignored rest binding allows remaining elements of a
sequence to be ignored.

```python
>>> pattern = (0, Binding('a'), BindingRest(''))
>>> match(pattern, range(10))
CapturedValues(a=1)

>>> def loop():
...    while True:
...       yield 0
>>> match(pattern, loop())
CapturedValues(a=0)

```

Pattern Matching with ASTs
--------------------------

```python
>>> import ast
>>> an_ast = ast.parse('def square(t): return t*t')
>>> pattern = ast.Module(body=[
...    ast.FunctionDef(name=Binding('name'))
... ])
>>> match(pattern, an_ast)
CapturedValues(name='square')

```

Match Cases
-----------

Using metaclass magic and function annotations admits a construct
similar in flavor to Racket's `type-case`. Subclasses of `MatchCases`
analize their contained functions to collect a series of patterns to
match. The patterns are given by the annotation on the first argument
of each function. The patterns are tried in the order the functions
are defined in the class. When a pattern is matched the corresponding
function will be invoked with the value that matched as the first
argument and the resulting `CapturedValues` namedtuple as the second.
After a match is found, no further patterns are examined. If no
pattern matches, a `CasesExhausted` exception is raised.

```python
>>> from adt import MatchCases
>>> class ListIter(MatchCases):
...    def nil(match: Nil, bindings):
...        yield from ()
...    def cons(match: Cons, bindings):
...        yield bindings.car
...        yield from ListIter(bindings.cdr)

>>> lst = Cons(1, Cons(2, Cons(3, Nil())))
>>> tuple(ListIter(lst))
(1, 2, 3)

>>> class MissingCases(MatchCases):
...    def only_nil(match: Nil(), bindings):
...        pass

>>> MissingCases(lst) # doctest: +ELLIPSIS
Traceback (most recent call last):
adt.CasesExhausted: no case for Cons(...) in <class '__main__.MissingCases'>

```

Functions in a `MatchCases` class can exclude the second, captured
values, argument. This triggers special behavior whereby the function
is replaced by a dynamically generated version with arguments inserted
for each captured value. This eliminates the need to repeat the names
of the bindings from the pattern.

```python
>>> class ListSum(MatchCases):
...    def nil(match: Nil()):
...        return 0
...    def cons(match: Cons(b('head'), b('tail'))):
...        return head + ListSum(tail)

>>> ListSum(lst)
6

```

Here another example with a binary tree ADT this time:

```python
>>> class Tree(ADT): pass

>>> class Leaf(Tree):
...   value = Require(int)

>>> class Node(Tree):
...    left = Require(Tree)
...    right = Require(Tree)

>>> tree = Node(Leaf(1), Node(Node(Leaf(2), Leaf(3)), Leaf(4)))

>>> class TreeSum(MatchCases):
...    def leaf(match: Leaf):
...        return value
...    def node(match: Node):
...        return TreeSum(left) + TreeSum(right)

>>> TreeSum(tree)
10

```
