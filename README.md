# auto_doc_ai
A weekend project to generate an automated DMV document workflow pipeline.

## Cross-State Field Implementations

Fields and sections found across US state vehicle titles. Checked when added to the variant pool.

### High Priority
- [x] Title brand / remarks field (SALVAGE, REBUILT, FLOOD, LEMON, etc.)
- [x] Color field in most vehicle_info variants
- [x] License plate number
- [x] Notary block (required in ~15+ states for transfers)
- [x] Purchase / sale price on transfer sections
- [x] Odometer EXEMPT checkbox (vehicles 20+ model years)
- [x] Title type indicator (Original / Duplicate / Corrected / Salvage)

### Medium Priority
- [x] Previous title state / number (out-of-state transfers)
- [x] Damage disclosure statement (separate section, ~6+ states)
- [x] County of issuance
- [x] Ownership type (AND / OR / JTWROS)
- [x] Driver license / ID number for buyer/seller
- [x] Transfer on Death (TOD) beneficiary (10+ states)

### Lower Priority / State-Specific
- [ ] VIN verification / inspection block (FL, CA, CO, NH)
- [ ] Power of attorney section (TX, NC, CA, OR)
- [ ] Tax / fee section (PA, CT, IN)
- [ ] Gift transfer checkboxes (TX, CA, MA, MD)
- [ ] Witness lines (LA requires 2 witnesses + notary)
