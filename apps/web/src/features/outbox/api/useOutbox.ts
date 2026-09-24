/**
 * useOutbox.ts — TanStack Query hook for Outbox Deliveries.
 * DOC 3 §M4 (outbox, channels) · DOC 4 Step C7
 *
 * Real backend only: GET /outbox. Status values are the backend's own DeliveryStatus
 * (alerting/domain/delivery.py): "pending", "sent", "failed" (will retry), "dead" (gave up after
 * max_attempts) — not the fixture's invented "delivered"/"retrying".
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";
import type { Delivery } from "../../../shared/api/types.ts";

export type { Delivery };
/** The backend types `status` as a plain string (looser API coupling); these are its only
 * real values (alerting/domain/delivery.py DeliveryStatus). */
export type DeliveryStatus = "pending" | "sent" | "failed" | "dead";

export function useOutboxDeliveries() {
  return useQuery<Delivery[]>({
    queryKey: ["outbox-deliveries"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/outbox", { params: { query: {} } });
      if (error) throw new Error("Failed to load the outbox");
      return data.items;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
