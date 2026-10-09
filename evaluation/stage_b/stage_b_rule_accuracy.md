# Stage B per-rule accuracy: `test` split

482 degraded prompts through Stage A + Stage B (frozen rules; measurement only). Expected = the dataset's optimized prompt fixes the rule's defect while the degraded prompt has it, judged with the Stage A detectors (definitions in `app/stage_b/rule_accuracy.py`); fired = the rule's change-log entry. **The targets are LLM-written**, so expected is the LLM's choice, not a human gold label: a rule that adds what the LLM left out counts as a false positive, and a target that adds what Stage B deliberately does not (e.g. a format below the 0.6 confidence gate) counts as a false negative.

| rule | change-log code | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| B01 | B01_REMOVE_FILLER | 18 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| B02 | B02_REMOVE_DUPLICATES | 0 | 1 | 0 | 0.000 | - | - |
| B03 | B03_ADD_OUTPUT_FORMAT | 243 | 52 | 124 | 0.824 | 0.662 | 0.734 |
| B04 | B04_ADD_LENGTH | 67 | 14 | 146 | 0.827 | 0.315 | 0.456 |
| B05 | B05_ADD_LANGUAGE | 37 | 3 | 2 | 0.925 | 0.949 | 0.937 |
| B06 | B06_ADD_LABELS | 37 | 27 | 20 | 0.578 | 0.649 | 0.612 |
| B07 | B07_STANDARDIZE_STRUCTURE | 17 | 464 | 0 | 0.035 | 1.000 | 0.068 |
| B08 | B08_GROUP_FALLBACK | 109 | 40 | 99 | 0.732 | 0.524 | 0.611 |
| **macro (B01-B08)** | | | | | **0.615** | **0.728** | **0.631** |
| B07, data moved only (not in macro) | B07 fired and set `context` | 14 | 33 | 3 | 0.298 | 0.824 | 0.438 |
| macro, with B07 = data moved | | | | | 0.648 | 0.703 | 0.684 |

Macro = unweighted mean over the rules where the value is defined (B02 has no expected prompt, so its recall and F1 are undefined and left out). B01's expected uses the same filler detector the rule uses, so its perfect score shows consistency, not independent accuracy. Rules share defects (a length can come from B04 or from B08), so a defect fixed by another rule counts as a false negative here.
