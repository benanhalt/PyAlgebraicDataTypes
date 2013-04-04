from collections import OrderedDict, namedtuple
from itertools import zip_longest
import inspect

class Ignore(namedtuple('Ignore', 'etype')):
    __slots__ = ()
    def __enter__(self):
        pass
    def __exit__(self, etype, evalue, traceback):
        return etype is None or issubclass(etype, self.etype)

class Singleton:
    __slots__ = ()
    def __new__(cls):
        try:
            return cls._instance
        except AttributeError:
            cls._instance = super().__new__(cls)
        return cls._instance

class Constraint:
    pass

class Anything(Constraint, Singleton):
    def check(self, value):
        pass

class Require(Constraint, namedtuple('Required', 'dtype')):
    __slots__ = ()
    def check(self, value):
        if not isinstance(value, self.dtype):
            raise TypeError("expected type %s, got %s" %
                            (self.dtype, value.__class__))

class AlgebraicMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, name, bases, clsdict):
        if bases == ():
            return super().__new__(metacls, name, bases, clsdict)
        if bases[0] is Algebraic:
            clsdict['_variants'] = []
            return super().__new__(metacls, name, bases, clsdict)
        # else making a variant

        fields = [key for key, value in clsdict.items()
                  if isinstance(value, Constraint)]

        clsdict['_constraints'] = [clsdict[key] for key in fields]
        for key in fields:
            del clsdict[key]

        bases = ( namedtuple(name + 'Tuple', fields), ) + bases
        if len(fields) < 1:
            bases = ( Singleton, ) + bases
        cls = type.__new__(metacls, name, bases, clsdict)
        cls._variants.append(cls)
        return cls

class Algebraic(metaclass=AlgebraicMeta):
    def __new__(cls, *args, **kwargs):
        raise TypeError("can't instantiate")

    def __init__(self, *args, **kwargs):
        for field, constraint in zip(self._fields, self._constraints):
            value = getattr(self, field)
            if isinstance(value, Binding):
                pass
            else:
                constraint.check(value)

class Binding(str):
    def __repr__(self):
        return 'Binding(%r)' % str(self)

    def bind(self, value):
        return {} if self == "" else {self: value}

class MatchFailed(Exception):
    pass

def match(pattern, value):
    def recur(subpattern, subvalue):
        try:
            return match(subpattern, subvalue)
        except MatchFailed as failure:
            raise MatchFailed("%r didn't match %r" % (value, pattern)) \
                  from failure

    if isinstance(pattern, Binding):
        return pattern.bind(value)

    if isinstance(pattern, type) and issubclass(pattern, Algebraic):
        if not hasattr(pattern, '_fields'):
            raise TypeError("can't match against generic type %r" % pattern)
        if not isinstance(value, pattern):
            raise MatchFailed("expected %r, got %r" %
                              (pattern, value))
        return value._asdict()

    if isinstance(pattern, Algebraic):
        if not isinstance(value, pattern.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (pattern, value))
        result = {}
        for subpattern, subvalue in zip(pattern, value):
            result.update(recur(subpattern, subvalue))
        return result

    if hasattr(pattern, 'keys') and hasattr(pattern, 'values'):
        if not hasattr(value, 'keys') or not hasattr(value, 'values'):
            raise MatchFailed("can't match mapping type pattern with %r"
                              % value)
        result = {}
        for key in pattern:
            if key not in value:
                raise MatchFailed("pattern has key %r not in value" % key)
            result.update(recur(pattern[key], value[key]))
        return result

    if hasattr(pattern, '__iter__'):
        if not hasattr(value, '__iter__'):
            raise MatchFailed("can't match sequence with %r" % value)

        result = {}
        sentinel = object()
        for subpattern, subvalue in zip_longest(pattern, value,
                                                fillvalue=sentinel):
            if sentinel in (subpattern, subvalue):
                raise MatchFailed("pattern and value had different lengths")
            result.update(recur(subpattern, subvalue))
        return result

    if value == pattern:
        return {}

    raise MatchFailed("%r didn't match %r" % (value, pattern))

class CasesExhausted(Exception):
    pass

def match_cases(value, *pattern_cases):
    for pattern, action in pattern_cases:
        with Ignore(MatchFailed):
            bindings = match(pattern, value)
            break
    else:
        raise CasesExhausted()
    return action(**bindings)

class Expr(Algebraic):
    pass

class Num(Expr):
    value = Require(int)

class Add(Expr):
    lhs = Require(Expr)
    rhs = Require(Expr)


class List(Algebraic):
    def iterator(self):
        t = self
        while True:
            try:
                car, t = match(Cons, t).values()
                yield car
            except MatchFailed:
                break


class Nil(List):
    pass

class Cons(List):
    car = Anything()
    cdr = Require(List)

class Match(namedtuple('Match', 'pattern, value')):
    def __enter__(self):
        return lambda: match(self.pattern, self.value)
    def __exit__(self, etype, evalue, traceback):
        return etype is None or issubclass(etype, MatchFailed)


class MatchCases:
    @classmethod
    def run(cls, value):
        cases = [v for v in cls.__dict__.values() if callable(v)]
        for case in cases:
            argspec = inspect.getfullargspec(case)
            pattern = argspec.annotations[argspec.args[0]]
            with Match(pattern, value) as match:
                return case(match())
        raise CasesExhausted('no case for %r' % (value, ))


class Tree(Algebraic):
    def iterator(self):
        with Match(Node, self) as match:
            left, right = match().values()
            yield from left.iterator()
            yield from right.iterator()
            return
        with Match(Leaf, self) as match:
            value, = match().values()
            yield value
            return
        raise Exception

class Leaf(Tree):
    value = Anything()

class Node(Tree):
    left = Require(Tree)
    right = Require(Tree)

class TreeIterator(MatchCases):
    def node(match : Node):
        left, right = match.values()
        yield from TreeIterator.run(left)
        yield from TreeIterator.run(right)

    def leaf(match : Leaf):
        value, = match.values()
        yield value

lst = Cons(1, Cons(2, Cons(3, Nil())))

print(lst)

pattern = Cons(Binding('a'), Cons(Binding('b'), Binding('c')))

print(match(pattern, lst))

tree = Node(Leaf(1), Node(Node(Leaf(2), Leaf(3)), Leaf(4)))

print(list(TreeIterator.run(tree)))

class ListIterator(MatchCases):
    def nil(match: Nil):
        raise StopIteration
    def cons(match: Cons):
        yield match['car']
        yield from ListIterator.run(match['cdr'])

print(list(ListIterator.run(lst)))
