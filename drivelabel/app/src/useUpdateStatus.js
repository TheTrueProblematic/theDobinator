import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchUpdateStatus } from './api.js';
import { UPDATE_POLL_MS } from './constants.js';

const IDLE = { available: false, reboot: false, processing: false };

/**
 * Polls the API for theDobinator's pending-update state so this site can show
 * the same update badge its sibling does.
 *
 * A failed poll is deliberately silent and leaves the badge hidden — if the API
 * or theDobinator is unreachable, the honest thing is to show nothing rather
 * than an update button that can't work.
 */
export default function useUpdateStatus() {
  const [status, setStatus] = useState(IDLE);
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetchUpdateStatus();
      setStatus({
        available: !!(res && res.available),
        reboot: !!(res && res.reboot),
        processing: !!(res && res.processing),
      });
    } catch {
      setStatus(IDLE);
    }
  }, []);

  useEffect(() => {
    refresh();
    timer.current = setInterval(refresh, UPDATE_POLL_MS);
    return () => clearInterval(timer.current);
  }, [refresh]);

  return { status, refresh };
}
