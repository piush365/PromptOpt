# Dataset validation report

| sheet | rows | completed | accepted |
|---|---|---|---|
| Nirzara_Manade | 170 | 170 (100%) | 152 |
| Piush_Gogi | 170 | 170 (100%) | 150 |
| Siddhi_Bolaikar | 170 | 170 (100%) | 138 |
| faculty | 20 | 20 (100%) | 19 |

## Inter-rater agreement (90 of 90 overlap records rated by the whole team)

| question | % Y (prevalence) | raw agreement (all agree) | Fleiss' kappa | interpretation | Gwet's AC1 | PABAK |
|---|---|---|---|---|---|---|
| Q1_degraded_same_task | 96.3% | 90.0% | 0.065 | slight | 0.928 | 0.867 |
| Q2_degraded_realistic | 96.3% | 88.9% | -0.038 | poor | 0.920 | 0.852 |
| Q3_optimized_same_intent | 96.3% | 90.0% | 0.065 | slight | 0.928 | 0.867 |
| Q4_optimized_better | 98.1% | 94.4% | -0.019 | poor | 0.962 | 0.926 |
| Q5_category_correct | 98.1% | 94.4% | -0.019 | poor | 0.962 | 0.926 |
| accept | 86.3% | 67.8% | 0.092 | slight | 0.719 | 0.570 |

## Faculty check (faculty vs the team's majority vote, 20 of 20 faculty records compared)

| question | % Y (prevalence) | percent agreement | Cohen's kappa | interpretation | Gwet's AC1 | PABAK |
|---|---|---|---|---|---|---|
| Q1_degraded_same_task | 95.0% | 90.0% | -0.053 | poor | 0.890 | 0.800 |
| Q2_degraded_realistic | 100.0% | 100.0% | n/a | undefined (all answers identical) | 1.000 | 1.000 |
| Q3_optimized_same_intent | 95.0% | 90.0% | -0.053 | poor | 0.890 | 0.800 |
| Q4_optimized_better | 100.0% | 100.0% | n/a | undefined (all answers identical) | 1.000 | 1.000 |
| Q5_category_correct | 97.5% | 95.0% | 0.000 | poor | 0.947 | 0.900 |
| accept | 92.5% | 85.0% | -0.071 | poor | 0.826 | 0.700 |

An independent check on the team's ratings: the faculty answers do not change any record.

**Kappa paradox.** Kappa subtracts the agreement expected by chance, which is computed from how often each answer is used. When almost every answer is Y (high prevalence), chance agreement is already close to 1, so kappa is low or even negative although the raters agree on nearly every record, and it is undefined (n/a) when one side only ever answers Y. Gwet's AC1 and PABAK (prevalence- and bias-adjusted kappa, 2 x agreement - 1) do not collapse this way, so all of them are reported together with the raw agreement and the prevalence (% Y).

## Acceptance rule

Overlap records (rated by the whole team) are decided per question by majority vote (at least 2 of 3 matching answers); a record is accepted only if the majority answer is Y on all five questions. Extra and v1.2 records (one team member each) take that rater's answers: accepted only if all five are Y. The faculty sheet is an independent check and never decides a record.

## Result

Validated records: **330**, accepted: **295**. Records nobody rated rely on the automatic checks.
Accepted per category: classification 48, closed_qa 56, coding 53, information_extraction 72, summarization 66
