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

    def test_custom_bengali_category(self):
        result = parse_expense("5000 খরির টাকা", CATEGORIES)
        self.assertEqual(result.amount, 5000)
        self.assertEqual(result.category, "খরির টাকা")

    def test_custom_transport_category(self):
        result = parse_expense("3000 গাড়ি ভাড়া", CATEGORIES)
        self.assertEqual(result.amount, 3000)
        self.assertEqual(result.category, "গাড়ি ভাড়া")

    def test_custom_category_whitespace_is_normalized(self):
        result = parse_expense("1000   দোকানের   নাস্তা", CATEGORIES)
        self.assertEqual(result.category, "দোকানের নাস্তা")

    def test_zero_is_rejected(self):
        self.assertIsNone(parse_expense("0 বেতন", CATEGORIES))


if __name__ == "__main__":
    unittest.main()
