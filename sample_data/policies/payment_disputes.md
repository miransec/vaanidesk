# VaaniDesk Payment Disputes Policy

**Effective date:** 1 January 2026

## Purpose

This document explains how VaaniDesk handles payment failures, duplicate charges, unauthorized transactions, chargebacks, and reconciliation for UPI, cards, net banking, wallets, EMI, and COD remittance.

## Payment Failure at Checkout

If payment fails but amount debited:

1. Wait **30 minutes** for auto-reversal (UPI/card auth holds)
2. Check bank SMS for "reversal" or "release"
3. If not reversed in **3 business days**, raise dispute with transaction UTR / ARN

Do not reorder until you confirm whether original debit cleared—duplicate orders cause refund delays.

## Duplicate Charges

Duplicate captures occur rarely during gateway timeout retries. Provide both transaction IDs. Verified duplicates refunded within **5 business days**; interim credit may apply for amounts > ₹5,000.

## Unauthorized Transactions

If you did not authorize a charge:

1. Change password and sign out all sessions immediately
2. Contact bank to block card / UPI mandate
3. Email **payments-disputes@vaanidesk.in** within **48 hours** with police FIR optional for amounts > ₹25,000

We suspend linked payment tokens pending investigation. Resolution target: **7 business days**.

## Chargebacks

When you dispute via bank chargeback:

- VaaniDesk submits delivery proof, IP logs (hashed), and device fingerprint summary
- Order fulfillment pauses on active chargeback
- Friendly fraud chargebacks may result in account restriction

Prefer VaaniDesk dispute channel first—faster than bank chargeback cycle (45–90 days).

## EMI & No-Cost EMI

EMI conversion failures: order cancels automatically; first EMI debit reversals follow lender SLA (7–14 days). Pre-closure charges on NCE plans are lender-defined—VaaniDesk displays lender T&C at checkout.

## COD Remittance Disputes

Sellers and delivery partners remit COD separately. If you paid COD but order shows unpaid, provide receipt photo. Investigation with carrier POD within **5 business days**.

## Wallet & Gift Card Balance

Wallet disputes for missing cashback: provide promotion code and order ID. Promotional credits expire per campaign terms shown in wallet ledger.

## Refund Not Received

If order cancelled/refunded but money not credited after stated SLA, submit **Refund Trace** form with bank statement redacting unrelated transactions. We escalate with payment aggregator using RRN.

## Hindi — भुगतान विवाद

Duplicate charge: 5 दिन में refund।  
Unauthorized: 48 घंटे में **payments-disputes@vaanidesk.in**।  
Chargeback से पहले VaaniDesk channel तेज़।  
Refund trace: bank statement + RRN।

## Marathi — payment disputes

Duplicate: 5 days refund.  
Unauthorized: 48 hours **payments-disputes@vaanidesk.in**.  
Refund trace: bank statement + RRN.
