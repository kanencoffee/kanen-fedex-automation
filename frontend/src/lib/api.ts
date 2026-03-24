const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ShipmentStatus =
  | "pending"
  | "in_transit"
  | "out_for_delivery"
  | "delivered"
  | "exception"
  | "returned";

export interface Shipment {
  id: string;
  tracking_number: string;
  work_order: string | null;
  customer_name: string;
  customer_email: string | null;
  service_type: string | null;
  status: ShipmentStatus;
  expected_cost: number | null;
  actual_cost: number | null;
  weight_lb: number | null;
  origin_city: string | null;
  destination_city: string | null;
  shipped_at: string | null;
  estimated_delivery: string | null;
  delivered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrackingEvent {
  id: string;
  timestamp: string;
  location: string | null;
  description: string | null;
  event_code: string | null;
}

export interface BillingRecord {
  id: string;
  shipment_id: string;
  invoice_number: string | null;
  expected_cost: number;
  actual_cost: number;
  discrepancy: number;
  service_type_expected: string | null;
  service_type_billed: string | null;
  flagged: boolean;
  flag_reason: string | null;
  resolved: boolean;
  resolved_note: string | null;
  tracking_number: string | null;
  work_order: string | null;
  customer_name: string | null;
}

export interface ShipmentStats {
  total: number;
  by_status: Partial<Record<ShipmentStatus, number>>;
}

export interface BillingSummary {
  total_invoices: number;
  flagged_unresolved: number;
  total_discrepancy_usd: number;
  total_overcharged_usd: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// Shipments
export const getShipments = (params?: string) =>
  apiFetch<Shipment[]>(`/shipments/${params ? `?${params}` : ""}`);

export const getShipmentStats = () => apiFetch<ShipmentStats>("/shipments/stats");

export const getShipment = (id: string) => apiFetch<Shipment>(`/shipments/${id}`);

export const getTrackingEvents = (id: string) =>
  apiFetch<TrackingEvent[]>(`/shipments/${id}/events`);

export const createShipment = (data: Partial<Shipment>) =>
  apiFetch<Shipment>("/shipments/", { method: "POST", body: JSON.stringify(data) });

export const refreshTracking = (id: string) =>
  apiFetch<Shipment>(`/shipments/${id}/refresh`, { method: "POST" });

export const deleteShipment = (id: string) =>
  fetch(`${BASE}/shipments/${id}`, { method: "DELETE" });

// Billing
export const getBillingRecords = (flaggedOnly = false) =>
  apiFetch<BillingRecord[]>(`/billing/?flagged_only=${flaggedOnly}`);

export const getBillingSummary = () => apiFetch<BillingSummary>("/billing/summary");

export const ingestInvoiceLine = (data: {
  tracking_number: string;
  invoice_number?: string;
  actual_cost: number;
  service_type_billed?: string;
}) => apiFetch<BillingRecord>("/billing/ingest", { method: "POST", body: JSON.stringify(data) });

export const resolveBillingRecord = (id: string, note?: string) =>
  apiFetch<BillingRecord>(`/billing/${id}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ resolved_note: note }),
  });

export const billingCsvUrl = () => `${BASE}/billing/export/csv`;
