import { DEMO_STATE_VERSION, buildDemoState, type DemoState } from "./seed";

const STORAGE_KEY = "crm.demoState";

let state: DemoState | null = null;

function load(): DemoState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw !== null) {
      const parsed = JSON.parse(raw) as DemoState;
      if (parsed.version === DEMO_STATE_VERSION) {
        return parsed;
      }
    }
  } catch {
    // Broken or blocked storage: fall back to a fresh base.
  }
  return buildDemoState();
}

/** The demo database. Edits live in this browser only. */
export function demoState(): DemoState {
  if (state === null) {
    state = load();
  }
  return state;
}

export function saveDemoState(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full or unavailable: the session keeps working in memory.
  }
}

export function resetDemoState(): void {
  state = buildDemoState();
  saveDemoState();
}
