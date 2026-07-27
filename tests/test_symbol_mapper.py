import unittest

from praecursor.data.symbol_mapper import SymbolMapper


class SymbolMapperTests(unittest.TestCase):
    def test_loads_enabled_symbols_and_source_symbols(self):
        mapper = SymbolMapper.from_csv()
        symbols = mapper.get_symbols()

        self.assertIn("COMI", symbols)
        self.assertIn("SWDY", symbols)
        self.assertEqual(mapper.get_yahoo_symbol("COMI"), "COMI.CA")
        self.assertEqual(mapper.get_stockanalysis_symbol("SWDY"), "SWDY")
        self.assertTrue(mapper.is_enabled("COMI"))


if __name__ == "__main__":
    unittest.main()
