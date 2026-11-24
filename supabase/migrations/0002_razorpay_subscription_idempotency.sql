-- Make subscription creation idempotent for each Razorpay order.
-- The same verified order must never create multiple subscription rows when
-- the browser retries or two verification requests race.

BEGIN;

ALTER TABLE public.subscriptions
    ADD COLUMN IF NOT EXISTS razorpay_order_id text;

CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_razorpay_order_id_unique
    ON public.subscriptions (razorpay_order_id);

COMMIT;
