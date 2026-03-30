# React Performance Testing Dashboard - Quick Start Guide

## 🚀 Start in 5 Minutes

### Step 1: Start Backend Server
```bash
cd "d:\Major project\A. MAIN\Learn mod\dance_eval_backend"
python app.py
```
Expected output:
```
 * Running on http://127.0.0.1:5000
```

### Step 2: Start Frontend Development Server
```bash
cd "d:\Major project\A. MAIN\Learn mod\Front\dance-eval-test-ui"
npm start
```
Expected output:
```
Compiled successfully!
Local:   http://localhost:3000
```

### Step 3: Open in Browser
- Navigate to `http://localhost:3000`
- You should see the app with two mode buttons at the top

---

## 📋 Testing Scenarios

### Scenario 1: Test Dance Evaluation Mode
1. Click **🎭 Dance Evaluation** button
2. Click "1) Upload Reference Video"
3. Select a video file (MP4 recommended, <100MB)
4. Wait for "Extraction complete" message
5. Click "2) Upload User Video"
6. Select another video file
7. Wait for extraction complete
8. Click "Compare" button in Compare panel
9. View skeleton overlays and comparison scores

### Scenario 2: Test Performance Monitoring
1. Click **⚡ Performance Testing** button
2. You should see the dashboard with 3 tabs:
   - Monitor (with queue stats and system info)
   - Batch Upload (with file upload)
   - History (with past batches)

### Scenario 3: Test Queue Monitoring
1. In Performance Testing mode, click "Monitor" tab
2. Click "Check Health" button - should show status "ok"
3. Look at queue statistics:
   - Queued: number of waiting jobs
   - Processing: currently running jobs
   - Done: completed jobs
4. Toggle "Auto Refresh" ON
5. Select refresh interval (2-5 seconds recommended)
6. Watch queue stats update in real-time

### Scenario 4: Test Batch Upload
1. In Performance Testing mode, click "Batch Upload" tab
2. Click file input area or drag-and-drop videos
3. Select 2-5 video files
4. Files should appear in the list below input
5. Click "Upload Batch" button
6. You should see success message with batch ID
7. Click "History" tab to see the batch being processed

### Scenario 5: Test Batch Progress Tracking
1. After uploading batch (Scenario 4)
2. Go to "History" tab
3. You should see your batch with progress percentage
4. Progress should update every 3 seconds
5. Watch progress go from 0% to 100%
6. When complete, status should show "✓ Completed"

### Scenario 6: Test System Resource Monitoring
1. In "Monitor" tab, scroll down to "System Resources"
2. You should see:
   - CPU Usage: percentage (0-100%)
   - Memory (RSS): in MB
   - Memory (VMS): in MB
   - Disk Usage: percentage
   - Thread Count: number of threads
3. These update with the selected refresh interval

---

## 🔍 What to Look For

### Success Indicators ✅

- **Mode Switcher Works**: Clicking buttons smoothly switches between modes
- **No Console Errors**: F12 → Console shows no red errors
- **Queue Stats Update**: Numbers change when auto-refresh is on
- **Batch Upload Works**: Files selected and uploaded successfully
- **Progress Tracking**: Batch progress updates in real-time
- **Responsive Design**: Works on desktop, tablet, mobile

### Common Issues & Fixes ❌

| Issue | Cause | Fix |
|-------|-------|-----|
| "Cannot connect to server" | Backend not running | Run `python app.py` first |
| "Module not found" errors | Dependencies missing | Run `npm install` in frontend dir |
| Queue stats don't update | Auto-refresh off | Toggle "Auto Refresh" ON |
| Batch upload button disabled | No files selected | Select at least one file |
| Page stuck loading | API timeout | Refresh page, check backend |
| Videos not extracting | Video format issue | Try different MP4 file |

---

## 📊 Expected Performance

### Queue Monitoring Performance
- Queue stats should update every 2-5 seconds
- No lag or stuttering in UI
- CPU usage <30% while monitoring

### Batch Upload Performance
- File upload should start within 1 second of clicking button
- Each 10MB video takes ~30-60 seconds to extract (depends on hardware)
- 5 videos in parallel: ~2-3 minutes total

### System Resources (Typical)
- CPU: 20-50% during extraction
- Memory: 500-1000 MB for backend
- Disk: Varies based on database size

---

## 🔧 Configuration Tips

### Faster Testing
Edit `PerformanceMonitor.js` line ~80:
```javascript
// Change from:
const refreshInterval = Math.max(1000, intervals[autoRefresh] || 5000);

// To faster interval:
const refreshInterval = 1000; // 1 second
```

### Larger Batch Uploads
Edit `PerformanceMonitor.js` line ~30:
```javascript
// Change from:
const MAX_BATCH_FILES = 10;

// To allow more files:
const MAX_BATCH_FILES = 50;
```

### Custom Backend URL
Edit `PerformanceMonitor.js` line ~20:
```javascript
// Change from:
const API_BASE = "http://localhost:5000";

// To custom URL:
const API_BASE = "http://your-server.com:5000";
```

---

## 📱 Testing on Different Devices

### Desktop (Recommended for Testing)
- Full feature access
- Best performance
- Easiest debugging (F12 DevTools)

### Tablet (iPad, Android Tablet)
- Responsive layout adapts
- Touch-friendly buttons
- Some CPU constraints

### Mobile (iPhone, Android Phone)
- Single-column layout
- Icon-only mode switcher
- May need larger video files

---

## 🐛 Debugging Tips

### View Network Requests
1. Press F12 to open DevTools
2. Click "Network" tab
3. Perform actions (upload, refresh)
4. Check requests to `/monitor/queue`, `/upload-batch`, `/batch/<id>`
5. Click each request to see response data

### View Console Logs
1. Press F12 to open DevTools
2. Click "Console" tab
3. Look for errors (red), warnings (yellow), logs (blue)
4. Check backend console simultaneously

### Monitor Performance
1. Press F12 to open DevTools
2. Click "Performance" tab
3. Click record button
4. Perform action (upload, refresh)
5. Click stop
6. Analyze timeline for bottlenecks

### Check Backend Logs
Terminal window running `python app.py` shows:
```
127.0.0.1 - - [timestamp] "GET /monitor/queue HTTP/1.1" 200
127.0.0.1 - - [timestamp] "POST /upload-batch HTTP/1.1" 201
```

---

## ✨ Advanced Testing

### Load Testing
1. Upload 10+ video batches simultaneously
2. Monitor queue depth and CPU
3. Check for queue depth exceeded (HTTP 429)
4. Verify timeout enforcement after 1 hour

### Memory Profiling
1. Enable ST-GCN memory profiling in backend
2. Compare batches with different skeleton counts
3. Monitor memory usage in System Resources
4. Check backend logs for memory warnings

### Stress Testing
1. Continuously upload batches
2. Watch queue grow and shrink
3. Monitor system resources
4. Test timeout recovery

---

## 📝 Checklist for Complete Testing

### Frontend UI
- [ ] Mode switcher buttons visible and clickable
- [ ] Layout responsive on desktop/tablet/mobile
- [ ] No console errors when switching modes
- [ ] Colors and styling match design

### Queue Monitoring
- [ ] Queue stats display correctly
- [ ] Health check button works
- [ ] Auto-refresh toggle works
- [ ] Stats update at selected interval
- [ ] System resources show current values

### Batch Upload
- [ ] File input accepts multiple files
- [ ] File list shows selected files
- [ ] Remove button works for each file
- [ ] Upload button submits files
- [ ] Success message shows batch ID

### Batch History
- [ ] Completed batches appear in history
- [ ] Progress percentage updates
- [ ] Status shows "Completed" when done
- [ ] Timestamps display correctly

### Integration
- [ ] Switching between modes preserves state
- [ ] No data loss on mode switch
- [ ] Both modes work independently
- [ ] Responsive design works on all devices

---

## 🎓 Learning Resources

### Understanding the Dashboard

**Monitor Tab**: Shows what's currently happening
- Queue depth = how many jobs waiting
- Processing = jobs currently running
- Done/Failed = historical count

**Batch Upload Tab**: Send multiple videos at once
- Select files → Upload → Batch created
- System creates extract jobs automatically
- Up to 10 files per batch (configurable)

**History Tab**: Track completed operations
- Shows all batches you've uploaded
- Progress percentage (0-100%)
- Status: Completed, Failed, or In Progress

### Queue Concepts

**Queued**: Job waiting for a worker to process
**Processing**: Worker actively extracting/comparing
**Done**: Successfully completed
**Failed**: Error occurred during processing
**Timed Out**: Job took too long (>1 hour for extract)

---

## 🆘 Getting Help

### Check Backend Logs
```bash
# Watch backend output in real-time
# Look for error messages and timestamps
```

### Test Backend Directly
```bash
# Test health endpoint
curl http://localhost:5000/health

# Test queue monitoring
curl http://localhost:5000/monitor/queue

# Should return JSON responses
```

### Test Frontend Network
```javascript
// In browser console (F12):
fetch('http://localhost:5000/health')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error(e))
```

---

## 📞 Contact & Documentation

- **Backend Docs**: See `dance_eval_backend/PERFORMANCE.md`
- **API Reference**: See `dance_eval_backend/API_REFERENCE.md`
- **Architecture**: See `dance_eval_backend/ARCHITECTURE.md`
- **Full Integration Guide**: See `REACT_INTEGRATION_COMPLETE.md`

---

**Status**: ✅ Ready for Testing
**Last Updated**: Now
**Version**: 1.0 (Complete)
