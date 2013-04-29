from adt import match, MatchCases, Binding as b, BindingRest as r, ast_kwargs as kw
import ast

class MatchMod(MatchCases):
    def module(match: ast.Module):
        for stmt in body:
            yield from MatchStmt(stmt)

class MatchArg(MatchCases):
    def arg(match: kw(ast.arg, annotation=None)):
        return arg

    def annotated(match: ast.arg):
        return '%s: %s' % (arg, MatchExpr(annotation))

def make_bin_op(op):
    return {ast.Add: '+',
            ast.Mod: '%',}[op.__class__]

def make_cmp_op(op):
    return {ast.Gt: '>',
            ast.IsNot: 'is not'}[op.__class__]

def make_call_args(call):
    arg_list = [MatchExpr(a) for a in call.args]
    arg_list.extend(MatchKeyword(kw)
                    for kw in call.keywords)
    if call.starargs is not None:
        arg_list.append('*(%s)' % MatchExpr(call.starargs))
    if call.kwargs is not None:
        arg_list.append('**(%s)' % MatchExpr(call.kwargs))
    return '(%s)' % ', '.join(arg_list)

class MatchKeyword(MatchCases):
    def keyword(match: ast.keyword):
        return '%s=%s' % (arg, MatchExpr(value))

class MatchSlice(MatchCases):
    def slice_end(match: kw(ast.Slice, lower=None)):
        result = ['', MatchExpr(upper)]
        if step is not None:
            result.append(MatchExpr(step))
        return ':'.join(result)

    def slice_begin(match: ast.Slice):
        result = [MatchExpr(lower), MatchExpr(upper)]
        if step is not None:
            result.append(MatchExpr(step))
        return ':'.join(result)

    def index(match: ast.Index):
        return MatchExpr(value)

class MatchComprehension(MatchCases):
    def comp(match: ast.comprehension):
        if_list = (' if %s' % MatchExpr(p)
                   for p in ifs)
        return 'for %s in %s%s' % (
            MatchExpr(target),
            MatchExpr(iter),
            ''.join(if_list))

class MatchExpr(MatchCases):
    def genexpr(match: ast.GeneratorExp):
        comps = (MatchComprehension(c) for c in generators)
        return '(%s %s)' % (MatchExpr(elt), ' '.join(comps))

    def listcomp(match: ast.ListComp):
        comps = (MatchComprehension(c) for c in generators)
        return '[%s %s]' % (MatchExpr(elt), ' '.join(comps))

    def listexpr(match: ast.List):
        return '[%s]' % ', '.join(
            MatchExpr(e) for e in elts)

    def dictexpr(match: ast.Dict):
        pairs = ('%s: %s' % (
            MatchExpr(k), MatchExpr(v))
                 for k, v in zip(keys, values))
        return '{%s}' % ', '.join(pairs)

    def tupleexpr(match: ast.Tuple):
        elements = (MatchExpr(e) + ', '
                    for e in elts)
        return '(%s)' % ''.join(elements)

    def subscript(match: ast.Subscript):
        return '%s[%s]' % (MatchExpr(value),
                           MatchSlice(slice))

    def strexpr(match: ast.Str):
        return repr(s)

    def call(match: ast.Call):
        return MatchExpr(func) + make_call_args(match)

    def yieldexpr(match: ast.Yield):
        return 'yield ' + MatchExpr(value)

    def yieldfrom(match: ast.YieldFrom):
        return 'yield from ' + MatchExpr(value)

    def number(match: ast.Num):
        return str(n)

    def binop(match: ast.BinOp):
        return '(%s %s %s)' % (
            MatchExpr(left),
            make_bin_op(op),
            MatchExpr(right))

    def compare(match: ast.Compare):
        pieces = [MatchExpr(left)]
        pieces.extend(' %s %s' %
                      (make_cmp_op(op), MatchExpr(c))
                      for op, c in zip(ops, comparators))
        return '(%s)' % ''.join(pieces)

    def name(match: ast.Name):
        return id

    def attribute(match: ast.Attribute):
        return MatchExpr(value) + '.' + attr

class MatchArguments(MatchCases):
    def arguments(match: ast.arguments):
        arg_list = [MatchArg(a) for a in args]
        if vararg is not None:
            if varargannotation is not None:
                vararg += ": " + MatchExpr(
                    varargannotation)
            arg_list.append('*' + vararg)
        arg_list.extend(MatchArg(a) for a in kwonlyargs)
        if kwarg is not None:
            if kwargannotation is not None:
                kwarg += ": " + MatchExpr(
                    kwargannotation)
            arg_list.append('**' + kwarg)
        return ', '.join(arg_list)

class MatchAlias(MatchCases):
    def no_alias(match: kw(ast.alias, asname=None)):
        return name

    def alias(match: ast.alias):
        return name + ' as ' + asname

def make_body(body):
    return ('    ' + line
            for stmt in body
            for line in MatchStmt(stmt))

class MatchStmt(MatchCases):
    def assertstmt(match: kw(ast.Assert, msg=None)):
        yield 'assert %s' % ( MatchExpr(test) )

    def assert_with_msg(match: ast.Assert):
        yield 'assert %s, %s' % (
            MatchExpr(test), MatchExpr(msg))

    def importfrom(match: ast.ImportFrom):
        name_list = ', '.join(MatchAlias(a) for a in names)
        yield 'from %s import %s' % (module, name_list)

    def importstmt(match: ast.Import):
        yield 'import %s' % (
            ', '.join(MatchAlias(a) for a in names),)

    def functiondef(match: ast.FunctionDef):
        arg_list = MatchArguments(args)
        yield 'def %s(%s):' % (name, arg_list)
        yield from make_body(body)

    def passstmt(match: ast.Pass):
        yield 'pass'

    def assign(match: ast.Assign):
        target_list = ', '.join(MatchExpr(e)
                                for e in targets)
        yield target_list + ' = ' + MatchExpr(value)

    def augassign(match: ast.AugAssign):
        yield '%s %s= %s' % (
            MatchExpr(target),
            make_bin_op(op),
            MatchExpr(value))

    def classdef(match: ast.ClassDef):
        bases_list = MatchClassBases(bases)
        yield 'class %s%s:' % (name, bases_list)
        yield from make_body(body)

    def forstmt(match: ast.For):
        yield 'for %s in %s:' % (
            MatchExpr(target), MatchExpr(iter))
        yield from make_body(body)
        if len(orelse) > 0:
            yield 'else:'
            yield from make_body(orelse)

    def ifstmt(match: ast.If):
        yield 'if %s:' % MatchExpr(test)
        yield from make_body(body)
        if len(orelse) > 0:
            yield 'else:'
            yield from make_body(orelse)

    def returnstmt(match: ast.Return):
        yield 'return %s' % MatchExpr(value)

    def delete(match: ast.Delete):
        assert False

    def expr(match: ast.Expr):
        yield MatchExpr(value)

class MatchClassBases(MatchCases):
    def empty(match: ()):
        return ""

    def otherwise(match: b('bases')):
        base_list = ', '.join(MatchExpr(base)
                              for base in bases)
        return '(%s)' % base_list

st = ast.parse(open(__file__).read())

for line in MatchMod(st):
    print(line)


