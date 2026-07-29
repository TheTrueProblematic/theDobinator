import { useCallback, useRef, useState } from 'react';
import {
  UNLOCK_CLICKS,
  UNLOCK_WINDOW_MS,
  UNLOCK_HINT_AT,
  ADMIN_STORAGE_KEY,
  ADMIN_PASSWORD,
} from './constants.js';

function readStored() {
  try {
    return window.localStorage.getItem(ADMIN_STORAGE_KEY) === '1';
  } catch {
    return false; // private mode / storage disabled — just start locked
  }
}

function writeStored(on) {
  try {
    if (on) window.localStorage.setItem(ADMIN_STORAGE_KEY, '1');
    else window.localStorage.removeItem(ADMIN_STORAGE_KEY);
  } catch {
    /* non-fatal: admin mode simply won't persist across reloads */
  }
}

/**
 * Two gates guard the admin panel.
 *
 * 1. The handshake — UNLOCK_CLICKS taps on the brand mark inside
 *    UNLOCK_WINDOW_MS. Clicks older than the window are dropped, so a slow,
 *    accidental series never accumulates.
 * 2. The password — clearing the handshake opens a prompt; only a correct
 *    password actually unlocks.
 *
 * Once unlocked it's remembered per browser (no password on reload), and the
 * panel's own lock button clears it.
 */
export default function useAdminUnlock() {
  const [unlocked, setUnlocked] = useState(readStored);
  const [hinting, setHinting] = useState(false);
  const [asking, setAsking] = useState(false);      // password prompt open
  const [authError, setAuthError] = useState('');
  const [justUnlocked, setJustUnlocked] = useState(false);
  const clicksRef = useRef([]);
  const hintTimer = useRef(null);

  const registerClick = useCallback(() => {
    // Already in, or already being asked: a tap on the mark is a no-op.
    if (unlocked || asking) return;

    const now = Date.now();
    const recent = clicksRef.current.filter((t) => now - t < UNLOCK_WINDOW_MS);
    recent.push(now);
    clicksRef.current = recent;

    if (recent.length >= UNLOCK_CLICKS) {
      clicksRef.current = [];
      setHinting(false);
      setAuthError('');
      setAsking(true);   // handshake cleared — now prove it
      return;
    }

    // A small wiggle from click three onward — enough feedback that a curious
    // person keeps going, invisible to anyone who isn't already trying.
    if (recent.length >= UNLOCK_HINT_AT) {
      setHinting(true);
      if (hintTimer.current) clearTimeout(hintTimer.current);
      hintTimer.current = setTimeout(() => setHinting(false), 450);
    }
  }, [unlocked, asking]);

  // Returns true when the password was right (so the dialog can close itself).
  const submitPassword = useCallback((value) => {
    if (String(value) !== ADMIN_PASSWORD) {
      setAuthError('Incorrect password.');
      return false;
    }
    setAsking(false);
    setAuthError('');
    setUnlocked(true);
    writeStored(true);
    setJustUnlocked(true);
    return true;
  }, []);

  const cancelPassword = useCallback(() => {
    setAsking(false);
    setAuthError('');
    clicksRef.current = [];
  }, []);

  const lock = useCallback(() => {
    clicksRef.current = [];
    setUnlocked(false);
    setJustUnlocked(false);
    setAsking(false);
    setAuthError('');
    writeStored(false);
  }, []);

  const clearJustUnlocked = useCallback(() => setJustUnlocked(false), []);

  return {
    unlocked,
    hinting,
    asking,
    authError,
    justUnlocked,
    registerClick,
    submitPassword,
    cancelPassword,
    lock,
    clearJustUnlocked,
  };
}
