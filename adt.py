from collections import OrderedDict, namedtuple

class Constraint:
    def check(self, value):
        return True

Anything = Constraint

class Require(Constraint):
    def __init__(self, adtype):
        self.adtype = adtype

    def check(self, value):
        if not isinstance(self.adtype, type) or \
               not issubclass(self.adtype, Algebraic):
            self.adtype = globals()[self.adtype]
        if not self.adtype.isntit(value):
            raise TypeError("Expected type %s, got %s" %
                            (self.adtype, value.__class__))

class VariantMeta(type):
    class Singleton:
        def __new__(cls):
            try:
                return cls._instance
            except AttributeError:
                cls._instance = super().__new__(cls)
            return cls._instance

    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, name, bases, clsdict):
        if bases == ():
            return type.__new__(metacls, name, bases, clsdict)

        fields = [key for key, value in clsdict.items()
                  if isinstance(value, Constraint)]

        clsdict['_constraints'] = [clsdict[key] for key in fields]
        for key in fields:
            del clsdict[key]

        bases = ( namedtuple(name + 'Tuple', fields), ) + bases
        if len(fields) < 1:
            bases = ( metacls.Singleton, ) + bases

        return type.__new__(metacls, name, bases, clsdict)

class Variant(metaclass=VariantMeta):
    def __init__(self, *args, **kwargs):
        for field, constraint in zip(self._fields, self._constraints):
            value = getattr(self, field)
            if isinstance(value, Binding):
                pass
            else:
                constraint.check(value)

class Algebraic:
    @classmethod
    def isntit(cls, value):
        variants = [v for v in cls.__dict__.values()
                    if isinstance(v, type) and issubclass(v, Variant)]
        return any(isinstance(value, variant) for variant in variants)

class List(Algebraic):
    class Nil(Variant):
        pass

    class Cons(Variant):
        car = Anything()
        cdr = Require('List')

class Tree(Algebraic):
    class Empty(Variant):
        pass

    class Node(Variant):
        value = Anything()
        left = Require('Tree')
        right = Require('Tree')

class Binding:
    def __init__(self, name=None):
        self.name = name

    def __repr__(self):
        return 'Binding("%s")' % self.name

    def bind(self, value):
        if self.name is None:
            return {}
        return {self.name: value}

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

    if isinstance(pattern, Variant):
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

    if hasattr(pattern, '__len__'):
        if not hasattr(value, '__len__'):
            raise MatchFailed("can't match sequence with %r" % value)
        if len(pattern) != len(value):
            raise MatchFailed("can't match length %d pattern with "
                              "length %d value" % (len(pattern), len(value)))
        result = {}
        for subpattern, subvalue in zip(pattern, value):
            result.update(recur(subpattern, subvalue))
        return result

    if value == pattern:
        return {}

    raise MatchFailed("%r didn't match %r" % (value, pattern))

empty = Tree.Empty()

tree = Tree.Node(4,
                 Tree.Node(2, empty, empty),
                 Tree.Node(5, Tree.Node(6, empty, empty), empty))

pattern = Tree.Node(Binding("v"), Binding("l"), Binding("r"))

print(match(pattern, tree))
