import asyncio
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
import os


# -------------------------------------------------
# GLOBAL STATE
# -------------------------------------------------
pcs = set()
relay = MediaRelay()
source_tracks = {}
tracks_ready = asyncio.Event()

# -------------------------------------------------
# HTML VIEWER (ENHANCED ADMIN PANEL: USER-SET RESOLUTION + ANTI-BLUR)
# -------------------------------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Android Live Stream</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { 
      background:#111; 
      color:#fff; 
      font-family:Arial; 
      margin:0; 
      padding:10px; 
      display:flex; 
      flex-direction:column; 
      align-items:center; 
      min-height:100vh;
    }
    h2 { text-align:center; margin:10px 0; }
    #admin-panel {
      background:rgba(0,0,0,0.7); 
      padding:15px; 
      border-radius:12px; 
      margin-bottom:15px; 
      width:98%; 
      max-width:700px;
      display:flex; 
      justify-content:center; 
      gap:15px; 
      flex-wrap:wrap;
      box-shadow:0 4px 8px rgba(0,0,0,0.5);
    }
    #admin-panel label { 
      display:flex; 
      align-items:center; 
      gap:8px; 
      font-size:14px; 
      white-space:nowrap;
    }
    #admin-panel input, #admin-panel select { 
      padding:5px; 
      border-radius:4px; 
      border:1px solid #555; 
      background:#333; 
      color:#fff;
    }
    #res-controls { display:flex; gap:10px; align-items:center; }
    video { 
      max-width:98%; 
      width:98vw; 
      height:auto; 
      background:#000; 
      border-radius:12px; 
      object-fit:contain; /* ✅ Prevents blur/distortion */
      image-rendering: pixelated; /* ✅ Sharp pixels on upscale if needed */
      image-rendering: -moz-crisp-edges; /* Firefox sharp */
      image-rendering: crisp-edges; /* Safari/Chrome sharp */
    }
    .native { 
      width:auto !important; 
      height:auto !important; 
      max-width:none !important;
    }
    .custom { 
      width: var(--custom-width) !important; 
      height: var(--custom-height) !important;
    }
    @media (max-width: 600px) {
      #admin-panel { flex-direction:column; align-items:center; gap:10px; }
      #res-controls { flex-direction:column; text-align:center; }
      video { max-width:100%; }
      label { justify-content:center; }
    }
  </style>
</head>
<body>
<h2>📡 Android Live Stream (Admin Mode)</h2>
<div id="admin-panel">
  <label>
    <input type="radio" name="display-mode" value="fit" id="fit-screen" checked> Fit to Screen
  </label>
  <label>
    <input type="radio" name="display-mode" value="native" id="native-res"> Native Res
  </label>
  <label>
    <input type="radio" name="display-mode" value="custom" id="custom-res"> Custom Res
  </label>
  <div id="res-controls" style="display:none;">
    <label>Width: <input type="number" id="custom-width" min="1" max="3840" value="640"></label>
    <label>Height: <input type="number" id="custom-height" min="1" max="2160" value="480"></label>
    <button onclick="applyCustom()">Apply</button>
  </div>
  <label id="native-res-label" style="display:none;">
    Detected: <span id="res-display">--</span>px
  </label>
</div>
<video id="v" autoplay playsinline controls></video>
<script>
const pc = new RTCPeerConnection({
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
});
let nativeWidth = 640, nativeHeight = 480;
let currentMode = 'fit';

pc.ontrack = e => {
  const v = document.getElementById("v");
  if (!v.srcObject) {
    v.srcObject = e.streams[0];
  }
  const videoTrack = e.streams[0].getVideoTracks()[0];
  if (videoTrack) {
    videoTrack.addEventListener('loadedmetadata', () => {
      const settings = videoTrack.getSettings();
      nativeWidth = settings.width || nativeWidth;
      nativeHeight = settings.height || nativeHeight;
      document.getElementById('res-display').textContent = `${nativeWidth} × ${nativeHeight}`;
      document.getElementById('native-res-label').style.display = 'flex';
      updateVideoSize();
    });
  }
};

// ✅ TRANSCEIVERS FOR CLEAN NEGOTIATION
pc.addTransceiver('video', {direction: 'recvonly'});
pc.addTransceiver('audio', {direction: 'recvonly'});

function updateVideoSize() {
  const v = document.getElementById('v');
  v.classList.remove('native', 'custom');
  if (currentMode === 'fit') {
    v.style.width = '98vw';
    v.style.height = 'auto';
    v.style.setProperty('--custom-width', 'auto');
    v.style.setProperty('--custom-height', 'auto');
  } else if (currentMode === 'native') {
    v.style.width = nativeWidth + 'px';
    v.style.height = nativeHeight + 'px';
    v.classList.add('native');
  } else if (currentMode === 'custom') {
    // Apply will set it
  }
  // ✅ Force sharp rendering
  v.style.imageRendering = 'pixelated';
}

function applyCustom() {
  const w = document.getElementById('custom-width').value;
  const h = document.getElementById('custom-height').value;
  const v = document.getElementById('v');
  v.style.setProperty('--custom-width', w + 'px');
  v.style.setProperty('--custom-height', h + 'px');
  v.classList.add('custom');
  currentMode = 'custom';
}

document.querySelectorAll('input[name="display-mode"]').forEach(radio => {
  radio.addEventListener('change', (e) => {
    currentMode = e.target.value;
    if (currentMode === 'custom') {
      document.getElementById('res-controls').style.display = 'flex';
    } else {
      document.getElementById('res-controls').style.display = 'none';
    }
    updateVideoSize();
  });
});

(async () => {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const res = await fetch("/viewer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pc.localDescription)
  });
  const answer = await res.json();
  await pc.setRemoteDescription(answer);
})();
</script>
</body>
</html>
"""

# -------------------------------------------------
# ROUTES (UNCHANGED - FOCUS ON CLIENT-SIDE ENHANCEMENTS)
# -------------------------------------------------
async def index(request):
    return web.Response(text=HTML, content_type="text/html")

async def android_offer(request):
    data = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("track")
    def on_track(track):
        print("📱 Android track:", track.kind)
        source_tracks[track.kind] = relay.subscribe(track)
        tracks_ready.set()

    @pc.on("connectionstatechange")
    async def on_state():
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(
        RTCSessionDescription(data["sdp"], data["type"])
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def viewer_offer(request):
    data = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_state():
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(
        RTCSessionDescription(data["sdp"], data["type"])
    )
    await tracks_ready.wait()
    if "video" in source_tracks:
        pc.addTrack(source_tracks["video"])
    if "audio" in source_tracks:
        pc.addTrack(source_tracks["audio"])
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

# -------------------------------------------------
# CLEAN SHUTDOWN
# -------------------------------------------------
async def on_shutdown(app):
    await asyncio.gather(
        *[pc.close() for pc in pcs],
        return_exceptions=True
    )
    pcs.clear()

# -------------------------------------------------
# APP INIT
# -------------------------------------------------
app = web.Application()
app.router.add_get("/", index)
app.router.add_post("/offer", android_offer)
app.router.add_post("/viewer", viewer_offer)
app.on_shutdown.append(on_shutdown)
port = int(os.environ.get("PORT", 8000))
web.run_app(app, host="0.0.0.0", port=port)
