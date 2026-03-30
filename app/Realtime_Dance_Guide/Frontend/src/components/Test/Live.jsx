import { useEffect, useRef, useState, memo } from "react";
import { FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";

const COCO_TO_MP = [
  0,
  1,
  4,
  7,
  8,
  11,
  12,
  13,
  14,
  15,
  16,
  23,
  24,
  25,
  26,
  27,
  28,
];

const COCO_CONNECTIONS = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [5, 6],
  [5, 7], [7, 9],
  [6, 8], [8, 10],
  [11, 12],
  [5, 11], [6, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
];

const LIMBS = {
  left_arm: [5, 7, 9],
  right_arm: [6, 8, 10],
  left_leg: [11, 13, 15],
  right_leg: [12, 14, 16],
  torso: [5, 6, 11, 12],
};

const LIMB_FOR_JOINT = (() => {
  const out = Array(17).fill(null);
  for (const [name, idxs] of Object.entries(LIMBS)) {
    for (const i of idxs) out[i] = name;
  }
  for (let i = 0; i <= 4; i++) out[i] = out[i] || "torso";
  return out;
})();

function chooseVideoSrc(preview) {
  if (!preview) return null;
  if (preview.file && typeof preview.file === "string") return preview.file;
  if (preview.video) return preview.video;

  const candidates = [
    preview.video_url,
    preview.videoUrl,
    preview.url,
    preview.src,
    preview.preview_url,
    preview.video_preview_url,
    preview.preview,
    preview.download_url,
    preview.downloadUrl,
    preview.signed_url,
    preview.signedUrl,
    preview.storage_url,
    preview.storageUrl,
    preview.file_url,
    preview.fileUrl,
    preview.path,
    preview.filepath,
  ];
  for (const c of candidates) if (c) return c;

  if (preview.urls && typeof preview.urls === "object") {
    return preview.urls.video || preview.urls.signed || preview.urls.preview || preview.urls.download || null;
  }
  return null;
}

function parseRgbCss(s) {
  if (!s || typeof s !== "string") return [0, 255, 0];
  const m = s.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!m) return [0, 255, 0];
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function lerpRgb(a, b, t) {
  const tt = Math.max(0, Math.min(1, t));
  return [
    Math.round(a[0] + (b[0] - a[0]) * tt),
    Math.round(a[1] + (b[1] - a[1]) * tt),
    Math.round(a[2] + (b[2] - a[2]) * tt),
  ];
}

function rgbCss(a) {
  return `rgb(${a[0]},${a[1]},${a[2]})`;
}

function Panel({ title, preview, fps = 30, playing, modelAssetPath, restartKey, limbColors = null }) {
  console.log("[Live.Panel] Mounted:", { title, hasPreview: !!preview, playing, fps });
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const triedFallbackRef = useRef(false);

  const landmarkerRef = useRef(null);
  const rafRef = useRef(null);
  const detectIvRef = useRef(null);
  const objectUrlRef = useRef(null);
  const preprocessCanvasRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasLandmarks, setHasLandmarks] = useState(false);

  const colorStateRef = useRef(null);
  if (!colorStateRef.current) {
    colorStateRef.current = {};
    for (const k of Object.keys(LIMBS)) colorStateRef.current[k] = [0, 255, 0];
  }

  const limbTargetsRef = useRef(limbColors);
  useEffect(() => {
    limbTargetsRef.current = limbColors;
  }, [limbColors]);

  useEffect(() => {
    const videoEl = videoRef.current;
    if (!videoEl || !preview) return;

    if (!preprocessCanvasRef.current) {
      preprocessCanvasRef.current = document.createElement("canvas");
    }

    const hasLocalFile = preview.file && typeof preview.file !== "string";
    if (hasLocalFile) {
      try {
        const url = URL.createObjectURL(preview.file);
        objectUrlRef.current = url;
        videoEl.src = url;
      } catch {
        // ignore local blob url failures
      }
    }

    if (!videoEl.src) {
      const src = chooseVideoSrc(preview);
      if (!src) {
        setError("No video source");
        setLoading(false);
        return;
      }
      videoEl.src = src;
    }

    const handleVideoError = () => {
      try {
        const backendSrc = preview.video || null;
        if (!triedFallbackRef.current && backendSrc && videoEl.src !== backendSrc) {
          triedFallbackRef.current = true;
          videoEl.pause();
          videoEl.removeAttribute("src");
          videoEl.src = backendSrc;
          videoEl.crossOrigin = "anonymous";
          videoEl.load();
          videoEl.play().catch(() => {});
          return;
        }
      } catch {
        // ignore and show final error
      }

      setError("Video playback failed (unsupported format). Try converting to MP4/H264.");
      setLoading(false);
    };

    const handleCanPlay = () => {
      setLoading(false);
    };

    videoEl.crossOrigin = "anonymous";
    videoEl.muted = true;
    videoEl.playsInline = true;
    videoEl.preload = "auto";
    videoEl.controls = false;
    videoEl.disablePictureInPicture = true;
    videoEl.style.pointerEvents = "none";

    videoEl.addEventListener("error", handleVideoError);
    videoEl.addEventListener("canplay", handleCanPlay);

    return () => {
      try {
        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      } catch {
        // ignore cleanup errors
      }

      videoEl.removeEventListener("error", handleVideoError);
      videoEl.removeEventListener("canplay", handleCanPlay);
      objectUrlRef.current = null;
    };
  }, [preview]);

  useEffect(() => {
    let cancelled = false;
    let timeoutId = null;

    async function init() {
      setError(null);
      setLoading(true);
      setHasLandmarks(false);

      try {
        // Timeout for model initialization (30 seconds)
        const initPromise = (async () => {
          console.log("[Live.Panel] Starting PoseLandmarker init...");
          try {
            const vision = await FilesetResolver.forVisionTasks(
              "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
            );
            console.log("[Live.Panel] Vision tasks loaded");
            if (cancelled) return null;

            const landmarker = await PoseLandmarker.createFromOptions(vision, {
              baseOptions: {
                modelAssetPath: modelAssetPath || "/models/pose_landmarker_lite.task",
              },
              runningMode: "VIDEO",
              numPoses: 1,
              minPoseDetectionConfidence: 0.3,
              minPosePresenceConfidence: 0.2,
              minTrackingConfidence: 0.2,
            });
            console.log("[Live.Panel] PoseLandmarker initialized successfully");
            if (cancelled) {
              landmarker.close();
              return null;
            }
            return landmarker;
          } catch (e) {
            console.error("[Live.Panel] PoseLandmarker init error:", e);
            throw e;
          }
        })();

        // Set timeout that rejects after 30 seconds
        const timeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error("PoseLandmarker init timeout (30s)")), 30000)
        );

        const landmarker = await Promise.race([initPromise, timeoutPromise]);
        if (landmarker) {
          landmarkerRef.current = landmarker;
        }
        setLoading(false);
      } catch (e) {
        console.error("[Live.Panel] Init failed:", e);
        setError(`Pose detection unavailable: ${e?.message || "unknown error"}`);
        setLoading(false);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      try {
        if (landmarkerRef.current) landmarkerRef.current.close();
      } catch {
        // ignore close failures
      }
      landmarkerRef.current = null;
    };
  }, [modelAssetPath]);

  useEffect(() => {
    const videoEl = videoRef.current;
    const canvas = canvasRef.current;
    if (!videoEl || !canvas) return;

    const ctx = canvas.getContext("2d");

    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);

      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      ctx.clearRect(0, 0, w, h);

      if (videoEl.readyState >= 2 && videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
        try {
          ctx.drawImage(videoEl, 0, 0, w, h);
        } catch {
          // ignore frame draw errors
        }
      }

      const mp33 = canvas._lastLandmarks33;
      if (mp33 && mp33.length) {
        const cocoLm = COCO_TO_MP.map((mpIdx) => {
          const p = mp33[mpIdx];
          if (!p) return null;
          return { x: p.x, y: p.y, z: p.z ?? 0, visibility: p.visibility ?? 1 };
        });

        try {
          const targets = limbTargetsRef.current || {};
          const smooth = 0.45;
          for (const limb of Object.keys(LIMBS)) {
            const tgt = targets[limb] ? parseRgbCss(targets[limb].color) : [0, 255, 0];
            const cur = colorStateRef.current[limb] || [0, 255, 0];
            colorStateRef.current[limb] = lerpRgb(cur, tgt, smooth);
          }
        } catch {
          // ignore color update errors
        }

        for (const [a, b] of COCO_CONNECTIONS) {
          const A = cocoLm[a];
          const B = cocoLm[b];
          if (!A || !B) continue;
          const ax = A.x * ctx.canvas.width;
          const ay = A.y * ctx.canvas.height;
          const bx = B.x * ctx.canvas.width;
          const by = B.y * ctx.canvas.height;

          const limbA = LIMB_FOR_JOINT[a] || "torso";
          const limbB = LIMB_FOR_JOINT[b] || "torso";
          const colA = colorStateRef.current[limbA] || [0, 255, 0];
          const colB = colorStateRef.current[limbB] || [0, 255, 0];

          const grad = ctx.createLinearGradient(ax, ay, bx, by);
          grad.addColorStop(0, rgbCss(colA));
          grad.addColorStop(1, rgbCss(colB));

          ctx.save();
          ctx.strokeStyle = grad;
          ctx.lineWidth = 2;
          ctx.lineJoin = "round";
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.stroke();
          ctx.restore();
        }

        for (let i = 0; i < cocoLm.length; i++) {
          const p = cocoLm[i];
          if (!p) continue;
          const x = p.x * ctx.canvas.width;
          const y = p.y * ctx.canvas.height;
          const limb = LIMB_FOR_JOINT[i] || "torso";
          const col = colorStateRef.current[limb] || [0, 255, 0];

          ctx.save();
          ctx.fillStyle = rgbCss(col);
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, []);

  useEffect(() => {
    const videoEl = videoRef.current;

    if (detectIvRef.current) clearInterval(detectIvRef.current);
    detectIvRef.current = null;

    if (!videoEl) return;

    if (!playing) {
      try {
        videoEl.pause();
      } catch {
        // ignore pause errors
      }
      return;
    }

    videoEl.play().catch(() => {});

    const intervalMs = Math.max(1, Math.round(1000 / (fps || 30)));
    detectIvRef.current = setInterval(() => {
      const landmarker = landmarkerRef.current;
      if (!landmarker || videoEl.readyState < 2) return;

      try {
        const ts = performance.now();
        let sourceEl = videoEl;

        try {
          const pcan = preprocessCanvasRef.current;
          if (pcan && videoEl.videoWidth && videoEl.videoHeight) {
            const targetW = Math.max(videoEl.videoWidth, 640);
            const targetH = Math.max(videoEl.videoHeight, 480);
            if (pcan.width !== targetW || pcan.height !== targetH) {
              pcan.width = targetW;
              pcan.height = targetH;
            }
            const pctxt = pcan.getContext("2d");
            pctxt.drawImage(videoEl, 0, 0, targetW, targetH);
            sourceEl = pcan;
          }
        } catch {
          // use raw video on preprocessing failures
        }

        const res = landmarker.detectForVideo(sourceEl, ts);
        const lms = res?.landmarks?.[0] || null;

        if (lms && Array.isArray(lms) && lms.length > 0) {
          const validCount = lms.filter((p) => p && typeof p.x === "number" && typeof p.y === "number").length;
          if (validCount >= 11) {
            canvasRef.current._lastLandmarks33 = lms;
            if (!hasLandmarks) {
              setHasLandmarks(true);
              setLoading(false);
            }
          }
        }
      } catch {
        // ignore per-frame inference errors
      }
    }, intervalMs);

    return () => {
      if (detectIvRef.current) clearInterval(detectIvRef.current);
      detectIvRef.current = null;
    };
  }, [playing, fps, hasLandmarks]);

  useEffect(() => {
    const videoEl = videoRef.current;
    if (!videoEl) return;

    try {
      videoEl.currentTime = 0;
    } catch {
      // ignore reset errors
    }

    try {
      if (canvasRef.current) canvasRef.current._lastLandmarks33 = null;
    } catch {
      // ignore reset errors
    }

    setHasLandmarks(false);
    setLoading(true);
  }, [restartKey]);

  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ position: "relative", width: "100%", height: 240 }}>
        <video
          ref={videoRef}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            background: "#000",
            transition: "opacity 200ms",
            opacity: hasLandmarks ? 1 : 0.95,
            zIndex: 1,
            position: "relative",
          }}
        />

        <canvas
          ref={canvasRef}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 2,
          }}
        />

        {loading && (
          <div
            style={{
              position: "absolute",
              left: 8,
              top: 8,
              background: "rgba(0,0,0,0.6)",
              color: "#fff",
              padding: "4px 8px",
              borderRadius: 6,
              fontSize: 12,
            }}
          >
            Loading pose_landmarker_lite.task...
          </div>
        )}

        {error && (
          <div
            style={{
              position: "absolute",
              left: 8,
              bottom: 8,
              background: "rgba(200,0,0,0.85)",
              color: "#fff",
              padding: "6px 10px",
              borderRadius: 6,
              fontSize: 12,
            }}
          >
            {error}
          </div>
        )}

        {!loading && !error && (
          <div
            style={{
              position: "absolute",
              right: 8,
              top: 8,
              background: "rgba(0,200,0,0.7)",
              color: "#fff",
              padding: "4px 8px",
              borderRadius: 6,
              fontSize: 11,
            }}
          >
            ✓ Ready
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(function Live({
  refPreview,
  userPreview,
  fps = 30,
  playing = false,
  restartKey = 0,
  limbColors = null,
}) {
  console.log("[Live] Mounted/Updated:", { refPreview: !!refPreview, userPreview: !!userPreview, playing, fps });
  const modelAssetPath = "/models/pose_landmarker_lite.task";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Live PoseLandmarker at {fps} FPS — master controls govern playback
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <Panel
          title="Reference (Live Pose)"
          preview={refPreview}
          fps={fps}
          playing={playing}
          modelAssetPath={modelAssetPath}
          restartKey={restartKey}
          limbColors={null}
        />
        <Panel
          title="User (Live Pose)"
          preview={userPreview}
          fps={fps}
          playing={playing}
          modelAssetPath={modelAssetPath}
          restartKey={restartKey}
          limbColors={limbColors}
        />
      </div>
    </div>
  );
});
