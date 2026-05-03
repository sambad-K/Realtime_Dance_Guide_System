const API_BASE = "http://127.0.0.1:5000";

export async function uploadVideo(file, kind) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("kind", kind);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: fd,
  });

  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json(); // { video_id }
}

export async function createExtractJob(videoId) {
  const res = await fetch(`${API_BASE}/jobs/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: videoId }),
  });

  if (!res.ok) throw new Error(`Create job failed: ${res.status}`);
  return res.json(); // { job_id }
}

export async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Get job failed: ${res.status}`);
  return res.json();
}

export async function getPreview(jobId) {
  const res = await fetch(`${API_BASE}/preview/${jobId}`);
  if (!res.ok) throw new Error(`Preview not ready: ${res.status}`);
  return res.json(); // {frames, kpts, conf}
}
export async function createCompareJob(refJobId, userJobId, maxShiftFrames = 90) {
  const ac = new AbortController();
  const id = setTimeout(() => ac.abort(), 12000);
  let res;
  console.log("[api] createCompareJob called with:", { refJobId, userJobId, maxShiftFrames });
  try {
    res = await fetch(`${API_BASE}/jobs/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ref_job_id: refJobId,
        user_job_id: userJobId,
        max_shift_frames: maxShiftFrames,
      }),
      signal: ac.signal,
    });
  } catch (err) {
    clearTimeout(id);
    if (err?.name === "AbortError") {
      throw new Error("Create compare timed out (12s)");
    }
    console.error("[api] createCompareJob fetch error:", err);
    throw err;
  }
  clearTimeout(id);
  
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("[api] createCompareJob bad response:", { status: res.status, text });
    throw new Error(`Create compare failed: ${res.status} ${text}`);
  }
  
  const json = await res.json();
  console.log("[api] createCompareJob response:", json);
  return json; // { job_id }
}

export async function getCompare(jobId) {
  const res = await fetch(`${API_BASE}/compare/${jobId}`);
  if (!res.ok) throw new Error(`Compare not ready: ${res.status}`);
  return res.json();
}

export async function getVerdict(jobId, timeoutMs = 7000, mode = "quick") {
  const url = `${API_BASE}/jobs/${jobId}/verdict${mode ? `?mode=${encodeURIComponent(mode)}` : ""}`;
  const ac = new AbortController();
  const id = setTimeout(() => ac.abort(), Number(timeoutMs) || 7000);
  try {
    const res = await fetch(url, { signal: ac.signal });
    if (!res.ok) throw new Error(`Verdict not ready: ${res.status}`);
    return res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Verdict request timed out');
    throw err;
  } finally {
    clearTimeout(id);
  }
}

export async function getArtifact(jobId, name) {
  const url = `${API_BASE}/artifacts/${jobId}/${encodeURIComponent(name)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Artifact not found: ${res.status}`);
  return res.json();
}
