# Appendix B. Formula index

[Back to the index](README.md)

Every formula used in the project, where it is implemented, and where it is derived or explained.

| # | quantity | formula | code | explained in |
|---|---|---|---|---|
| 1 | cosine similarity (normalized embeddings) | $\text{sim}(a,b) = \mathbf{e}_a \cdot \mathbf{e}_b$ | `stage_a/classifier.py`, dataset checks | 3.6.5, 4.2.1 |
| 2 | k-NN weight | $w_i = \exp((s_i - s_{\max})/\tau)$, $\tau = 0.05$ | `EmbeddingClassifier.knn_scores` | 4.2.3 |
| 3 | k-NN score | $\text{knn}_c = \sum_{y_i = c} w_i / \sum_i w_i$ over the top 25 | same | 4.2.3 |
| 4 | keyword blend | $\text{blend}_c = 0.7\,\text{knn}_c + 0.3\,\text{kw}_c$ (if a cue fired) | `predict_many` | 4.2.4 |
| 5 | logistic head | $p(c \mid \mathbf{x}) = \operatorname{softmax}(W\mathbf{x} + \mathbf{b})_c$, $\mathbf{x} \in \mathbb{R}^{390}$ | `LinearHead` | 4.2.5 |
| 6 | head training objective | $C\sum_i \alpha_{y_i}(-\log p(y_i \mid \mathbf{x}_i)) + \tfrac12\lVert W\rVert^2$, $\alpha_c = N/(K N_c)$ | `build_index.train_head` | 4.2.5 |
| 7 | final category score | $0.5\,\text{blend}_c + 0.5\,p(c \mid \mathbf{x})$ | `predict_many` | 4.2.6 |
| 8 | `other` backstop | keep $= \max(s_{\max},0)/0.6$; scores × keep; other += 1 − keep (if $s_{\max} < 0.3$) | same | 4.2.6 (proof that `other` wins) |
| 9 | precision / recall / F1 / macro-F1 | $P = TP/\text{pred}$, $R = TP/\text{gold}$, $F1 = 2PR/(P+R)$, mean over 5 | `stage_a/evaluate.py`, `stage_b/rule_accuracy.py` | 4.4, 5.7.2 |
| 10 | B08 condition | $\max_c s_c < 0.6 \wedge \text{context} \wedge s_{cqa} + s_{ie} + s_{sum} \ge 0.6$ | `group_applies` | 5.5 |
| 11 | stored confidence | $\operatorname{clip}(\text{base} - 0.2\,\lvert\text{unresolved}\rvert)$ | `optimizer.confidence` | 5.2 |
| 12 | response-length outlier cut | median + 3σ | `dataset_expand.clean_pool` | 3.3 |
| 13 | complexity tertile | $\min(2, \lfloor 3r/N \rfloor)$ | `clean_pool` | 3.3 |
| 14 | rows to sample | $\min(\text{unused}, \lceil \text{needed}/\text{rate} \times 1.05 \rceil)$ | `plan_categories` | 3.6.1 |
| 15 | largest-remainder allocation | $a_k = nN_k/N$; floor; remainders by size | `stratified_pick` | 3.6.2 |
| 16 | Groq pacing | $\max(2.2, 60T/(0.9 \cdot 8000))$ s | `pace_for` | 3.6.4 |
| 17 | repair coverage | content words kept / content words of the payload < 0.5 | `dataset_repair.coverage` | 3.5 |
| 18 | per-item agreement | $P_i = (\sum_j n_{ij}^2 - n)/(n(n-1))$ | `validation.py` | 3.9.1 |
| 19 | Fleiss' κ | $(\bar P - \sum_j p_j^2)/(1 - \sum_j p_j^2)$ | `fleiss_kappa` | 3.9.2, worked example 3.9.4 |
| 20 | Gwet's AC1 | $(\bar P - 2\pi(1-\pi))/(1 - 2\pi(1-\pi))$ | `gwet_ac1` | 3.9.3 |
| 21 | PABAK | $2\bar P - 1$ | `pabak` | 3.9.3 |
| 22 | Cohen's κ | $(p_o - p_e)/(1 - p_e)$, $p_e = \sum_c p_{1c}p_{2c}$ | `cohen_kappa` | 3.9.6 |
| 23 | forced-subset sizes | $P(1) = 1/2$, $P(2) = 3/8$, $P(3) = 1/8$ | `stage_c/data.build` | 6.3 |
| 24 | LoRA forward | $h = W_0x + (\alpha/r)BAx$ | peft | 6.6 |
| 25 | LoRA parameter count | $r(d_{in} + d_{out})$ per projection → 8,798,208 | – | 6.6 |
| 26 | causal-LM loss on the answer | $-\frac{1}{\lvert T\rvert}\sum_{t \in T}\log p_\theta(x_t \mid x_{<t})$ | `train.py`, HF loss | 6.7.1 |
| 27 | AdamW | $m_t, v_t$ moments; $\theta \leftarrow \theta - \eta(\hat m/(\sqrt{\hat v}+\epsilon) + \lambda\theta)$ | PyTorch | 6.7.2 |
| 28 | learning-rate schedule | linear warm-up $(s+1)/W$, then $(T-s)/(T-W)$ | `train.py` | 6.7.2 |
| 29 | gradient clipping | $g \leftarrow g\min(1, 1/\lVert g\rVert)$ | `train.py` | 6.7.2 |
| 30 | perplexity | $e^{\text{val loss}}$ = $e^{0.7047}$ = 2.02 | – | 6.7.3 |
| 31 | p95 | sorted value at $\min(n-1, \lfloor 0.95n \rfloor)$ | `stage_c/evaluate.latency` | 6.10 |
| 32 | fence length | $\max(3, L+1)$ backticks | `rendering.fence` | 7.1.1 |
| 33 | approximate tokens | $\max(1, \operatorname{round}(\text{chars}/4))$ | `rendering.count_tokens` | 7.2 |
| 34 | per-prompt token reduction | $r_i = 100(b_i - a_i)/b_i$ | `evaluation/tokens.reduction` | 8.3 |
| 35 | aggregate reduction | $R = 100(\sum b - \sum a)/\sum b = \sum_i (b_i/\sum b)\, r_i$ | `tokens.summary` | 8.3 (derivation) |
| 36 | percentile bootstrap CI | resample means; positions $\lfloor 0.025B \rfloor$, $\lfloor 0.975B \rfloor - 1$ | `bootstrap_ci` | 8.3.1 |
| 37 | Wilcoxon signed-rank | ranks of $\lvert d_i\rvert$; normal approximation for large $n$ | SciPy | 8.3.2 |
| 38 | sign test / exact McNemar | $\min(1, 2\sum_{i \le k}\binom{n}{i}2^{-n})$ | `_sign_test`, `mcnemar_exact` | 8.4 |
| 39 | cost and its sensitivity | $(T_{in}p_{in} + T_{out}p_{out})/10^6$; saving as a function of $\rho = p_{out}/p_{in}$ | – | 8.6 |
| 40 | Compare change | $100(a - b)/b$ (negative = fewer) | `compare/service._change` | 12.1.2 |
| 41 | net token change | $(\text{opt}_{in} + \text{opt}_{out}) - (\text{orig}_{in} + \text{orig}_{out})$ | `TokenUsage.net_token_change` | 13.3.1 |
| 42 | CLIPScore | $100\cos(\mathbf{v}_I, \mathbf{t}_T)$ | `image/generate.score` | 11.4 |
| 43 | style adherence | softmax over $\lambda\cos$ with "a ⟨style⟩" vs "a photograph"; kept if > 0.5 | same | 11.4 |
| 44 | Stable Diffusion size | $s = \sqrt{512^2/(wh)}$, round $ws$ and $hs$ to multiples of 8 | `render.sd_size`, `v2.render_v2` | 11.3 |
| 45 | rate-limit pacing | $60/2.2 = 27.3$ req/min; $3600/24.5 = 146.9$ req/h | clients | 13.6.1 |
