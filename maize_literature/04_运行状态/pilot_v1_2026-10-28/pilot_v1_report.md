# PlantKG maize pilot classification v1

Rule version: `plantkg-maize-pilot-v1.0`

This pilot processed only the three sample CSVs and small review workbooks. The full corpus was not read or classified.

The labels mix evidence type (A/B/C/D/E/R) with screening state (X/U). The output therefore keeps `candidate_label` separate from `screening_status`.

Source integrity check: 11 files checked; all unchanged = True.

## Sample CSV outputs

| Input | Rows | A | B | C | D | E | R | X | U |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| screening_review_first30.csv | 30 | 0 | 1 | 3 | 1 | 1 | 1 | 14 | 9 |
| screening_sample_500.csv | 500 | 10 | 19 | 11 | 5 | 3 | 1 | 167 | 284 |
| screening_sample_500_prelabelled.csv | 500 | 10 | 19 | 11 | 5 | 3 | 1 | 167 | 284 |

## Manual comparison

- manual_30_final: 21/30 exact labels (70.0%); 21/30 screening statuses (70.0%).
- manual_6_targeted: 6/6 exact labels (100.0%); 6/6 screening statuses (100.0%).
- manual_36_union: 27/36 exact labels (75.0%); 27/36 screening statuses (75.0%).
- manual_20_separate: 9/20 exact labels (45.0%); 9/20 screening statuses (45.0%).
- unique_56: 36/56 exact labels (64.3%); 36/56 screening statuses (64.3%).

## Dependence and overlap

- 30 final IDs: 30
- Six targeted IDs: 6
- 36 union IDs: 36
- 36 equals 30 union 6: True
- 20 versus 36 overlap: 0
- Two 36-workbook ID sets identical: True

The 36-record workbook is not an independent validation set: it is the 30 final records plus the six targeted candidates. The two 36-record workbooks are derivative copies, and the six-record set is deliberately enriched for A/B evidence.

## Errors in the deduplicated 56-record comparison

- S0295: manual X, pilot U — Coupling self-sustaining air flotation screening with conventional CSTR enhances anaerobic biodegradability of corn stover.
- S0207: manual X, pilot U — Mycorrhizae and grapevines: the known unknowns of their interaction for wine growers' challenges.
- S0259: manual X, pilot U — Cottonseed Density: Associated Physical and Chemical Properties of 10 Cultivars
- S0434: manual X, pilot U — Chemical and Physical Architecture of Macromolecular Gels for Fracturing Fluid Applications in the Oil and Gas Industry; Current Status, Challenges, and Prospects.
- S0200: manual U, pilot B — Lipid peroxidation damage to leaves of Zea mays L. seedlings under calcium deficiency.
- S0394: manual X, pilot U — SARS-CoV-2's closest relative, RaTG13, was generated from a bat transcriptome not a fecal swab: implications for the origin of COVID-19
- S0033: manual X, pilot U — The FAST technique: a simplified Agrobacterium-based transformation method for transient gene expression analysis in seedlings of Arabidopsis and other plant species.
- S0480: manual X, pilot U — A Co-Expression Network in Hexaploid Wheat Reveals Mostly Balanced Expression and Lack of Significant Gene Loss of Homeologous Meiotic Genes Upon Polyploidization.
- S0378: manual X, pilot U — Physical structure and genetic organisation of the genome of maize streak virus (Kenyan isolate).
- S0150: manual X, pilot U — The Putative Mesoamerican Domestication Center of Phaseolus vulgaris Is Located in the Lerma–Santiago Basin of Mexico
- S0262: manual X, pilot U — Estimation of the nuclear DNA content of gossypium species.
- S0221: manual X, pilot U — Protein quality and quantity of quality protein maize (QPM) and non‐QPM hybrids under optimal and low nitrogen conditions
- S0244: manual U, pilot X — Effect of low temperature stress on the expression of sucrose synthetase in spring and winter wheat plants. Development of a monoclonal antibody against wheat germ sucrose synthetase.
- S0411: manual X, pilot U — Recurrent and niche-specific functional bacteriome of maize hybrid revealed by integrated metabarcoding and culturomics.
- S0117: manual X, pilot U — Identification of Compounds Which Account for Variation in P Concentration in Corn Hybrids
- S0316: manual X, pilot B — Chemical structures of corn stover and its residue after dilute acid prehydrolysis and enzymatic hydrolysis: insight into factors limiting enzymatic hydrolysis.
- S0301: manual E, pilot U — Combining Partially Overlapping Multi-Omics Data in Databases Using Relationship Matrices.
- S0175: manual X, pilot U — Review of the existing maximum residue levels for glyphosate according to Article 12 of Regulation (EC) No 396/2005 - revised version to take into account omitted data.
- S0240: manual X, pilot U — Pathways to deeper roots : anatomical phenes of maize under impedance
- S0141: manual X, pilot U — Effects of diets containing gossypol on reproductive capacity of rainbow trout (Oncorhynchus mykiss).
