-- Make frontend Razorpay subscription creation idempotent per provider order.
-- Existing subscriptions remain valid; only newly verified Razorpay orders
-- populate this nullable reference.
ALTER TABLE public.subscriptions
    ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_razorpay_order_id_key
    ON public.subscriptions (razorpay_order_id);
