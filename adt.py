# Copyright 2013 Ben Anhalt

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict, namedtuple
from itertools import zip_longest, chain
import inspect
import ast
import re

class Singleton:
    """Mix-in for making singleton types."""
    def __new__(cls):
        try:
            return cls._instance
        except AttributeError:
            cls._instance = super().__new__(cls)
        return cls._instance

class Constraint:
    """Base class for specifing fields in type constructors."""
    pass

class Anything(Constraint, Singleton):
    """Used for fields that accept any type."""
    def check(self, value):
        pass

class Require(Constraint, namedtuple('Required', 'dtype')):
    """Used for fields that must be of a given type."""
    def check(self, value):
        if not isinstance(value, self.dtype):
            raise TypeError("expected type %s, got %s" %
                            (self.dtype, value.__class__))

class AlgebraicMeta(type):
    """Metaclass for Algebraic Data Types."""
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, name, bases, clsdict):
        if bases is ():
            # Constructing the base class,
            # so there is no need to do anything.
            return super().__new__(metacls, name, bases, clsdict)

        if bases[0] is ADT:
            # Constructing a generic type. Just add a class
            # variable for tracking its variants.
            clsdict['_variants'] = []
            return super().__new__(metacls, name, bases, clsdict)

        # else: Constructing a variant of some generic type.

        fields = [key for key, value in clsdict.items()
                  if isinstance(value, Constraint)]

        clsdict['_constraints'] = [clsdict[key] for key in fields]
        for key in fields:
            del clsdict[key]

        bases = ( namedtuple(name + 'Tuple', fields), ) + bases
        if len(fields) < 1:
            # If the type constructor takes no arguments, all the
            # instance must be identical making it a natural singleton.
            bases = ( Singleton, ) + bases
        cls = type.__new__(metacls, name, bases, clsdict)
        cls._variants.append(cls)
        return cls

class ADT(metaclass=AlgebraicMeta):
    """Base class for algebraic data types."""
    def __new__(cls, *args, **kwargs):
        # Don't allow instances of the base class.
        raise TypeError("can't instantiate")

    def __init__(self, *args, **kwargs):
        """Construct an instance of the type."""
        for field, constraint in zip(self._fields, self._constraints):
            value = getattr(self, field)
            if isinstance(value, Binding):
                # Need to be able to build patterns up by adding bindings
                # anywhere into a type definition.
                pass
            else:
                constraint.check(value)

class Binding(str):
    """A Python identifier that can be inserted into a data structure
    pattern in order to bind matching values to the given name.
    """
    def __init__(self, *args, **kwargs):
        if not self.isidentifier() and self != '':
            raise TypeError("not a valid Python identifier: %r" %
                            str(self))

    def __repr__(self):
        return 'Binding(%r)' % str(self)

    def bind(self, value):
        """Associate this binding with the given value."""
        # A bound value is represented by a pair and a set of
        # bindings by a tuple of paired identifiers and values.
        return () if self == "" else ((self, value), )

class BindingRest(Binding):
    """A subclass of Binding that signals the pattern matching
    system to bind an iterator of all remaining values when
    matching an iterable value.
    """
    pass

class MatchFailed(Exception):
    pass

def dispatch(pattern, handle):
    """Dispatches to the appropriate method of 'handle' based
    on the type of 'pattern'.
    """
    if isinstance(pattern, Binding):
        return handle.binding(pattern)

    if isinstance(pattern, type) and issubclass(pattern, ADT):
        if not hasattr(pattern, '_fields'):
            raise TypeError("can't match against generic type %r" %
                            pattern)
        return handle.adt_constructor(pattern)

    if isinstance(pattern, ADT):
        return handle.adt_instance(pattern)

    if isinstance(pattern, type) and issubclass(pattern, ast.AST):
        return handle.ast_constructor(pattern)

    if isinstance(pattern, ast.AST):
        return handle.ast_instance(pattern)

    if isinstance(pattern, re._pattern_type):
        return handle.regexp(pattern)

    if isinstance(pattern, str):
        return handle.literal(pattern)

    if hasattr(pattern, 'keys') and hasattr(pattern, 'values'):
        return handle.mapping(pattern)

    if hasattr(pattern, '__iter__'):
        return handle.sequence(pattern)

    return handle.literal(pattern)

def extract_bindings(pattern):
    """Return an iterable of all the bindings contained in 'pattern'."""
    return dispatch(pattern, BindingExtractor())

class BindingExtractor(Singleton):
    """Provides a set of methods for each type of (sub)pattern for
    extracting all the bindings that it contains.
    """
    # Matches named groups in Python regular expression strings.
    named_group_re = re.compile(r'\(\?P<([^>]+)>')

    def binding(self, binding):
        if binding != '':
            # Bindings with an empty string identifier
            # are to be ignored.
            yield binding

    def adt_constructor(self, ctr):
        # A type constructor as a pattern automatically binds
        # its fields to fields in a matching value.
        return ctr._fields

    def adt_instance(self, instance):
        # A type instance is essentially a sequence of its fields.
        return self.sequence(instance)

    def ast_constructor(self, ctr):
        # Python AST constructors can be used in patterns to
        # match AST nodes in values and bind their fields.
        return ctr._fields

    def ast_instance(self, instance):
        # Just handle each element sequentially.
        return self.sequence(instance.__dict__.values())

    def regexp(self, pattern):
        # A regular expression in a pattern binds all of its named groups.
        return self.named_group_re.findall(pattern.pattern)

    def mapping(self, map):
        # Check for bindings in the elements of the mapping type.
        return self.sequence(map.values())

    def sequence(self, seq):
        # Check for bindings in the elements of the sequence.
        return chain.from_iterable(
            extract_bindings(value) for value in seq)

    def literal(self, value):
        # A literal either matches or it doesn't.
        # Either way it binds nothing.
        return ()

def unzip(z):
    """Given a sequence of pairs, return a pair of
    sequences such that `zip(unzip(z)) == z`.
    """
    return tuple(zip(*z)) or ((), ())

def match(pattern, value):
    """Attempt to match 'pattern' against 'value'.
    If the match succeeds, return a namedtuple with fields
    from the bindings in the pattern containing the
    associated values from the given value. If the match
    fails, MatchFailed is raised.
    """
    bindings = dispatch(pattern, MatchVisitor(value))
    fields, values = unzip(bindings)
    return namedtuple('CapturedValues', fields)(*values)

class MatchVisitor:
    """Provides a set of methods which when dispatched on
    a pattern will attempt to recursively match the given
    value.
    """
    def __init__(self, value):
        self.value = value

    def recur(self, subpattern, subvalue):
        try:
            return dispatch(subpattern, MatchVisitor(subvalue))
        except MatchFailed as failure:
            raise MatchFailed("%r didn't match %r" %
                              (subvalue, subpattern)) from failure

    def binding(self, binding):
        # A binding matches any value and binds it.
        return binding.bind(self.value)

    def adt_constructor(self, ctr):
        # A type constructor matches any instance of its class
        # and binds its fields to the instance's values.
        if not isinstance(self.value, ctr):
            raise MatchFailed("expected %r, got %r" %
                              (ctr, self.value))
        return zip(ctr._fields, self.value)

    def adt_instance(self, instance):
        # A type instance matches instances of the same type
        # if the values of each of their fields also match.
        if not isinstance(self.value, instance.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (instance, self.value))
        return chain.from_iterable(
            self.recur(subpattern, subvalue)
            for subpattern, subvalue in zip(instance, self.value))

    def ast_constructor(self, ctr):
        # A Python AST constructor matches instances of its class
        # and binds its fields to the instances values.
        if not isinstance(self.value, ctr):
            raise MatchFailed("expected %r, got %r" %
                              (ctr, self.value))
        return ((field, getattr(self.value, field))
                for field in ctr._fields)

    def ast_instance(self, instance):
        # A Python AST instance matches instances of the same type
        # if the values of each of their fields also match.
        if not isinstance(self.value, instance.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (instance, self.value))
        return chain.from_iterable(
            self.recur(getattr(instance, field),
                       getattr(self.value, field))
            for field in instance._fields)

    def regexp(self, pattern):
        # A regular expression matches in the usual sense and
        # binds any named groups the matched values.
        # TODO: Should check that value is a string first?
        match = pattern.match(self.value)
        if match is None:
            raise MatchFailed("regex %r didn't match %r" %
                              (pattern.pattern, self.value))
        items = match.groupdict().items()
        # Return the bindings in the order they were in RE string.
        return sorted(items,
                      key=lambda item: pattern.groupindex[item[0]])

    def mapping(self, map):
        # A mapping type matches values which are also mapping types
        # if all of the keys in the pattern map are in the value map
        # and if the corresponding values match.
        if not (hasattr(self.value, 'keys') and
                hasattr(self.value, 'values')):
            # value is not a mapping type.
            raise MatchFailed("can't match mapping type pattern "
                              "with %r" % self.value)
        def check(key):
            # check that value has key and that its value
            # for that key mathes the pattern's value
            if key not in self.value:
                raise MatchFailed("pattern has key %r "
                                  "which is not in value" % key)
            return self.recur(map[key], self.value[key])

        # Get the set of keys to check and sort them if they
        # are not coming out of an ordered dictionary.
        keys = map.keys()
        if not isinstance(map, OrderedDict):
            keys = sorted(map.keys())

        return chain.from_iterable(check(key) for key in keys)

    def sequence(self, seq):
        # A sequence pattern matches sequence values if each
        # of the elements match.
        if not hasattr(self.value, '__iter__'):
            # value is not a sequence type.
            raise MatchFailed("can't match sequence with %r" %
                              self.value)

        sentinel = object() # signals the end of either sequence
        pieces = zip_longest(seq, self.value, fillvalue=sentinel)

        for subpattern, subvalue in pieces:
            if isinstance(subpattern, BindingRest):
                # If a 'rest binding' is encountered, construct a
                # generator that produces the remaining elements
                # of the value sequence and bind that.
                def rest():
                    # the first remaining element is the
                    # one corresponding to the 'rest binding'
                    # in the pattern sequence
                    yield subvalue
                    # after that come all the remaining elements
                    yield from (value for __, value in pieces)

                # bind the generator
                yield from subpattern.bind(rest())
                break

            elif sentinel in (subpattern, subvalue):
                # hit the end of one of the sequences
                raise MatchFailed(
                    "pattern and value had different lengths")

            else:
                # try to match the corresponding elements
                yield from self.recur(subpattern, subvalue)

    def literal(self, value):
        # Anything else in the pattern matches if it is
        # equal to the value and results in no binding.
        if self.value != value:
            raise MatchFailed("%r didn't match %r" %
                              (self.value, value))
        return ()

class CasesExhausted(Exception):
    pass

def get_pattern(func):
    """Returns any annotation on the first argument of the
    function for use in pattern matching.
    """
    if not callable(func): return None
    argspec = inspect.getfullargspec(func)
    if len(argspec) < 1: return None
    try:
        return argspec.annotations[argspec.args[0]]
    except KeyError:
        return None

Case = namedtuple('Case', 'name action pattern')

class MatchCasesMeta(type):
    """Metaclass that leverages the class syntax to define
    a series of cases to be pattern matched.
    """
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, clsname, bases, clsdict):
        if bases is ():
            # Building the base class; no need to do anything.
            return type.__new__(metacls, clsname, bases, clsdict)
        # Pull list of cases out of the class definition.
        cases = [Case(name, func, ptrn)
                 for name, func in clsdict.items()
                 for ptrn in [ get_pattern(func) ]
                 if ptrn is not None]
        for case in cases: del clsdict[case.name]
        clsdict['_cases'] = cases
        return type.__new__(metacls, clsname, bases, clsdict)

    def __init__(cls, name, bases, clsdict):
        # Do this stuff in __init__ because the class needs to
        # be constructed in case there is a free variable that
        # refers to it.
        if hasattr(cls, '_cases'):
            cls._cases = [cls.fixup_args(case) for case in cls._cases]

    def fixup_args(cls, case):
        """If a case doesn't have a second argument to accept the
        bound values from a match, its definition is altered to
        accept arguments for each binding in the pattern.
        """
        wants_args_patched_in = case.action.__code__.co_argcount == 1
        if not wants_args_patched_in:
            case.action.patch_in_args = False
            return case

        args = tuple(extract_bindings(case.pattern))
        if len(args) > 0:
            # Only need to add arguments to
            # the function if there is at least one binding.
            action = cls.add_binding_args_to_func(args, case.action)
            case = case._replace(action=action)
        case.action.patch_in_args = True
        return case

    def add_binding_args_to_func(cls, args, func):
        """Alter the definition of 'func' to accept 'args'."""
        # Get the AST of the function and add extra argument nodes.
        funcast = ast.parse(inspect.getsource(func).strip())
        funcname = funcast.body[0].name
        funcargs = funcast.body[0].args
        funcargs.args = [ ast.arg(funcargs.args[0].arg, None) ]
        funcargs.args.extend(ast.arg(str(a), None) for a in args)
        env = dict()  # An environment in which to evaluate the modded AST.
        if len(func.__code__.co_freevars) < 1:
            # If the function doesn't close over any free variables,
            # it can be evaluated as is.
            exec(compile(funcast, '<generated>', 'exec'),
                 func.__globals__, env)
            newfunc = env[funcname]
        else:
            # TODO: what happens if a freevar is also a binding arg?
            # Have to build a closure.
            clsname = cls.__name__
            freevars = tuple(func.__code__.co_freevars)
            # Pull the values out of the existing closure.
            # When a function is defined in a class and refers to
            # to the class as a free variable it is not included
            # in the closure and has to be added manually.
            closvals = [cell.cell_contents if var != clsname else cls
                        for var, cell in
                        zip(freevars, func.__closure__)]
            # Create a wrapper function to bind the closure values.
            wrapperargs = ', '.join(freevars)
            wrapper = ast.parse("def wrapper(%s):\n"
                                "  def %s(): pass\n"
                                "  return %s" %
                                (wrapperargs, funcname, funcname))
            wrapperfunc = wrapper.body[0]
            # Replace the body of the wrapper with the target function.
            wrapperfunc.body[0] = funcast.body[0]
            # Evaluate the resulting AST and call the
            # wrapper function with the closure values.
            exec(compile(wrapper, '<generated>', 'exec'),
                 func.__globals__, env)
            newfunc = env['wrapper'](*closvals)
        return newfunc

class MatchCases(metaclass=MatchCasesMeta):
    """Base class for building a series of cases
    to match against.
    """
    def __new__(cls, value):
        # Hijack the constructor to just do the
        # matching an return the result instead
        # of constructing an instance. Not sure
        # this the best idea.
        for name, action, pattern in cls._cases:
            try:
                bindings = match(pattern, value)
                break
            except MatchFailed:
                pass
        else:
            raise CasesExhausted('no case for %r in %r' %
                                 (value, cls))

        if action.patch_in_args:
            return action(value, **bindings._asdict())
        else:
            return action(value, bindings)

def ast_kwargs(Ctr, **kwargs):
    return Ctr(*[kwargs.get(field, Binding(field))
                 for field in Ctr._fields])
