-- Prevent duplicate billing ledger rows when Razorpay retries webhooks.
BEGIN;

DELETE FROM public.invoices
WHERE paddle_invoice_id IS NOT NULL
  AND id NOT IN (
      SELECT MIN(id)
      FROM public.invoices
      WHERE paddle_invoice_id IS NOT NULL
      GROUP BY paddle_invoice_id
  );

DELETE FROM public.transactions
WHERE paddle_transaction_id IS NOT NULL
  AND id NOT IN (
      SELECT MIN(id)
      FROM public.transactions
      WHERE paddle_transaction_id IS NOT NULL
      GROUP BY paddle_transaction_id
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_provider_invoice_id
    ON public.invoices (paddle_invoice_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_provider_transaction_id
    ON public.transactions (paddle_transaction_id);

COMMIT;
