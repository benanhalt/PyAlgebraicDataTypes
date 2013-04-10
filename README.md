Algebraic Datatypes for Python
==============================

```python
>>> import adt

```


A List of Int
-------------

```python
>>> class List(adt.Algebraic):
...    pass

>>> class Nil(List):
...    pass

>>> class Cons(List):
...    car = adt.Require(int)
...    cdr = adt.Require(List)

>>> Cons(1, Nil())
Cons(car=1, cdr=Nil())

>>> try:
...    Cons('foo', Nil())
... except TypeError as e:
...    print(e)
expected type <class 'int'>, got <class 'str'>

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

A List of Anything
------------------
```python
>>> class List(adt.Algebraic):
...     pass

>>> class Nil(List):
...     pass

>>> class Cons(List):
...     car = adt.Anything()
...     cdr = adt.Require(List)

>>> Cons('foo', Cons('bar', Nil()))
Cons(car='foo', cdr=Cons(car='bar', cdr=Nil()))

>>> try:
...     Cons(1, 2)
... except TypeError as e:
...     print(e)
expected type <class '__main__.List'>, got <class 'int'>

```

Bindings
--------
Bindings are used to create patterns with named slots.

```python
>>> adt.Binding('a')
Binding('a')

>>> try:
...    adt.Binding('3')
... except TypeError as e:
...    print(e)
not a valid Python identifier: '3'

```

Pattern Matching Algebraic Types
--------------------------------
For convenience, create a short name for the binding constructor.

```python
>>> b = adt.Binding
>>> pattern = Cons(b('a'), Cons(b('b'), b('c')))
>>> pattern
Cons(car=Binding('a'), cdr=Cons(car=Binding('b'), cdr=Binding('c')))

>>> lst = Cons(1, Cons(2, Nil()))
>>> result = adt.Match(lst).against(pattern)
>>> result['a'], result['b'], result['c']
(1, 2, Nil())

>>> lst = Nil()
>>> try:
...    adt.Match(lst).against(Cons(b('car'), Nil()))
... except adt.MatchFailed as e:
...    print(e)
expected Cons(car=Binding('car'), cdr=Nil()), got Nil()

```

ADT constructors can stand in for pattern elments and
automatically bind their arguments.

```python
>>> result = adt.Match(Cons(1, Nil())).against(Cons)
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
>>> result = adt.Match(Cons("123-456-7890", Nil())).against(pattern)
>>> sorted(result.items())
[(Binding('a'), Nil()), ('area_code', '123'), ('exchange', '456'), ('subscriber', '7890')]

```

Pattern Matching with Mapping Types
-----------------------------------
Patterns can include dicts or other mapping types that will
be matched against mapping types in the value.

```python
>>> pattern = {'a': 1, 'list': Cons, 'foo': b('foo_value')}
>>> result = adt.Match({'a': 1, 'list': Cons(1, Nil()), 'foo': 'bar', 'b': 2}).against(pattern)
>>> sorted(result.items())
[('car', 1), ('cdr', Nil()), (Binding('foo_value'), 'bar')]

>>> try:
...    adt.Match({'a': 1, 'foo': 2, 'b': 3}).against(pattern)
... except adt.MatchFailed as e:
...    print(e)
pattern has key 'list' not in value

```

Pattern Matching with Sequence Types
------------------------------------

```python
>>> pattern = [1, b('second'), 3, b('fourth')]
>>> result = adt.Match((1, 2, 3, 4)).against(pattern)
>>> result['second'], result['fourth']
(2, 4)

>>> try:
...    adt.Match((1,2,3)).against(pattern)
... except adt.MatchFailed as e:
...    print(e)
pattern and value had different lengths

>>> try:
...    adt.Match("abcd").against(('a', 'b', 'c'))
... except adt.MatchFailed as e:
...    print(e)
pattern and value had different lengths

```

Rest Bindings
-------------
When matching a sequence a rest binding can be used to
capture all remaining elements of the sequence as a list.
The resulting list is copied element, so this is not recommended
for destructuring long sequences.

```python
>>> adt.Match(range(6)).against([0,1,2,adt.BindingRest('rest')])
{Binding('rest'): [3, 4, 5]}

```

Match Cases
-----------

```python
>>> class Tree(adt.Algebraic): pass

>>> class Leaf(Tree):
...   value = adt.Require(int)

>>> class Node(Tree):
...    left = adt.Require(Tree)
...    right = adt.Require(Tree)

>>> tree = Node(Leaf(1), Node(Node(Leaf(2), Leaf(3)), Leaf(4)))

>>> class TreeSum(adt.MatchCases):
...    def leaf(match: Leaf):
...        return value
...    def node(match: Node):
...        return TreeSum(left) + TreeSum(right)

>>> TreeSum(tree)
10

```
