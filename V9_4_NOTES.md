# YOUSSEF.COM v9.4 - TEST BUILD

This is an offline/test candidate, not a production-certified migration.

- Price offers by product: exact delivered price matches commission, regardless of delivery date.
- Optional effective date is informational.
- Closest higher offer creates a pending remise for single-product orders.
- Remise requires explicit approval. Approved gaps converted with product's local-to-MAD rate; 80% deducted from buyer payout.
- Multi-product or quantity 2+ candidates are excluded from automatic remise detection.
- Per-product local-to-MAD rate is editable on Offers page.
- Existing July/August periods are not reset by database initialization.

## Important limitations before production
- Existing imported deliveries must be re-evaluated against offers; do not treat old totals as validated without a backup and comparison.
- Multi-quantity parsing depends on how quantity is represented in source Excel. Verify real examples.
- Currency conversions are currently per product (local_mad) rather than a centrally managed per-currency registry.
- Bulk remise approval, explicit price-offer deletion, export remise audit, and full historical rate-versioning are not yet implemented.
- The legacy date-based Commission History screen remains available and must not be used to replace price offers.
- A real source product/commission file is needed for complete reconciliation.

Do not deploy over production until data backups and end-to-end import tests pass.
