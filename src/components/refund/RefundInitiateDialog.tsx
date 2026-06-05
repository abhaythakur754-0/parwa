"use client";

import React, { useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface RefundLineItem {
  line_item_id: string;
  title: string;
  quantity: number;
  price: string;
  refund_quantity: number;
  refund_amount: string;
}

interface RefundInitiateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orderId: string;
  orderItems: Array<{
    id: string;
    title: string;
    quantity: number;
    price: string;
  }>;
  totalAmount: string;
  currency?: string;
  companyId: string;
  onSuccess?: (result: Record<string, unknown>) => void;
}

type RefundStatus = "idle" | "loading" | "success" | "error";

export function RefundInitiateDialog({
  open,
  onOpenChange,
  orderId,
  orderItems,
  totalAmount,
  currency = "USD",
  companyId,
  onSuccess,
}: RefundInitiateDialogProps) {
  const [refundItems, setRefundItems] = useState<RefundLineItem[]>([]);
  const [customAmount, setCustomAmount] = useState("");
  const [reason, setReason] = useState("");
  const [notifyCustomer, setNotifyCustomer] = useState(true);
  const [processPayment, setProcessPayment] = useState(true);
  const [status, setStatus] = useState<RefundStatus>("idle");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  // Initialize refund items from order items
  React.useEffect(() => {
    if (open && orderItems.length > 0) {
      setRefundItems(
        orderItems.map((item) => ({
          line_item_id: item.id,
          title: item.title,
          quantity: item.quantity,
          price: item.price,
          refund_quantity: item.quantity,
          refund_amount: item.price,
        }))
      );
      setCustomAmount("");
      setReason("");
      setStatus("idle");
      setResult(null);
      setError("");
    }
  }, [open, orderItems]);

  const calculateTotalRefund = useCallback(() => {
    if (customAmount) return parseFloat(customAmount) || 0;
    return refundItems.reduce(
      (sum, item) => sum + (parseFloat(item.refund_amount) || 0) * item.refund_quantity,
      0
    );
  }, [customAmount, refundItems]);

  const updateRefundItem = (index: number, field: string, value: string | number) => {
    setRefundItems((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      // Recalculate refund amount if quantity changes
      if (field === "refund_quantity") {
        const qty = typeof value === "number" ? value : parseInt(value) || 0;
        const pricePerUnit = parseFloat(updated[index].price) / updated[index].quantity;
        updated[index].refund_amount = (pricePerUnit * qty).toFixed(2);
      }
      return updated;
    });
  };

  const handleRefund = async () => {
    setStatus("loading");
    setError("");

    try {
      const items = refundItems
        .filter((item) => item.refund_quantity > 0)
        .map((item) => ({
          line_item_id: item.line_item_id,
          quantity: item.refund_quantity,
          amount: item.refund_amount,
        }));

      const response = await fetch("/api/shopify/refund-initiate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: orderId,
          items,
          amount: customAmount || undefined,
          reason,
          currency,
          notify_customer: notifyCustomer,
          process_payment: processPayment,
          company_id: companyId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Refund initiation failed");
      }

      setResult(data);
      setStatus("success");
      onSuccess?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setStatus("error");
    }
  };

  const totalRefund = calculateTotalRefund();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[525px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Initiate Refund
            <Badge variant="outline" className="text-xs">
              Order #{orderId}
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Process a refund for this order. The refund will be created in Shopify and
            {processPayment ? " the payment will be refunded via Paddle." : " payment will NOT be processed."}
          </DialogDescription>
        </DialogHeader>

        {status === "success" && result ? (
          <div className="space-y-4">
            <Alert className="border-green-200 bg-green-50">
              <AlertDescription className="text-green-800">
                Refund processed successfully!
              </AlertDescription>
            </Alert>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Refund ID</span>
                <span className="font-mono">{(result as Record<string, string>).refund_id || "N/A"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Amount</span>
                <span className="font-semibold">
                  {currency} {(result as Record<string, string>).amount || totalRefund.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Shopify Status</span>
                <Badge variant={((result as Record<string, string>).shopify_status || "").includes("processed") ? "default" : "destructive"} className="text-xs">
                  {(result as Record<string, string>).shopify_status || "N/A"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Paddle Status</span>
                <Badge variant={((result as Record<string, string>).paddle_status || "").includes("processed") ? "default" : "secondary"} className="text-xs">
                  {(result as Record<string, string>).paddle_status || "skipped"}
                </Badge>
              </div>
              {(result as Record<string, boolean>).requires_reconciliation && (
                <Alert variant="destructive" className="mt-2">
                  <AlertDescription>
                    This refund requires manual reconciliation. One system succeeded but the other failed.
                  </AlertDescription>
                </Alert>
              )}
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Close</Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Line Items */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Items to Refund</Label>
              {refundItems.map((item, index) => (
                <div
                  key={item.line_item_id}
                  className="flex items-center gap-3 rounded-lg border p-3"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {currency} {item.price} x {item.quantity}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs">Qty</Label>
                    <Input
                      type="number"
                      min={0}
                      max={item.quantity}
                      value={item.refund_quantity}
                      onChange={(e) =>
                        updateRefundItem(
                          index,
                          "refund_quantity",
                          parseInt(e.target.value) || 0
                        )
                      }
                      className="w-16 h-8 text-center"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs">Amount</Label>
                    <Input
                      type="text"
                      value={item.refund_amount}
                      onChange={(e) =>
                        updateRefundItem(index, "refund_amount", e.target.value)
                      }
                      className="w-20 h-8 text-right"
                    />
                  </div>
                </div>
              ))}
            </div>

            <Separator />

            {/* Custom Total Amount Override */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Custom Total Amount (optional)</Label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{currency}</span>
                <Input
                  type="text"
                  placeholder={`Auto-calculated: ${totalRefund.toFixed(2)}`}
                  value={customAmount}
                  onChange={(e) => setCustomAmount(e.target.value)}
                  className="flex-1"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Override the total refund amount. Leave empty to use the sum of item amounts.
              </p>
            </div>

            {/* Refund Total */}
            <div className="rounded-lg bg-muted p-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Total Refund</span>
                <span className="text-lg font-bold">
                  {currency} {totalRefund.toFixed(2)}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Original order total: {currency} {totalAmount}
              </p>
            </div>

            {/* Reason */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Reason</Label>
              <Textarea
                placeholder="Why is this refund being initiated? (e.g., Product defective, Duplicate order, Customer request)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
              />
            </div>

            {/* Options */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-sm">Notify Customer</Label>
                  <p className="text-xs text-muted-foreground">
                    Send refund confirmation email
                  </p>
                </div>
                <Switch
                  checked={notifyCustomer}
                  onCheckedChange={setNotifyCustomer}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-sm">Process Payment Refund</Label>
                  <p className="text-xs text-muted-foreground">
                    Refund payment via Paddle
                  </p>
                </div>
                <Switch
                  checked={processPayment}
                  onCheckedChange={setProcessPayment}
                />
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Actions */}
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={status === "loading"}
              >
                Cancel
              </Button>
              <Button
                onClick={handleRefund}
                disabled={
                  status === "loading" ||
                  refundItems.every((item) => item.refund_quantity === 0)
                }
                variant="destructive"
              >
                {status === "loading" ? "Processing..." : `Refund ${currency} ${totalRefund.toFixed(2)}`}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default RefundInitiateDialog;
