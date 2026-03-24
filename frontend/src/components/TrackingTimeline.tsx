"use client";

import { useEffect, useState } from "react";
import { getTrackingEvents, TrackingEvent } from "@/lib/api";

const EVENT_ICON: Record<string, string> = {
  DL: "✅",
  OD: "🚚",
  EX: "⚠️",
  PU: "📦",
  IT: "🔄",
};

export default function TrackingTimeline({ shipmentId }: { shipmentId: string }) {
  const [events, setEvents] = useState<TrackingEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrackingEvents(shipmentId)
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [shipmentId]);

  if (loading) return <p className="text-sm text-gray-400">Loading events…</p>;
  if (events.length === 0)
    return <p className="text-sm text-gray-400">No tracking events yet. Try refreshing.</p>;

  return (
    <ol className="relative border-l border-gray-200 space-y-4 pl-5">
      {events.map((ev, i) => (
        <li key={ev.id} className="relative">
          <span className="absolute -left-[22px] flex items-center justify-center w-9 h-9 bg-white border-2 border-gray-200 rounded-full text-base">
            {EVENT_ICON[ev.event_code ?? ""] ?? "📍"}
          </span>
          <div className={i === 0 ? "font-semibold" : "text-gray-600"}>
            <span className="text-sm">{ev.description}</span>
            {ev.location && (
              <span className="ml-2 text-xs text-gray-400">— {ev.location}</span>
            )}
            <div className="text-xs text-gray-400 mt-0.5">
              {new Date(ev.timestamp).toLocaleString()}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
