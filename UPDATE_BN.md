# BusinessExpenseBot Custom Category Update

## নতুন সুবিধা

এখন তালিকাভুক্ত category ছাড়াও সরাসরি custom expense লেখা যাবে।

উদাহরণ:

- `5000 খরির টাকা`
- `3000 গাড়ি ভাড়া`
- `1500 দোকানের নাস্তা`

Amount-এর পরের পুরো লেখাটি category হিসেবে Google Sheet-এ save হবে। পরিচিত category লিখলে আগের configured category-ই ব্যবহার হবে।

## Replace করতে হবে

- `expense_parser.py`
- `bot.py`

`tests/test_expense_parser.py` শুধু automated test-এর জন্য।
