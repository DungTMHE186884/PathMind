@echo off
rem Copy to local.env.bat (git-ignored) and fill in. start.bat loads it.
rem ---- VNPAY (sandbox first: https://sandbox.vnpayment.vn/devreg/) ----
set VNPAY_TMN_CODE=
set VNPAY_HASH_SECRET=
set VNPAY_ENV=sandbox
set PATHMIND_PUBLIC_URL=http://localhost:3782
rem ---- Demo payment buttons: must be false on the real site ----
set BILLING_DEMO_MODE=true
