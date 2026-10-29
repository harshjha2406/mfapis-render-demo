#!/usr/bin/env python3
"""Authenticated MFAPIs quote publisher.

Consumes newline-delimited JSON from an EXISTING AUTHORIZED market observation stream.
No prices are generated. No upstream vendor APIs are contacted by this script.
Run: export MFAPIS_URL=https://...; export MFAPIS_INGEST_KEY=...;
     YOUR_AUTHORIZED_FEED_ADAPTER | python scripts/publish_quotes.py
"""
import json
import os
import sys
from urllib.parse import urlsplit
import requests


def main():
    url=os.getenv('MFAPIS_URL','http://127.0.0.1:8000').rstrip('/')
    secret=os.getenv('MFAPIS_INGEST_KEY','').strip()
    parsed=urlsplit(url)
    if len(secret)<32:
        raise SystemExit('Set a secure MFAPIS_INGEST_KEY (at least 32 characters)')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1','::1'}):
        raise SystemExit('Use HTTPS except for local development')
    with requests.Session() as session:
        for i,line in enumerate(sys.stdin,1):
            if not line.strip():continue
            if len(line)>4096:raise SystemExit(f'Line {i}: quotation exceeds supported size')
            try:payload=json.loads(line)
            except json.JSONDecodeError:raise SystemExit(f'Line {i}: invalid JSON') from None
            try:
                r=session.post(url+'/v1/fx/quotes/ingest',json=payload,
                     headers={'X-MFAPIS-Ingest-Key':secret},timeout=10)
                r.raise_for_status()
            except requests.RequestException as exc:
                # Avoid printing headers, URLs containing credentials or response bodies.
                raise SystemExit(f'Line {i}: MFAPIs quote ingestion failed ({type(exc).__name__})') from None
            result=r.json()
            print(f"{i}: {result['symbol']} {result['status']} at {result['as_of']}",flush=True)

if __name__=='__main__':main()
