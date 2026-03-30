const API_BASE = "http://127.0.0.1:5000";

let activeToken = 0;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

async function runPolling(jobId, intervalMs, token) {
  while (token === activeToken) {
    try {
      const job = await fetchJson(`${API_BASE}/jobs/${jobId}`);
      if (token !== activeToken) return;

      self.postMessage({
        type: "status",
        jobId,
        status: job.status || "unknown",
        progress: job.progress ?? 0,
      });

      if (job.status === "failed") {
        self.postMessage({
          type: "failed",
          jobId,
          error: job.error || "Compare failed",
        });
        return;
      }

      if (job.status === "done") {
        const data = await fetchJson(`${API_BASE}/compare/${jobId}`);
        if (token !== activeToken) return;

        self.postMessage({
          type: "done",
          jobId,
          data,
        });
        return;
      }
    } catch (error) {
      if (token !== activeToken) return;
      self.postMessage({
        type: "poll-error",
        jobId,
        error: String(error?.message || error),
      });
    }

    await sleep(intervalMs);
  }
}

self.onmessage = (event) => {
  const msg = event?.data || {};

  if (msg.type === "start" && msg.jobId) {
    activeToken += 1;
    const token = activeToken;
    const intervalMs = Math.max(500, Number(msg.intervalMs) || 1200);
    runPolling(String(msg.jobId), intervalMs, token);
    return;
  }

  if (msg.type === "stop") {
    activeToken += 1;
  }
};
