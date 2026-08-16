"use client";

import { useEffect, useState } from "react";

import { getNetworkMode, subscribeToNetwork, type NetworkMode } from "@/lib/image-prefetch";

/**
 * Reactive reduced-data state. Starts optimistic on the server / first paint,
 * then syncs after mount and whenever the Network Information API reports a
 * change (e.g. the user toggles Data Saver or drops to 2G).
 */
export function useReducedData(): { reducedData: boolean; mode: NetworkMode } {
  const [mode, setMode] = useState<NetworkMode>({ reducedData: false, reason: "unknown" });

  useEffect(() => {
    setMode(getNetworkMode());
    return subscribeToNetwork(() => setMode(getNetworkMode()));
  }, []);

  return { reducedData: mode.reducedData, mode };
}
