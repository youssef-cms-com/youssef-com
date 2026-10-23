YOUSSEF.COM v9.4 Products management update

- Centralized editable currency-to-MAD rates at the top of Products.
- Search box and market filter over imported products.
- Edit product name, base price, and base commission inline.
- Retained Add offer link for each product, with optional reference date.
- New product form reads its market currency conversion from the centralized settings.
- Existing imported offers and product records are preserved during application upgrade.
- Product editing does not automatically recalculate old deliveries. Changing currency settings updates the current product conversion rates, not historical delivery records.

This is a Python backend release for Railway or a compatible Python host, NOT a Netlify Drop static build. Back up the database before production upgrade.
