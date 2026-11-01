YOUSSEF.COM Offer Synchronization v3 - TESTING

Back up the Railway SQLite database before deployment. Replace app.py and server.py together. Do not replace the database.

Editing a product or adding an offer automatically recalculates all imported deliveries for that product across months. Exact price matches override inferred upsells/remises. The historical financial changes and former review decisions are recorded in offer_recalc_audit.

Caution: this recalculates historical months, including closed ones. Review payouts before finalizing. No production deployment performed.
