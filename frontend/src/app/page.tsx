import { getShipmentStats, getBillingSummary } from "@/lib/api";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  in_transit: "bg-blue-100 text-blue-800",
  out_for_delivery: "bg-purple-100 text-purple-800",
  delivered: "bg-green-100 text-green-800",
  exception: "bg-red-100 text-red-800",
  returned: "bg-gray-100 text-gray-700",
};

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [stats, billing] = await Promise.all([
    getShipmentStats().catch(() => ({ total: 0, by_status: {} })),
    getBillingSummary().catch(() => ({
      total_invoices: 0,
      flagged_unresolved: 0,
      total_discrepancy_usd: 0,
      total_overcharged_usd: 0,
    })),
  ]);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-800">Shipment Dashboard</h1>

      {/* Shipment status cards */}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Shipments
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Total" value={stats.total} color="bg-gray-100 text-gray-800" />
          {Object.entries(stats.by_status).map(([status, count]) => (
            <StatCard
              key={status}
              label={status.replace("_", " ")}
              value={count}
              color={STATUS_COLORS[status] ?? "bg-gray-100"}
            />
          ))}
        </div>
        <div className="mt-3">
          <Link
            href="/shipments"
            className="text-sm text-brand-700 font-medium hover:underline"
          >
            View all shipments →
          </Link>
        </div>
      </section>

      {/* Billing summary */}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Billing Audit
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Total Invoices" value={billing.total_invoices} color="bg-gray-100 text-gray-800" />
          <StatCard
            label="Flagged (open)"
            value={billing.flagged_unresolved}
            color={billing.flagged_unresolved > 0 ? "bg-red-100 text-red-800" : "bg-green-100 text-green-800"}
          />
          <StatCard
            label="Total Discrepancy"
            value={`$${billing.total_discrepancy_usd.toFixed(2)}`}
            color={billing.total_discrepancy_usd > 0 ? "bg-orange-100 text-orange-800" : "bg-green-100 text-green-800"}
          />
          <StatCard
            label="Overcharged"
            value={`$${billing.total_overcharged_usd.toFixed(2)}`}
            color={billing.total_overcharged_usd > 0 ? "bg-red-100 text-red-800" : "bg-green-100 text-green-800"}
          />
        </div>
        <div className="mt-3">
          <Link
            href="/billing"
            className="text-sm text-brand-700 font-medium hover:underline"
          >
            Review billing discrepancies →
          </Link>
        </div>
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className={`rounded-xl px-4 py-3 ${color}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs capitalize mt-1 font-medium">{label}</div>
    </div>
  );
}
