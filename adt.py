from collections import OrderedDict, namedtuple
from itertools import zip_longest, chain
import inspect
import ast
import re

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
        if bases[0] is ADT:
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

class ADT(metaclass=AlgebraicMeta):
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
        if not self.isidentifier() and self != '':
            raise TypeError("not a valid Python identifier: %r" % str(self))

    def __repr__(self):
        return 'Binding(%r)' % str(self)

    def bind(self, value):
        return () if self == "" else ((self, value), )

class BindingRest(Binding):
    pass

class MatchFailed(Exception):
    pass

def traverse(pattern, handle):
    if isinstance(pattern, Binding):
        return handle.binding(pattern)

    if isinstance(pattern, type) and issubclass(pattern, ADT):
        if not hasattr(pattern, '_fields'):
            raise TypeError("can't match against generic type %r" % pattern)
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
    return traverse(pattern, BindingExtractor())

class BindingExtractor(Singleton):
    named_group_re = re.compile(r'\(\?P<([^>]+)>')

    def binding(self, binding):
        return [binding]

    def adt_constructor(self, ctr):
        return ctr._fields

    def adt_instance(self, instance):
        return self.sequence(instance)

    def ast_constructor(self, ctr):
        return ctr._fields

    def ast_instance(self, instance):
        return self.sequence(instance.__dict__.values())

    def regexp(self, pattern):
        return self.named_group_re.findall(pattern.pattern)

    def mapping(self, map):
        return self.sequence(map.values())

    def sequence(self, seq):
        return chain(*(extract_bindings(value) for value in seq))

    def literal(self, value):
        return []

def match(pattern, value):
    fields, values = [], []
    for k, v in traverse(pattern, MatchVisitor(value)):
        fields.append(k)
        values.append(v)
    return namedtuple('CapturedValues', fields)(*values)

class MatchVisitor:
    def __init__(self, value):
        self.value = value

    def recur(self, subpattern, subvalue):
        try:
            return traverse(subpattern, MatchVisitor(subvalue))
        except MatchFailed as failure:
            raise MatchFailed("%r didn't match %r" % (subvalue, subpattern)) \
                  from failure

    def binding(self, binding):
        return binding.bind(self.value)

    def adt_constructor(self, ctr):
        if not isinstance(self.value, ctr):
            raise MatchFailed("expected %r, got %r" %
                              (ctr, self.value))
        return zip(ctr._fields, self.value)

    def adt_instance(self, instance):
        if not isinstance(self.value, instance.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (instance, self.value))
        return chain.from_iterable(
            self.recur(subpattern, subvalue)
            for subpattern, subvalue in zip(instance, self.value))

    def ast_constructor(self, ctr):
        if not isinstance(self.value, ctr):
            raise MatchFailed("expected %r, got %r" %
                              (ctr, self.value))
        return ((field, getattr(self.value, field)) for field in ctr._fields)

    def ast_instance(self, instance):
        if not isinstance(self.value, instance.__class__):
            raise MatchFailed("expected %r, got %r" %
                              (instance, self.value))
        return chain.from_iterable(
            self.recur(subpattern, getattr(self.value, field))
            for field, subpattern in instance.__dict__.items())

    def regexp(self, pattern):
        match = pattern.match(self.value)
        if match is None:
            raise MatchFailed("regex %r didn't match %r" %
                              (pattern.pattern, self.value))
        items = match.groupdict().items()
        return sorted(items, key=lambda item: pattern.groupindex[item[0]])

    def mapping(self, map):
        if not hasattr(self.value, 'keys') or not hasattr(self.value, 'values'):
            raise MatchFailed("can't match mapping type pattern with %r"
                              % self.value)
        def recur(key):
            if key not in self.value:
                raise MatchFailed("pattern has key %r not in value" % key)
            return self.recur(map[key], self.value[key])

        keys = map.keys() if isinstance(map, OrderedDict) else sorted(map.keys())
        return chain.from_iterable(recur(key) for key in keys)

    def sequence(self, seq):
        if not hasattr(self.value, '__iter__'):
            raise MatchFailed("can't match sequence with %r" % self.value)

        sentinel = object()
        pieces = zip_longest(seq, self.value, fillvalue=sentinel)

        for subpattern, subvalue in pieces:
            if isinstance(subpattern, BindingRest):
                def rest():
                    yield subvalue
                    yield from (subvalue for subpattern, subvalue in pieces)

                yield from subpattern.bind(rest())
                break

            elif sentinel in (subpattern, subvalue):
                raise MatchFailed("pattern and value had different lengths")

            else:
                yield from self.recur(subpattern, subvalue)

    def literal(self, value):
        if self.value != value:
            raise MatchFailed("%r didn't match %r" % (self.value, value))
        return ()

class CasesExhausted(Exception):
    pass

def get_pattern(func):
    if not callable(func): return None
    argspec = inspect.getfullargspec(func)
    if len(argspec) < 1: return None
    try:
        return argspec.annotations[argspec.args[0]]
    except KeyError:
        return None

Case = namedtuple('Case', 'name action pattern')

class MatchCasesMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return OrderedDict()

    def __new__(metacls, clsname, bases, clsdict):
        if bases is ():
            return type.__new__(metacls, clsname, bases, clsdict)
        cases = [(name, func, ptrn)
                 for name, func in clsdict.items()
                 for ptrn in [ get_pattern(func) ]
                 if ptrn is not None]
        for n, f, p in cases: del clsdict[n]
        clsdict['_cases'] = cases
        return type.__new__(metacls, clsname, bases, clsdict)

    def __init__(cls, name, bases, clsdict):
        if hasattr(cls, '_cases'):
            cls._cases = [cls.make_case(*c) for c in cls._cases]

    def make_case(cls, name, func, ptrn):
        args = extract_bindings(ptrn)
        action = cls.add_binding_args_to_func(args, func)
        return Case(name, action, ptrn)

    def add_binding_args_to_func(cls, args, func):
        args = list(args)
        if len(args) < 1:
            return func

        funcast = ast.parse(inspect.getsource(func).strip())
        funcname = funcast.body[0].name
        funcargs = funcast.body[0].args
        funcargs.args = [ast.arg(funcargs.args[0].arg, None)]
        funcargs.args.extend(ast.arg(str(name), None) for name in args)
        env = dict()
        if len(func.__code__.co_freevars) < 1:
            exec(compile(funcast, '<generated>', 'exec'), func.__globals__, env)
            newfunc = env[funcname]
        else:
            freevars = list(func.__code__.co_freevars)
            closurevals = [cls if var == cls.__name__ else cell.cell_contents
                           for var, cell in zip(freevars, func.__closure__)]
            wrapperargs = ', '.join(freevars)
            wrapper = ast.parse("def wrapper(%s):\n"
                                "  def %s(): pass\n"
                                "  return %s" % (wrapperargs, funcname, funcname))
            wrapperfunc = wrapper.body[0]
            wrapperfunc.body[0] = funcast.body[0]
            exec(compile(wrapper, '<generated>', 'exec'), globals, env)
            newfunc = env['wrapper'](*closurevals)
        return newfunc

class MatchCases(metaclass=MatchCasesMeta):
    def __new__(cls, value):
        for name, action, pattern in cls._cases:
            try:
                bindings = match(pattern, value)
                break
            except MatchFailed:
                pass
        else:
            raise CasesExhausted('no case for %r in %r' %
                                 (value, cls))

        return action(value, **bindings._asdict())

