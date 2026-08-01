# V5.2 Stable পরিবর্তন

- আগের `products.json` rules অক্ষত রেখে Pain Oil alias যোগ করা হয়েছে:
  - আল বোরাক অয়েল / আল বোরাক অয়েল
  - AL BORAK OIL / AL BORAQ OIL
  - BORAK / BORAQ / BURAK OIL
- Hair Oil 100ml এবং Pain Oil শুধু অটোমেটিক পাঠানো হবে।
- Hair Oil 200ml, Mixed Orders এবং Unknown Product button চাপলে পাঠানো হবে।
- Quantity 2 বা তার বেশি এবং `||` mixed descriptions মূল Hair/Pain Excel-এ থাকবে না।
- এগুলো Database, COD, Dashboard এবং Quantity report-এর হিসাবে থাকবে।
- সব export cache করা হয় এবং Import delete করলে linked cached files delete হয়।
- Duplicate নিয়ম অপরিবর্তিত: Consignment ID অথবা Merchant Order ID।
