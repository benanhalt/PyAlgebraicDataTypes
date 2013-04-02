from collections import OrderedDict, namedtuple


class Constraint:
    def check(self, value):
        return True

Anything = Constraint

class Require(Constraint):
    def __init__(self, adtype):
        self.adtype = adtype

    def check(self, value):
        if not isinstance(self.adtype, type) or not issubclass(self.adtype, Algebraic):
            self.adtype = globals()[self.adtype]
        if not self.adtype.isntit(value):
            raise TypeError("Expected type %s, got %s" % (self.adtype, value.__class__))

class VariantMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, name, bases, clsdict):
        fields = [key for key, value in clsdict.items()
                  if isinstance(value, Constraint)]
        clsdict['_constraints'] = [clsdict[key] for key in fields]
        for key in fields:
            del clsdict[key]

        class TypeChecked:
            def __init__(self, *args):
                for field, constraint in zip(self._fields, self._constraints):
                    value = getattr(self, field)
                    if isinstance(value, Binding):
                        pass
                    else:
                        constraint.check(value)

        bases = ( namedtuple(name, fields), ) + bases + ( TypeChecked, )
        return type.__new__(metacls, name, bases, clsdict)

class Variant(metaclass=VariantMeta):
    pass

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
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'Binding("%s")' % self.name

def match(matcher, value):
    pass

_ = Binding

empty = Tree.Empty()

tree = Tree.Node(4, Tree.Node(2, empty, empty), Tree.Node(5, Tree.Node(6, empty, empty), empty))

matcher = Tree.Node(_("v"), _("l"), _("r"))

print(match(matcher, tree))
