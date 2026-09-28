# LLM rater (Claude) vs the team majority, 90 overlap records

The LLM rater is not a team rater: it is not in Fleiss' Kappa and does not accept or reject any row.
Compared: 90 overlap records with a team majority.

| question | LLM % Y | team majority % Y | raw agreement | Cohen's kappa | Gwet's AC1 |
|---|---|---|---|---|---|
| Q1_degraded_same_task | 97.8% | 98.9% | 96.7% | -0.015 (poor) | 0.966 |
| Q2_degraded_realistic | 78.9% | 100.0% | 78.9% | 0.000 (poor) | 0.740 |
| Q3_optimized_same_intent | 71.1% | 98.9% | 70.0% | -0.022 (poor) | 0.597 |
| Q4_optimized_better | 98.9% | 100.0% | 98.9% | 0.000 (poor) | 0.989 |
| Q5_category_correct | 74.4% | 100.0% | 74.4% | 0.000 (poor) | 0.671 |
| accept | 42.2% | 97.8% | 42.2% | -0.006 (poor) | 0.004 |

## Acceptance rate on the overlap set

| rater | accepted | rate |
|---|---|---|
| Nirzara Manade | 85/90 | 94.4% |
| Piush Gogi | 78/90 | 86.7% |
| Siddhi Bolaikar | 70/90 | 77.8% |
| team majority (the decision) | 88/90 | 97.8% |
| LLM rater (Claude) | 38/90 | 42.2% |

## LLM says N, team majority accepted (51 rows)

No human re-check was done (the team finished rating). These rows stay as the team decided, except 9 of them, removed by the automatic LLM-assisted filter (llm_filter.csv; its 10th flagged row, dolly-1950, was already rejected by the team).

| source_id | category | split | LLM N on | LLM reason |
|---|---|---|---|---|
| codealpaca-10498 | coding | benchmark | Q3 | Q3: adds a function wrapper and a 'specified number of terms' parameter the original did not ask for |
| codealpaca-16240 | coding | val | Q3 | Q3: adds a required function name (split_equal_sum) and a return-None rule not in the original |
| codealpaca-18059 | coding | train | Q3 | Q3: adds an ordering requirement (order of the first list) not in the original |
| codealpaca-18944 | coding | train | Q2 | Q2: degraded is a near-copy of the original instruction, not a vaguer version |
| codealpaca-2655 | coding | train | Q3 | Q3: adds a required function name (find_max) and also bans sorting functions |
| codealpaca-4104 | coding | train | Q3 | Q3: requires printing the sum, which the JavaScript code does not do |
| codealpaca-7427 | coding | train | Q3 | Q3: drops the for-loop requirement and wraps the task in a function |
| codealpaca-913 | coding | train | Q3 | Q3: adds an in-place requirement not in the original |
| codealpaca-9857 | coding | train | Q3 | Q3: asks only for the length, the original asks to find the substring itself |
| dolly-10083 | summarization | train | Q5 | Q5: plain factual question, should be closed_qa |
| dolly-10157 | summarization | train | Q2 | Q2: degraded is a near-verbatim copy of the original (simple -> quick) |
| dolly-12797 | summarization | train | Q3, Q5 | Q3: drops 'short' and the grouping by real-world place; Q5: listing regions from the text is debatable, closer to information_extraction |
| dolly-12818 | classification | train | Q2 | Q2: degraded is a near-verbatim copy of the original |
| dolly-12913 | summarization | train | Q2, Q5 | Q2: degraded is a lowercase copy of the original; Q5: plain factual question, should be closed_qa |
| dolly-12914 | information_extraction | test | Q3, Q4, Q5 | Q3: turns 'what is Colour the World' (a song) into 'identify a colour', a different task; Q4: optimized prompt is wrong so not an improvement; Q5: 'what is X' question, should be closed_qa |
| dolly-1329 | summarization | train | Q3 | Q3: adds a 3-5 item limit, the passage lists more control-plane components |
| dolly-13367 | summarization | train | Q5 | Q5: plain question about how someone died, should be closed_qa |
| dolly-13946 | information_extraction | train | Q5 | Q5: a question answered from the passage, closed_qa is at least as fitting |
| dolly-14279 | information_extraction | train | Q5 | Q5: a plain 'what is' question, closed_qa is at least as fitting |
| dolly-14388 | information_extraction | train | Q5 | Q5: a plain question, closed_qa is at least as fitting |
| dolly-14441 | summarization | train | Q3, Q5 | Q3: turns 'what is X' into a 2-3 sentence summary that must include the release date; Q5: 'what is' question, should be closed_qa |
| dolly-2099 | information_extraction | train | Q2 | Q2: 'jesse lafoll...' is an artificially truncated name, not how a user types |
| dolly-2122 | summarization | train | Q2 | Q2: degraded is a lowercase copy of the original instruction |
| dolly-257 | summarization | train | Q3 | Q3: states the answer ('genetic factors', 'lack of a permanent cure') inside the prompt |
| dolly-2662 | summarization | train | Q5 | Q5: a question answered from the passage, closed_qa is at least as fitting |
| dolly-3291 | closed_qa | train | Q2, Q3 | Q2: degraded is a lowercase copy of the original; Q3: 'no more than three words' cannot hold the full answer (green or reddish leaves; white, yellow or red stalks) |
| dolly-3485 | classification | train | Q2 | Q2: degraded is a near-verbatim copy of the original (the following -> these) |
| dolly-3986 | summarization | train | Q3, Q5 | Q3: lists the answer's content (quarterly review, ranking criteria) in the prompt; Q5: 'how is X selected' question, closed_qa is at least as fitting |
| dolly-40 | summarization | train | Q3 | Q3: drops 'using examples taken from the text' and says 'estimate' the cost instead of reporting it |
| dolly-4205 | summarization | test | Q2, Q3, Q5 | Q2: degraded is a lowercase copy of the original; Q3: adds a 3-bullet structure incl. 'historical relevance' not in the text; Q5: 'why' question, closed_qa is at least as fitting [CONTAMINATED: faculty answer for this row was seen before rating] |
| dolly-4373 | information_extraction | train | Q1, Q5 | Q1: 'movies she made' is broader than 'films produced' (she was also an actress); Q5: a plain question, closed_qa is at least as fitting |
| dolly-4384 | closed_qa | train | Q2, Q3 | Q2: degraded is a lowercase copy of the original; Q3: 'a single number' cannot express the text's 'more than 60' |
| dolly-4618 | closed_qa | train | Q2 | Q2: degraded is a near-verbatim copy of the original (major -> main) |
| dolly-4651 | closed_qa | train | Q2 | Q2: degraded is a lowercase copy of the original |
| dolly-4852 | closed_qa | val | Q3 | Q3: a 1-2 sentence limit forces dropping most of the listed innovations |
| dolly-5272 | closed_qa | train | Q2 | Q2: degraded is a lowercase copy of the original |
| dolly-5480 | closed_qa | val | Q2 | Q2: degraded is a lowercase copy of the original |
| dolly-5580 | information_extraction | train | Q5 | Q5: a plain 'what does X do' question, closed_qa is at least as fitting |
| dolly-5695 | closed_qa | train | Q2 | Q2: degraded differs from the original only by a contraction |
| dolly-5827 | information_extraction | train | Q1, Q3, Q5 | Q1: original ('for what is known as') may ask for its other names, degraded asks for a definition; Q3: same shift to a definition; Q5: a question, closed_qa is at least as fitting |
| dolly-6576 | summarization | train | Q5 | Q5: listing names from the passage is information_extraction, not summarization |
| dolly-7248 | information_extraction | train | Q5 | Q5: a plain question, closed_qa is at least as fitting |
| dolly-7409 | summarization | train | Q2, Q3, Q5 | Q2: degraded is a lowercase copy of the original; Q3: turns 'who is X' into a 3-4 sentence career summary with a required focus; Q5: 'who is' question, should be closed_qa |
| dolly-7569 | summarization | train | Q3, Q5 | Q3: states the answer's content (water flow, supports other species) in the prompt; Q5: a plain question, closed_qa is at least as fitting |
| dolly-8401 | information_extraction | train | Q5 | Q5: a plain question, closed_qa is at least as fitting |
| dolly-8473 | closed_qa | train | Q2 | Q2: degraded differs from the original only by a contraction |
| dolly-8748 | summarization | train | Q2, Q3, Q5 | Q2: degraded is a near-verbatim copy (added 'so', contraction); Q3: asserts the answer (shift from children to broader demographics) and forces exactly three sentences; Q5: a plain question, closed_qa is at least as fitting |
| dolly-8925 | closed_qa | train | Q3 | Q3: adds required fields (sale price and date) the original did not ask for |
| dolly-9245 | summarization | train | Q3, Q5 | Q3: asks only for the counts, the original asks what the divisions are; Q5: a plain question, closed_qa is at least as fitting |
| dolly-9724 | classification | train | Q2 | Q2: degraded is an exact lowercase copy of the original |
| dolly-9750 | information_extraction | train | Q5 | Q5: a plain question, closed_qa is at least as fitting |
