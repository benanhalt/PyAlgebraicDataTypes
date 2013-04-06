from collections import OrderedDict, namedtuple
from itertools import zip_longest, chain
import inspect
import ast

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
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        if not self.isidentifier():
            raise TypeError("not a valid Python identifier: %r" % str(self))

    def __repr__(self):
        return 'Binding(%r)' % str(self)

    def bind(self, value):
        return {} if self == "" else {self: value}

class MatchFailed(Exception):
    pass

def traverse(pattern, handle):
    if isinstance(pattern, Binding):
        return handle.binding(pattern)

    if isinstance(pattern, type) and issubclass(pattern, Algebraic):
        if not hasattr(pattern, '_fields'):
            raise TypeError("can't match against generic type %r" % pattern)
        return handle.adt_constructor(pattern)

    if isinstance(pattern, Algebraic):
        return handle.adt_variant(pattern)

    if hasattr(pattern, 'keys') and hasattr(pattern, 'values'):
        return handle.mapping(pattern)

    if hasattr(pattern, '__iter__'):
        return handle.sequence(pattern)

    return handle.value(pattern)

class BindingExtractor:
    def extract(self, pattern):
        return traverse(pattern, self)

    def binding(self, binding):
        return binding

    def adt_constructor(self, ctr):
        return ctr._fields

    def adt_variant(self, variant):
        return self.sequence(variant)

    def mapping(self, map):
        return self.sequence(map.values())

    def sequence(self, seq):
        return chain(*(self.extract(value) for value in seq))

class Match:
    def __init__(self, value):
        self.value = value

    def match(self, pattern):
        return traverse(pattern, self)

    def recur(self, subpattern, subvalue):
        try:
            return self.match(subpattern, subvalue)
        except MatchFailed as failure:
            raise MatchFailed("%r didn't match %r" % (value, pattern)) \
                  from failure

    def binding(self, binding):
        return binding.bind(self.value)

    def adt_constructor(self, ctr):
        if not isinstance(self.value, ctr):
            raise MatchFailed("expected %r, got %r" %
                              (ctr, self.value))
        return self.value._asdict()

    def adt_variant(self, variant):
        if not isinstance(self.value, variant.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (variant, self.value))
        result = {}
        for subpattern, subvalue in zip(variant, self.value):
            result.update(self.recur(subpattern, subvalue))
        return result

    def mapping(self, map):
        if not hasattr(self.value, 'keys') or not hasattr(self.value, 'values'):
            raise MatchFailed("can't match mapping type pattern with %r"
                              % self.value)
        result = {}
        for key in map:
            if key not in self.value:
                raise MatchFailed("pattern has key %r not in value" % key)
            result.update(self.recur(map[key], self.value[key]))
        return result

    def sequence(self, seq):
        if not hasattr(self.value, '__iter__'):
            raise MatchFailed("can't match sequence with %r" % self.value)

        result = {}
        sentinel = object()
        for subpattern, subvalue in zip_longest(seq, self.value,
                                                fillvalue=sentinel):
            if sentinel in (subpattern, subvalue):
                raise MatchFailed("pattern and value had different lengths")
            result.update(self.recur(subpattern, subvalue))
        return result

    def value(self, v):
        if self.value != pattern:
            raise MatchFailed("%r didn't match %r" % (value, pattern))

class CasesExhausted(Exception):
    pass

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

def get_pattern(func):
    if not callable(func): return None
    argspec = inspect.getfullargspec(func)
    if len(argspec) < 1: return None
    try:
        return argspec.annotations[argspec.args[0]]
    except KeyError:
        return None

class MatchCasesMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, name, bases, clsdict):
        if bases is ():
            return type.__new__(metacls, name, bases, clsdict)
        cases = [(name, func, ptrn)
                 for name, func in clsdict.items()
                 for ptrn in [ get_pattern(func) ]
                 if ptrn is not None]
        for n, f, p in cases: del clsdict[n]
        clsdict['_cases'] = cases
        return type.__new__(metacls, name, bases, clsdict)

class MatchCases(metaclass=MatchCasesMeta):
    def __new__(cls, value):
        value = Match(value)
        for name, func, pattern in cls._cases:
            try:
                bindings = value.match(pattern)
                break
            except MatchFailed:
                pass
        else:
            raise CasesExhausted('no case for %r' % (value, ))

        if len(bindings) < 1:
            return func(value)

        funcast = ast.parse(inspect.getsource(func).strip())
        funcargs = funcast.body[0].args
        funcargs.args = [ast.arg(funcargs.args[0].arg, None)]
        funcargs.args.extend(ast.arg(name, None) for name in bindings.keys())
        env = dict()
        if len(func.__code__.co_freevars) < 1:
            exec(compile(funcast, '<generated>', 'exec'), globals(), env)
            newfunc = env[name]
        else:
            freevars = ', '.join(func.__code__.co_freevars)
            wrapper = ast.parse("def wrapper(%s):\n"
                                "  def %s(): pass\n"
                                "  return %s" % (freevars, name, name))
            wrapperfunc = wrapper.body[0]
            wrapperfunc.body[0] = funcast.body[0]
            exec(compile(wrapper, '<generated>', 'exec'), globals(), env)
            newfunc = env['wrapper'](*[c.cell_contents
                                       for c in func.__closure__])

        return newfunc(value, **bindings)

def wrapped(scale):

    class Tree(Algebraic):
        pass

    class Leaf(Tree):
        value = Anything()

    class Node(Tree):
        left = Require(Tree)
        right = Require(Tree)

    class TreeIterator(MatchCases):
        def node(match : Node):
            for v in TreeIterator(left): yield v
            for v in TreeIterator(right): yield v

        def leaf(match : Leaf):
            yield scale*value

    tree = Node(Leaf(1), Node(Node(Leaf(2), Leaf(3)), Leaf(4)))
    return tree, TreeIterator
tree, TreeIterator = wrapped(5)



lst = Cons(1, Cons(2, Cons(3, Nil())))

pattern = Cons(Binding('a'), Cons(Binding('b'), Binding('c')))


# print(list(TreeIterator.run(tree)))

class ListIterator(MatchCases):
    def nil(match: Nil):
        raise StopIteration
    def cons(match: Cons):
        yield car
        for v in ListIterator(cdr): yield v

# print(list(ListIterator.run(lst)))
