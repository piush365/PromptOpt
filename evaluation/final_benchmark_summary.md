# Evaluation run `final-benchmark`

Target `cerebras/gpt-oss-120b` (temperature 0, max 2048 tokens, reasoning low); judge `qwen/qwen3.8-27b`, blind to the variant. Quality 0-10. Task success over checkable items (count in brackets). Output tokens include the model's hidden reasoning tokens (shown separately).

| category | variant | n | quality | task success | input tok | output tok | of which reasoning | total tok | latency ms | truncated |
|---|---|---|---|---|---|---|---|---|---|---|
| classification | dataset_target | 8 | 8.6 | 57% (7) | 117 | 95 | 50 | 212 | 876 | 0 |
| classification | degraded | 8 | 7.5 | 43% (7) | 90 | 412 | 43 | 502 | 789 | 0 |
| classification | stage_b | 8 | 10.0 | 86% (7) | 118 | 99 | 63 | 217 | 656 | 0 |
| closed_qa | dataset_target | 10 | 8.8 | 90% (10) | 283 | 89 | 49 | 372 | 1270 | 0 |
| closed_qa | degraded | 10 | 8.6 | 90% (10) | 267 | 739 | 22 | 1005 | 1264 | 1 |
| closed_qa | stage_b | 10 | 9.0 | 90% (10) | 279 | 82 | 15 | 361 | 676 | 0 |
| coding | dataset_target | 10 | 8.9 | 90% (10) | 116 | 264 | 13 | 380 | 1497 | 0 |
| coding | degraded | 10 | 8.0 | 60% (10) | 91 | 1007 | 15 | 1098 | 1218 | 1 |
| coding | stage_b | 10 | 7.8 | 80% (10) | 100 | 341 | 14 | 441 | 1031 | 1 |
| information_extraction | dataset_target | 10 | 8.9 | - | 350 | 66 | 32 | 416 | 1309 | 0 |
| information_extraction | degraded | 10 | 8.1 | - | 333 | 392 | 27 | 725 | 1348 | 0 |
| information_extraction | stage_b | 10 | 8.9 | - | 346 | 91 | 34 | 437 | 733 | 0 |
| summarization | dataset_target | 6 | 10.0 | - | 374 | 120 | 13 | 495 | 759 | 0 |
| summarization | degraded | 6 | 9.0 | - | 350 | 826 | 13 | 1176 | 1473 | 0 |
| summarization | stage_b | 6 | 10.0 | - | 361 | 116 | 9 | 477 | 731 | 0 |
| **all** | degraded | 44 | 8.2 | 67% (27) | 221 | 673 | 24 | 894 | 1215 | 2 |
| **all** | stage_b | 44 | 9.0 | 85% (27) | 235 | 151 | 27 | 386 | 773 | 1 |
| **all** | dataset_target | 44 | 9.0 | 81% (27) | 242 | 129 | 32 | 371 | 1189 | 0 |
