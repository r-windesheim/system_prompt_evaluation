# Clear Cached Results

Your browser has old analysis results that don't include leave-one-out responses.

## Option 1: Clear via Browser Console
1. Open browser console (F12)
2. Go to "Application" tab → "Session Storage"
3. Clear `analysisResult` and `sections`
4. Refresh page

## Option 2: Run this in console
```javascript
sessionStorage.clear();
window.location.reload();
```

## Option 3: Run a fresh analysis
Just go back to /analyze and run a new analysis - it will overwrite the old data.

The backend DOES generate leave-one-out responses, they're just not in your cached data.
