import { task } from "@trigger.dev/sdk/v3";
import { execa } from "execa";

// 1. Daily Email Batch
export const dailyBatch = task({
  id: "daily-batch",
  machine: "micro",
  run: async () => {
    await execa("python", ["main.py", "daily-batch", "--size", "3"]);
  },
});

// 2. Check Lead Responses
export const checkResponses = task({
  id: "check-responses",
  machine: "micro",
  run: async () => {
    await execa("python", ["main.py", "check"]);
  },
});

// 3. Weekly Metrics Report
export const metricsReport = task({
  id: "metrics-report",
  machine: "micro",
  run: async () => {
    await execa("python", ["main.py", "metrics"]);
  },
});

// 4. Welcome Campaign (Manual)
export const welcomeCampaign = task({
  id: "welcome-campaign",
  machine: "small-1x",
  run: async () => {
    await execa("python", ["main.py", "welcome"]);
  },
});

// 5. Follow-Up Campaign (Manual)
export const followupCampaign = task({
  id: "followup-campaign",
  machine: "small-1x",
  run: async () => {
    await execa("python", ["main.py", "followup"]);
  },
});

// 6. Full Campaign Run (Manual)
export const fullRun = task({
  id: "full-run",
  machine: "small-1x",
  run: async () => {
    await execa("python", ["main.py", "full_run"]);
  },
});
