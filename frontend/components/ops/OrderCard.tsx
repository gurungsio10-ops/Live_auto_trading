import { Badge } from "@/components/ui/Badge";
import { MoneyValue, QuantityValue, TimestampValue } from "@/components/values";
import type { Order, OrderStatus } from "@/lib/types";

function statusTone(status: OrderStatus) {
  switch (status) {
    case "FILLED":
      return "positive" as const;
    case "REJECTED":
    case "FAILED":
      return "negative" as const;
    case "CANCELLED":
    case "EXPIRED":
      return "neutral" as const;
    case "PARTIALLY_FILLED":
    case "SUBMITTED":
    case "APPROVED":
      return "info" as const;
    case "CREATED":
    case "RISK_PENDING":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}

function statusLabel(status: OrderStatus) {
  return status.replaceAll("_", " ");
}

export function OrderCard({ order }: { order: Order }) {
  return (
    <article className="rounded-card border border-border bg-surface-raised/40 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-foreground">{order.symbol}</p>
          <p className="mt-0.5 text-[12px] uppercase tracking-wide text-secondary">
            {order.side} {order.order_type}
          </p>
        </div>
        <Badge tone={statusTone(order.status)}>{statusLabel(order.status)}</Badge>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
        <div>
          <p className="text-muted">Quantity</p>
          <QuantityValue value={order.quantity} />
        </div>
        <div>
          <p className="text-muted">Price</p>
          <MoneyValue value={order.price ?? order.average_fill_price} size="sm" />
        </div>
        <div>
          <p className="text-muted">Created</p>
          <TimestampValue value={order.created_at} relative />
        </div>
        <div>
          <p className="text-muted">Reference</p>
          <p className="truncate font-mono text-[12px] text-foreground">
            {order.client_order_id || order.id.slice(0, 10)}
          </p>
        </div>
      </div>
    </article>
  );
}
