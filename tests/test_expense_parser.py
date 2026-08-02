import unittest

from expense_parser import parse_expense


CATEGORIES = (
    "নারিকেল তেলের টাকা",
    "তেলের টাকা",
    "পলির টাকা",
    "বেতন",
)


class ExpenseParserTests(unittest.TestCase):
    def test_english_number(self):
        result = parse_expense("10000 তেলের টাকা", CATEGORIES)
        self.assertEqual(result.amount, 10000)
        self.assertEqual(result.category, "তেলের টাকা")

    def test_bangla_number_and_comma(self):
        result = parse_expense("৳১০,৫০০ নারিকেল তেলের টাকা", CATEGORIES)
        self.assertEqual(result.amount, 10500)

    def test_salary(self):
        result = parse_expense("3000 বেতন", CATEGORIES)
        self.assertEqual(result.category, "বেতন")

    def test_unknown_category(self):
        self.assertIsNone(parse_expense("500 খাবার", CATEGORIES))

    def test_zero_is_rejected(self):
        self.assertIsNone(parse_expense("0 বেতন", CATEGORIES))


if __name__ == "__main__":
    unittest.main()
