# Upsell engine patch - review build

- Exact single-unit offers take precedence over inferred multi-unit orders.
- Multiple nonempty product lines are treated as multi-product orders.
- `Pack de 2` inside a product name does NOT imply two ordered units.
- A single-line delivery at >= 1.5x the highest configured single-unit offer is flagged `INFERRED UPSELL - VERIFY QUANTITY` and enters the existing African pending approval workflow if its additional value is positive.
- Africa upsell candidate = max(0, delivered order price - selected base offer price) x 25% x market-to-MAD rate; base commission is separate.
- Morocco uses its configured automatic upsell percentage.
- City-mapping recalculation uses the same classifier as the delivery importer.

## Deployment caution
This is a candidate build, not a production-certified release. Before deploying, back up the production SQLite database and test on a copy. Reimporting deliveries currently replaces delivery rows for that period/source. Do not reimport production files without preserving approval decisions and validating duplicates and historical totals. The >=1.5x heuristic may need adjustment based on the user's actual products and selling practices. The original full export has not been reconciled end-to-end with the production DB.
