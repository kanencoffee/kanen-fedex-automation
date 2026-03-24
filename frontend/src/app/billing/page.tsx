"use client";

import { useEffect, useState } from "react";
import {
  getBillingRecords, getBillingSummary, ingestInvoiceLine,
  resolveBillingRecord, billingCsvUrl,
  BillingRecord, BillingSummary,
} from "@/lib/api";
import clsx from "clsx";

export default function BillingPage() {
  const [records, setRecords] = useState<BillingRecord[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [loading, setLoading] = useState(true);

  // Ingest form
  const [form, setForm] = useState({
    tracking_number: "",
    invoice_number: "",
    actual_cost: "",
    service_type_billed: "",
  });

  const load = async () => {
    setLoading(true);
    const [r, s] = await Promise.all([
      getBillingRecords(flaggedOnly).catch(() => []),
      getBillingSummary().catch(() => null),
    ]);
    setRecords(r);
    setSummary(s);
    setLoading(false);
  };

  useEffect(() => { load(); }, [flaggedOnly]);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    await ingestInvoiceLine({
      tracking_number: form.tracking_number,
      invoice_number: form.invoice_number || undefined,
      actual_cost: parseFloat(form.actual_cost),
      service_type_billed: form.service_type_billed || undefined,
    });
    setShowIngest(false);
    setForm({ tracking_number: "", invoice_number: "", actual_cost: "", service_type_billed: "" });
    load();
  };

  const handleResolve = async (id: string) => {
    const note = prompt("Optional note for resolution:");
    await resolveBillingRecord(id, note || undefined);
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-800">Billing Audit</h1>
        <div className="flex gap-2">
          <a
            href={billingCsvUrl()}
            download
            className="border px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-100"
          >
            ↓ Export CSV
          </a>
          <button
            onClick={() => setShowIngest(true)}
            className="bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-900"
          >
            + Ingest Invoice Line
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SummaryCard label="Total Invoices" value={summary.total_invoices} />
          <SummaryCard
            label="Flagged (open)"
            value={summary.flagged_unresolved}
            accent={summary.flagged_unresolved > 0 ? "red" : "green"}
          />
          <SummaryCard
            label="Total Discrepancy"
            value={`$${summary.total_discrepancy_usd.toFixed(2)}`}
            accent={summary.total_discrepancy_usd > 0 ? "orange" : "green"}
          />
          <SummaryCard
            label="Total Overcharged"
            value={`$${summary.total_overcharged_usd.toFixed(2)}`}
            accent={summary.total_overcharged_usd > 0 ? "red" : "green"}
          />
        </div>
      )}

      {/* Filter toggle */}
      <div className="flex gap-2 text-sm">
        <button
          onClick={() => setFlaggedOnly(false)}
          className={clsx("px-3 py-1.5 rounded-lg", !flaggedOnly ? "bg-brand-700 text-white" : "border text-gray-600")}
        >
          All
        </button>
        <button
          onClick={() => setFlaggedOnly(true)}
          className={clsx("px-3 py-1.5 rounded-lg", flaggedOnly ? "bg-red-600 text-white" : "border text-gray-600")}
        >
          Flagged only
        </button>
      </div>

      {/* Ingest modal */}
      {showIngest && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleIngest}
            className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md space-y-4"
          >
            <h2 className="font-bold text-lg">Ingest Invoice Line</h2>
            <p className="text-sm text-gray-500">
              Enter one line from a FedEx invoice. The system will auto-compare against your expected cost.
            </p>
            <FInput label="Tracking Number *" value={form.tracking_number} onChange={v => setForm(f => ({ ...f, tracking_number: v }))} required />
            <FInput label="Invoice Number" value={form.invoice_number} onChange={v => setForm(f => ({ ...f, invoice_number: v }))} />
            <FInput label="Actual Cost ($) *" value={form.actual_cost} onChange={v => setForm(f => ({ ...f, actual_cost: v }))} type="number" required />
            <FInput label="Service Type Billed" value={form.service_type_billed} onChange={v => setForm(f => ({ ...f, service_type_billed: v }))} />
            <div className="flex gap-2 pt-1">
              <button type="submit" className="flex-1 bg-brand-700 text-white py-2 rounded-lg text-sm font-medium">
                Ingest
              </button>
              <button type="button" onClick={() => setShowIngest(false)} className="flex-1 border py-2 rounded-lg text-sm">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Records table */}
      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                {["Invoice #", "Tracking #", "Work Order", "Customer", "Expected", "Actual", "Discrepancy", "Status", "Actions"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {records.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">No records found.</td></tr>
              )}
              {records.map(r => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-500">{r.invoice_number || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{r.tracking_number || "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{r.work_order || "—"}</td>
                  <td className="px-4 py-3">{r.customer_name || "—"}</td>
                  <td className="px-4 py-3">${r.expected_cost.toFixed(2)}</td>
                  <td className="px-4 py-3">${r.actual_cost.toFixed(2)}</td>
                  <td className={clsx("px-4 py-3 font-semibold", r.discrepancy > 0 ? "text-red-600" : "text-green-600")}>
                    {r.discrepancy > 0 ? "+" : ""}{r.discrepancy.toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    {r.resolved ? (
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">Resolved</span>
                    ) : r.flagged ? (
                      <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs" title={r.flag_reason ?? ""}>
                        ⚑ Flagged
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">OK</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {r.flagged && !r.resolved && (
                      <button
                        onClick={() => handleResolve(r.id)}
                        className="text-xs text-brand-700 hover:underline"
                      >
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, accent }: { label: string; value: string | number; accent?: "red" | "green" | "orange" }) {
  const colors = {
    red: "bg-red-50 text-red-800",
    green: "bg-green-50 text-green-800",
    orange: "bg-orange-50 text-orange-800",
  };
  return (
    <div className={clsx("rounded-xl px-4 py-3", accent ? colors[accent] : "bg-gray-100 text-gray-800")}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs font-medium mt-1">{label}</div>
    </div>
  );
}

function FInput({ label, value, onChange, required, type = "text" }: {
  label: string; value: string; onChange: (v: string) => void; required?: boolean; type?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-600">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        required={required}
        className="border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
      />
    </div>
  );
}
