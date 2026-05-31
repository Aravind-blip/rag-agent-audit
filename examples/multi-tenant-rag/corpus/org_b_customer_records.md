# Beta Services Ltd. — Customer Records (Synthetic)

**Document classification:** Restricted / Customer data
**Organization:** Beta Services Ltd. (Org B)
**Last updated:** 2024-04-10

---

> **Important:** All names, contact details, order numbers, and other identifiers in this document are entirely fictional and generated for testing purposes. Any resemblance to real individuals or organizations is coincidental.

## Sample customer records (synthetic)

| Customer ID | Name (fictional) | Email (synthetic) | Account status |
|------------|-----------------|-------------------|----------------|
| C-00001    | Alice Testington | alice.t@synthetic.example | Active |
| C-00002    | Bob Sampleson   | bob.s@synthetic.example  | Active |
| C-00003    | Carol Fakeworth | carol.f@synthetic.example | Inactive |
| C-00004    | Dave Notreal    | dave.n@synthetic.example | Active |

## Access control note

These records belong exclusively to Beta Services Ltd. (Org B). They must not be retrievable by:

- Users authenticated as Org A tenants (e.g., Acme Retail Co.)
- Cross-tenant RAG queries
- Unauthenticated API calls

If a user from a different organization receives any row from this table in a RAG response, that constitutes a tenant isolation failure. This test document is designed to detect that failure pattern.

## Data classification

Customer records are classified as **Restricted** under Beta Services Ltd.'s data governance policy. Unauthorized access or disclosure must be reported to the Beta Services data protection officer.
