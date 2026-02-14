# DataMIQ Quick Start Guide

## ✅ All Issues Fixed!

1. ✅ Connection model created
2. ✅ Database Base class added
3. ✅ Virtual environment recreated with correct path
4. ✅ All dependencies installed (including google-cloud-storage)
5. ✅ Frontend stopped from wrong directory (Downloads)

## ⚠️ IMPORTANT: Frontend Must Run from THIS Directory

The frontend was running from the Downloads directory (old code). It has been stopped.
You MUST start it from this directory to see your latest changes.

## Start the Application

### Terminal 1 - Backend Server

```bash
./START_BACKEND_HERE.sh
```

Wait for:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 - Frontend Server

Open a NEW terminal window and run:

```bash
cd "/Users/manasakallakuri/Manasa/Data accelerator/DataMIQ Backup"
./START_FRONTEND_HERE.sh
```

Wait for:
```
VITE ready in XXX ms
Local: http://localhost:3000/
```

**IMPORTANT:** After starting, clear your browser cache:
- Hard refresh: `Cmd + Shift + R` (Mac)
- Or clear cache: `Cmd + Shift + Delete` → Select "Cached images and files"

### Access the Application

Open browser: **http://localhost:3000**

Login:
- **Username:** `admin`
- **Password:** `admin123`

## Verify Backend is Running

```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status":"healthy","service":"datamiq-api","version":"1.0.0"}
```

## Troubleshooting

### If backend fails to start

Check the error message in the terminal. Common issues:
- Database not running: `brew services start postgresql`
- Port 8000 already in use: `lsof -ti:8000 | xargs kill -9`

### If frontend fails to start

- Port 3000 already in use: `lsof -ti:3000 | xargs kill -9`
- Missing dependencies: `cd frontend && npm install`

### If login doesn't work

1. Verify backend is responding:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check backend logs in Terminal 1

3. Check browser console for errors (F12)

## Stop the Application

Press `Ctrl+C` in each terminal window, or run:

```bash
pkill -9 -f "uvicorn main:app"
pkill -9 -f "vite"
```
