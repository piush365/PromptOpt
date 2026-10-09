#!/usr/bin/env bash
# Lighthouse (mobile preset) on every page; prints the category scores. Needs the server on $BASE.
BASE=${BASE:-http://127.0.0.1:8765}
mkdir -p .lighthouse
for p in "" compare suite results how history image status; do
  npx --yes lighthouse@12.8.2 "$BASE/$p" --chrome-path="${CHROME:-/usr/bin/google-chrome}" --chrome-flags="--headless=new" \
    --only-categories=performance,accessibility,best-practices --output=json --output-path=".lighthouse/${p:-home}.json" --quiet >/dev/null 2>&1
  python3 -c "
import json; d = json.load(open('.lighthouse/${p:-home}.json'))
print('${p:-home}'.ljust(9), {k: round(v['score'] * 100) for k, v in d['categories'].items()},
      'LCP', d['audits']['largest-contentful-paint']['displayValue'], 'TBT', d['audits']['total-blocking-time']['displayValue'])"
done
