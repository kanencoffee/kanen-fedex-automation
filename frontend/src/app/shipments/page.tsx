"use client";

import { useEffect, useState } from "react";
import { getShipments, createShipment, refreshTracking, deleteShipment, Shipment } from "@/lib/api";
import TrackingTimeline from "@/components/TrackingTimeline";
import clsx from "clsx";

const STATUS_PILL: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  in_transit: "bg-blue-100 text-blue-800",
  out_for_delivery: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  exception: "bg-red-100 text-red-800",
  returned: "bg-gray-200 text-gray-700",
};

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Shipment | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState({
    tracking_number: "",
    work_order: "",
    customer_name: "",
    customer_email: "",
    service_type: "FEDEX_GROUND",
    expected_cost: "",
    weight_lb: "",
    origin_city: "",
    destination_city: "",
  });

  const load = async () => {
    setLoading(true);
    const data = await getShipments().catch(() => []);
    setShipments(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createShipment({
      ...form,
      expected_cost: form.expected_cost ? parseFloat(form.expected_cost) : undefined,
      weight_lb: form.weight_lb ? parseFloat(form.weight_lb) : undefined,
      work_order: form.work_order || undefined,
    } as any);
    setShowForm(false);
    setForm({ tracking_number: "", work_order: "", customer_name: "", customer_email: "", service_type: "FEDEX_GROUND", expected_cost: "", weight_lb: "", origin_city: "", destination_city: "" });
    load();
  };

  const handleRefresh = async (s: Shipment) => {
    setRefreshing(s.id);
    await refreshTracking(s.id).catch(console.error);
    setRefreshing(null);
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this shipment?")) return;
    await deleteShipment(id);
    if (selected?.id === id) setSelected(null);
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Shipments</h1>
        <button
          onClick={() => setShowForm(true)}
          className="bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-900 transition-colors"
        >
          + Add Shipment
        </button>
      </div>

      {/* Add shipment form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleCreate}
            className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg space-y-4"
          >
            <h2 className="font-bold text-lg">Add Shipment</h2>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Tracking Number *" value={form.tracking_number} onChange={v => setForm(f => ({ ...f, tracking_number: v }))} required />
              <Input label="Work Order #" value={form.work_order} onChange={v => setForm(f => ({ ...f, work_order: v }))} />
              <Input label="Customer Name *" value={form.customer_name} onChange={v => setForm(f => ({ ...f, customer_name: v }))} required />
              <Input label="Customer Email" value={form.customer_email} onChange={v => setForm(f => ({ ...f, customer_email: v }))} type="email" />
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-600">Service Type</label>
                <select
                  value={form.service_type}
                  onChange={e => setForm(f => ({ ...f, service_type: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="FEDEX_GROUND">FedEx Ground</option>
                  <option value="FEDEX_EXPRESS_SAVER">Express Saver</option>
                  <option value="FEDEX_2_DAY">2-Day</option>
                  <option value="PRIORITY_OVERNIGHT">Priority Overnight</option>
                  <option value="STANDARD_OVERNIGHT">Standard Overnight</option>
                </select>
              </div>
              <Input label="Expected Cost ($)" value={form.expected_cost} onChange={v => setForm(f => ({ ...f, expected_cost: v }))} type="number" />
              <Input label="Weight (lbs)" value={form.weight_lb} onChange={v => setForm(f => ({ ...f, weight_lb: v }))} type="number" />
              <Input label="Origin City" value={form.origin_city} onChange={v => setForm(f => ({ ...f, origin_city: v }))} />
              <Input label="Destination City" value={form.destination_city} onChange={v => setForm(f => ({ ...f, destination_city: v }))} />
            </div>
            <div className="flex gap-2 pt-2">
              <button type="submit" className="flex-1 bg-brand-700 text-white py-2 rounded-lg text-sm font-medium hover:bg-brand-900">
                Add Shipment
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="flex-1 border py-2 rounded-lg text-sm">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Shipments table */}
      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                {["Tracking #", "Work Order", "Customer", "Service", "Status", "Est. Delivery", "Actions"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {shipments.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No shipments yet.</td></tr>
              )}
              {shipments.map(s => (
                <tr
                  key={s.id}
                  className={clsx("hover:bg-gray-50 cursor-pointer", selected?.id === s.id && "bg-brand-50")}
                  onClick={() => setSelected(selected?.id === s.id ? null : s)}
                >
                  <td className="px-4 py-3 font-mono text-xs">{s.tracking_number}</td>
                  <td className="px-4 py-3 text-gray-600">{s.work_order || "—"}</td>
                  <td className="px-4 py-3">{s.customer_name}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{s.service_type || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={clsx("px-2 py-0.5 rounded-full text-xs font-medium capitalize", STATUS_PILL[s.status])}>
                      {s.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {s.estimated_delivery ? new Date(s.estimated_delivery).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 flex gap-2" onClick={e => e.stopPropagation()}>
                    <button
                      onClick={() => handleRefresh(s)}
                      disabled={refreshing === s.id}
                      className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                    >
                      {refreshing === s.id ? "…" : "Refresh"}
                    </button>
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tracking timeline drawer */}
      {selected && (
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-700">
              Tracking: <span className="font-mono text-sm">{selected.tracking_number}</span>
            </h2>
            <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
          </div>
          <TrackingTimeline shipmentId={selected.id} />
        </div>
      )}
    </div>
  );
}

function Input({
  label, value, onChange, required, type = "text",
}: {
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
