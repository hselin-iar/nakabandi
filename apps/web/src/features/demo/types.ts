/**
 * types.ts — Types for Demo Console & World-Sim Control API.
 * DOC 3 M1 · LC-8 · DOC 2 §2.7 · DOC 4 Step C8
 */

export type SimulatorState = "idle" | "running" | "paused" | "stopped" | string;

export interface SimulatorStatus {
  state: SimulatorState;
  sim_time: number;
  speed: number;
  seed: number;
  scenario: string;
  counts: {
    complaints: number;
    cashouts: number;
    ticks: number;
  };
  last_error: string | null;
}

export interface StartRequest {
  scenario: "free" | "guided_demo";
  speed?: number;
}

export interface SpeedRequest {
  factor: number;
}

export interface ResetRequest {
  seed?: number;
}

export interface InjectClusterRequest {
  district_id: string;
  size: number;
  fast_weight: number;
  locality: "district" | "multi_district" | "state" | "multi_state";
}

export interface ProxiedRequestLogEntry {
  id: string;
  timestamp: string;
  method: "GET" | "POST";
  path: string;
  payload?: unknown;
  status: number;
  response?: unknown;
  error?: string;
}

export interface DemoUser {
  username: string;
  role: string;
  display_name: string;
  password?: string;
}
