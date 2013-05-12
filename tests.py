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

import unittest
import adt

class TestSingleton(unittest.TestCase):
    def test_singleton(self):
        s1 = adt.Singleton()
        s2 = adt.Singleton()
        self.assertIs(s1, s2)

    def test_derived_classes(self):
        class Derived(adt.Singleton):
            pass
        d1 = Derived()
        d2 = Derived()
        self.assertIs(d1, d2)

    def test_different_classes(self):
        class Derived1(adt.Singleton):
            pass
        class Derived2(adt.Singleton):
            pass
        d1 = Derived1()
        d2 = Derived2()
        self.assertIsNot(d1, d2)

    def test_as_mixin(self):
        class Base:
            pass
        class Multi(adt.Singleton, Base):
            pass
        m1 = Multi()
        m2 = Multi()
        self.assertIs(m1, m2)

class TestConstraints(unittest.TestCase):
    def test_anything_is_singleton(self):
        a1 = adt.Anything()
        a2 = adt.Anything()
        self.assertIs(a1, a2)

    def test_require_raises_typeerror(self):
        r = adt.Require(str)
        with self.assertRaises(TypeError):
            r.check(42)

    def test_require_accepts_given_type(self):
        r = adt.Require(int)
        r.check(42)

    def test_require_accepts_subtypes(self):
        r = adt.Require(str)
        class Sub(str):
            pass
        r.check(Sub())

class TestAlgebraicMeta(unittest.TestCase):
    def test_algebraic_generic_types_get_variants_list(self):
        class Generic(adt.ADT):
            pass
        self.assertEqual(Generic._variants, [])

        class Variant1(Generic):
            pass
        self.assertEqual(Generic._variants, [Variant1])

        class Variant2(Generic):
            pass
        self.assertEqual(Generic._variants, [Variant1, Variant2])

    def test_variant_types_get_the_right_fields(self):
        class Generic(adt.ADT):
            pass
        class Variant(Generic):
            field1 = adt.Anything()
            field2 = adt.Require(int)
            something_else = 42

        self.assertEqual(Variant._fields, ('field1', 'field2'))
        self.assertEqual(Variant._constraints, [adt.Anything(),
                                                adt.Require(int)])
        self.assertEqual(Variant.something_else, 42)

    def test_singleton_variant_types(self):
        class Generic(adt.ADT):
            pass
        class Variant(Generic):
            pass
        v1 = Variant()
        v2 = Variant()
        self.assertIs(v1, v2)

class TestADTBase(unittest.TestCase):
    def test_cant_instantiate_base_class(self):
        with self.assertRaises(TypeError):
            adt.ADT()

    def test_cant_instantiate_generic_type(self):
        class Generic(adt.ADT):
            pass
        with self.assertRaises(TypeError):
            Generic()

    def test_variants_check_their_constraints(self):
        class Generic(adt.ADT):
            pass
        class Variant(Generic):
            field = adt.Require(int)

        Variant(42)

        with self.assertRaises(TypeError):
            Variant('foo')

    def test_bindings_are_accepted_for_any_type(self):
        class Generic(adt.ADT):
            pass
        class Variant(Generic):
            field = adt.Require(int)

        for b in (adt.Binding('foo'), adt.BindingRest('bar'), adt.Binding('')):
            Variant(b)

if __name__ ==  '__main__':
    unittest.main()
