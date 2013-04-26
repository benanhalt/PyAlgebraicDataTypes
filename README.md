Algebraic Datatypes for Python
==============================
This README can be run as a doctest:
    `python -m doctest README.md`

A List of Integers
------------------

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

>>> Cons(1, 2)
Traceback (most recent call last):
TypeError: expected type <class '__main__.List'>, got <class 'int'>

```

Bindings
--------
Bindings are used to create patterns with named slots.

```python
>>> from adt import Binding
>>> Binding('a')
Binding('a')

>>> Binding('3')
Traceback (most recent call last):
TypeError: not a valid Python identifier: '3'

```

Pattern Matching Algebraic Types
--------------------------------

```python
>>> b = Binding # A short name, for convenience.
>>> pattern = Cons(b('a'), Cons(b('b'), b('c')))
>>> pattern
Cons(car=Binding('a'), cdr=Cons(car=Binding('b'), cdr=Binding('c')))

>>> lst = Cons(1, Cons(2, Nil()))

>>> from adt import match, MatchFailed
>>> result = match(pattern, lst)
>>> result['a'], result['b'], result['c']
(1, 2, Nil())

>>> lst = Nil()
>>> match(Cons(b('car'), Nil()), lst)
Traceback (most recent call last):
adt.MatchFailed: expected Cons(car=Binding('car'), cdr=Nil()), got Nil()

```

ADT constructors can stand in for pattern elments and
automatically bind their arguments.

```python
>>> result = match(Cons, Cons(1, Nil()))
>>> sorted(result.items())
[('car', 1), ('cdr', Nil())]

```

Pattern Matching with Regular Expressions
-----------------------------------------
Patterns can include regular expressions. Named groups will
bind the matched vasues to the respective names.

```python
>>> import re
>>> tele_re = re.compile(r"(?P<area_code>\d{3})-"
...                      r"(?P<exchange>\d{3})-"
...                      r"(?P<subscriber>\d{4})")

>>> pattern = Cons(tele_re, b('a'))
>>> result = match(pattern, Cons("123-456-7890", Nil()))
>>> sorted(result.items())
[(Binding('a'), Nil()), ('area_code', '123'), ('exchange', '456'), ('subscriber', '7890')]

```

Pattern Matching with Mapping Types
-----------------------------------
Patterns can include dicts or other mapping types that will
be matched against mapping types in the value.

```python
>>> pattern = {'a': 1, 'list': Cons, 'foo': b('foo_value')}
>>> result = match(pattern, {'a': 1, 'list': Cons(1, Nil()), 'foo': 'bar', 'b': 2})
>>> sorted(result.items())
[('car', 1), ('cdr', Nil()), (Binding('foo_value'), 'bar')]

>>> match(pattern, {'a': 1, 'foo': 2, 'b': 3})
Traceback (most recent call last):
adt.MatchFailed: pattern has key 'list' not in value

```

Pattern Matching with Sequence Types
------------------------------------

```python
>>> pattern = [1, b('second'), 3, b('fourth')]
>>> result = match(pattern, (1, 2, 3, 4))
>>> result['second'], result['fourth']
(2, 4)

>>> match(pattern, (1,2,3))
Traceback (most recent call last):
adt.MatchFailed: pattern and value had different lengths

>>> match(('a', 'b', 'c'), "abcd")
Traceback (most recent call last):
adt.MatchFailed: pattern and value had different lengths

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
{Binding('name'): 'square'}

```

Rest Bindings
-------------
When matching a sequence, rest bindings can be used to
capture all remaining elements of the sequence as a list.
The resulting list is copied element by element, so this
is not recommended for destructuring long sequences.

```python
>>> from adt import BindingRest
>>> match([0,1,2,BindingRest('rest')], range(6))
{Binding('rest'): [3, 4, 5]}

```

Ignore Bindings
--------------

```python
>>> match(Binding(''), 'foo')
{}
>>> pattern = (0, Binding('a'), BindingRest(''))
>>> match(pattern, range(10))
{Binding('a'): 1}

>>> def loop():
...    while True:
...       yield 0
>>> match(pattern, loop())
{Binding('a'): 0}

```

Match Cases
-----------

```python
>>> class Tree(ADT): pass

>>> class Leaf(Tree):
...   value = Require(int)

>>> class Node(Tree):
...    left = Require(Tree)
...    right = Require(Tree)

>>> tree = Node(Leaf(1), Node(Node(Leaf(2), Leaf(3)), Leaf(4)))

>>> from adt import MatchCases
>>> class TreeSum(MatchCases):
...    def leaf(match: Leaf):
...        return value
...    def node(match: Node):
...        return TreeSum(left) + TreeSum(right)

>>> TreeSum(tree)
10

```
