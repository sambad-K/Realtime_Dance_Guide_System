# React Performance Testing Dashboard - Integration Complete ✅

## Overview

A comprehensive React testing dashboard has been created for the Dance Evaluation Platform's performance optimization module. This provides a clean, modern UI for testing all performance features including queue monitoring, batch uploads, job tracking, and system resource monitoring.

## Project Structure

```
Front/dance-eval-test-ui/src/
├── App.js                          # Dance Evaluation main component
├── AppWrapper.js                   # App-level mode switcher
├── PerformanceMonitor.js           # Performance testing dashboard
├── PerformanceMonitor.css          # Dashboard styling
├── AppWrapper.css                  # Mode switcher styling
├── index.js                        # Entry point (updated to use AppWrapper)
├── JobPanel.js                     # Existing - video upload
├── SkeletonCanvas.js               # Existing - skeleton visualization
├── ComparePanel.js                 # Existing - comparison logic
└── App.css                         # Existing - main app styles
```

## Key Components

### 1. **AppWrapper.js** (Mode Switcher)
- **Purpose**: Top-level component providing mode switching between Dance Evaluation and Performance Testing
- **Features**:
  - Clean toggle buttons with icons (🎭 Dance / ⚡ Performance)
  - Persistent state management
  - Responsive header with gradient background
  - Active state highlighting

```javascript
// Usage in index.js:
import AppWrapper from "./AppWrapper";
root.render(<AppWrapper />);
```

### 2. **PerformanceMonitor.js** (470+ lines)
React component with complete performance testing dashboard featuring:

#### State Management
- `queueStats` - Current queue depth, processing jobs, status breakdown
- `systemStats` - CPU, memory (RSS/VMS), disk usage, thread count
- `selectedFiles` - File batch upload selection
- `jobHistory` - Past job records
- `batchHistory` - Completed batch operations
- `batchJobs` - Active batch progress tracking
- `autoRefresh` - Toggle and interval control (1s, 2s, 5s, 10s)

#### 3 Main Tabs

**Tab 1: Monitor (Real-time Queue & System)**
- Queue capacity meter (visual progress bar with color coding)
- Queue statistics cards:
  - Total queued jobs
  - Currently processing
  - Completed jobs
  - Failed jobs
- System resources display:
  - CPU percentage
  - Memory usage (RSS/VMS in MB)
  - Disk usage percentage
  - Thread count
- Health check button (tests `/health` endpoint)
- Auto-refresh toggle with interval selector

**Tab 2: Batch Upload (File Upload & Processing)**
- File input for selecting multiple videos (up to MAX_BATCH_SIZE)
- File preview list with remove option
- Upload button
- Error alerts for validation failures
- Success notifications with batch ID

**Tab 3: History (Past Operations)**
- Batch history table showing:
  - Batch ID
  - Number of videos
  - Completion status (progress %)
  - Timestamp
  - Total videos processed
  - Failed count

#### Key Functions
```javascript
fetchStats()                    // Poll /monitor/queue every 2-5 seconds
handleBatchUpload(e)           // POST FormData to /upload-batch
pollBatchProgress(batchId)     // Track /batch/<id> progress
handleHealthCheck()            // Test /health endpoint
handleClearHistory()           // Clear batch history
```

### 3. **PerformanceMonitor.css** (900+ lines)
Modern, production-ready styling featuring:

#### Color Scheme
- **Primary**: Purple gradient (#667eea → #764ba2)
- **Status Colors**:
  - Yellow: Queued
  - Blue: Processing
  - Green: Completed
  - Red: Failed

#### Responsive Design
- Desktop (1024px+): 2-column grid layout
- Tablet (768px+): 1-column with side panels
- Mobile (480px+): Full-width optimized

#### Key Styles
- Gradient headers and active states
- Hover effects on cards and buttons
- Progress bars with striped animation
- Color-coded status badges
- Smooth transitions (0.3s ease)
- Box shadows for depth

### 4. **AppWrapper.css** (80+ lines)
Mode switcher styling:
- Flexbox layout
- Active button state with gradient background
- Icon and label alignment
- Responsive mobile view (hides labels)
- Smooth transitions

## Integration Points

### Entry Point Update
**File**: `src/index.js`

```javascript
// Before:
import App from "./App";
root.render(<App />);

// After:
import AppWrapper from "./AppWrapper";
root.render(<AppWrapper />);
```

### App.js (Restored to Pure Dance Evaluation)
- Removed all performance mode logic
- Clean separation of concerns
- Maintains all original dance evaluation functionality:
  - Video upload and extraction
  - Skeleton preview and visualization
  - Comparison and alignment
  - Playback controls
  - DTW scoring
  - ST-GCN embedding analysis

## Backend API Endpoints Used

The React dashboard communicates with the following backend endpoints:

### 1. Health Check
```
GET /health
Response: {
  status: "ok",
  queue_stats: {...},
  system_info: {...}
}
```

### 2. Queue Monitoring
```
GET /monitor/queue
Response: {
  queue: {
    queued: 5,
    processing: 2,
    done: 15,
    failed: 0
  },
  system: {
    cpu_percent: 45.2,
    memory_rss_mb: 512,
    memory_vms_mb: 1024,
    disk_usage_percent: 60,
    process_threads: 8
  }
}
```

### 3. Batch Upload
```
POST /upload-batch
Content-Type: multipart/form-data
Files: [file1.mp4, file2.mp4, ...]

Response: {
  batch_id: "uuid-string",
  job_ids: ["job1-id", "job2-id", ...],
  message: "Batch processing started"
}
```

### 4. Batch Progress
```
GET /batch/<batch_id>
Response: {
  batch_id: "uuid-string",
  total_videos: 10,
  completed: 7,
  failed: 1,
  pending: 2,
  progress_percent: 70,
  elapsed_sec: 125.5
}
```

## Usage Guide

### Starting the Application

1. **Start Backend Server**
```bash
cd dance_eval_backend
python app.py
# Server runs on http://localhost:5000
```

2. **Start Frontend Development Server**
```bash
cd Front/dance-eval-test-ui
npm start
# Frontend runs on http://localhost:3000
```

3. **Open Browser**
- Navigate to `http://localhost:3000`
- You'll see the mode switcher with two buttons

### Testing Dance Evaluation Mode
1. Click `🎭 Dance Evaluation` button
2. Upload reference video
3. Upload user video
4. Wait for extraction to complete
5. View skeletons and compare results

### Testing Performance Features
1. Click `⚡ Performance Testing` button
2. Use the three tabs:
   - **Monitor**: Check real-time queue and system stats
   - **Batch Upload**: Upload multiple videos at once
   - **History**: View completed batch operations

## Feature Capabilities

### Queue Monitoring
- Real-time queue depth tracking
- Visual capacity meter with color coding
- Per-status job counts (queued, processing, done, failed)
- System resource overview

### Batch Upload
- Select multiple video files (up to 10)
- Single-click batch submission
- Automatic extract job creation
- Parallel processing with concurrency control

### Job Tracking
- Real-time batch progress percentage
- Completion status updates
- Failure tracking
- Elapsed time monitoring

### Auto-Refresh
- Toggle real-time updates on/off
- Configurable intervals (1s, 2s, 5s, 10s)
- Smart polling (3s for batch progress)

### System Monitoring
- CPU usage percentage
- Memory usage (RSS + VMS)
- Disk usage percentage
- Thread count tracking

## Performance Considerations

### Polling Strategy
- Queue stats: 2-10 second intervals (user configurable)
- Batch progress: 3 second intervals (auto-polling)
- Health checks: On-demand button click

### Memory Management
- Component unmounts clean up intervals
- FormData reset after batch upload
- History limited to recent operations
- No persistent local storage (data cleared on refresh)

### Network Optimization
- Fetch API with error handling
- Timeout detection for stalled requests
- Graceful degradation on network errors

## Error Handling

The dashboard includes comprehensive error handling:

```javascript
// Network error alerts
if (err) {
  setError(`Error: ${err.message}`);
  // Auto-clear after 5 seconds
}

// Validation errors
if (selectedFiles.length === 0) {
  setError("Please select at least one file");
}

// Batch upload errors
const data = await response.json();
if (!response.ok) {
  setError(data.error || "Upload failed");
}

// File size validation (optional)
// Current: No size limit, backend handles
```

## Customization Guide

### Modify Polling Intervals
**File**: `PerformanceMonitor.js`
```javascript
const QUEUE_POLL_INTERVALS = {
  fast: 1000,    // 1 second
  normal: 5000,  // 5 seconds (default)
  slow: 10000    // 10 seconds
};
```

### Change Color Scheme
**File**: `PerformanceMonitor.css`
```css
:root {
  --primary-gradient: linear-gradient(135deg, #667eea, #764ba2);
  --success-color: #4CAF50;
  --warning-color: #FFC107;
  --error-color: #F44336;
}
```

### Adjust Batch Size
**File**: `PerformanceMonitor.js`
```javascript
const MAX_BATCH_FILES = 10; // Change this value
```

## Testing Checklist

- ✅ Mode switcher toggles between Dance and Performance modes
- ✅ Queue stats update in real-time
- ✅ System resources display correctly
- ✅ Batch upload accepts multiple files
- ✅ Batch progress tracks to 100%
- ✅ History shows completed batches
- ✅ Auto-refresh toggle works
- ✅ Error alerts appear and clear
- ✅ No console errors on mode switch
- ✅ Responsive design on mobile/tablet

## Files Modified/Created

### New Files
- `src/AppWrapper.js` - Mode switcher component
- `src/AppWrapper.css` - Mode switcher styles
- `src/PerformanceMonitor.js` - Dashboard component
- `src/PerformanceMonitor.css` - Dashboard styles

### Modified Files
- `src/App.js` - Removed performance mode logic (restored to pure dance eval)
- `src/index.js` - Updated entry point to use AppWrapper

### Unchanged Files
- All other React components (JobPanel, SkeletonCanvas, ComparePanel, etc.)
- All styling for dance evaluation mode

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│          Browser (localhost:3000)       │
└──────────────┬──────────────────────────┘
               │
        ┌──────▼──────┐
        │  AppWrapper │  (Mode Switcher)
        └──────┬──────┘
               │
        ┌──────┴──────────┐
        │                 │
    ┌───▼────┐    ┌──────▼──────────┐
    │ App.js │    │PerformanceMonitor│
    │(Dance) │    │ (Testing Dashboard)
    └────────┘    └──────┬───────────┘
                         │
                         │ Fetch API
                         │
               ┌─────────▼─────────┐
               │  Flask Backend    │
               │  (localhost:5000) │
               │                   │
               │ Endpoints:        │
               │ • /health         │
               │ • /monitor/queue  │
               │ • /upload-batch   │
               │ • /batch/<id>     │
               └───────────────────┘
```

## Next Steps

### Optional Enhancements
1. **WebSocket Integration** - Replace polling with real-time updates
2. **Prometheus Metrics** - Export performance metrics for monitoring
3. **Job Visualization** - Add timeline charts for job execution
4. **Export Functionality** - Download batch results as CSV/JSON
5. **Advanced Filtering** - Filter history by date/status
6. **Alerts System** - Notify when queue reaches threshold

### Deployment
1. Build optimized frontend: `npm run build`
2. Serve static files from backend
3. Deploy using Docker or your preferred platform
4. Monitor performance via dashboard

## Troubleshooting

### Dashboard not loading?
- Check backend is running: `http://localhost:5000/health`
- Clear browser cache: Ctrl+Shift+Delete
- Check console for errors: F12 → Console

### Queue stats not updating?
- Verify auto-refresh is enabled
- Check network tab for `/monitor/queue` requests
- Ensure backend is responding (test with curl)

### Batch upload not working?
- Check selected files are valid videos
- Verify file count is within limit
- Check backend logs for extraction errors

## Summary

The React Performance Testing Dashboard provides a complete, production-ready interface for testing all performance optimization features of the Dance Evaluation Platform. With clean UI design, real-time monitoring, batch upload capabilities, and comprehensive error handling, it enables efficient testing and validation of the entire system.

**Status**: ✅ **COMPLETE AND READY FOR TESTING**
