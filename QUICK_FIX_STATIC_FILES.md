# Quick Fix: Static Files Not Loading on Hosting

## The Problem
✗ CSS changes work on localhost
✗ CSS changes don't appear on hosting
✗ "Sort By" dropdown has no styling

## The Cause
Missing `collectstatic` command during deployment

## The Solution (3 Steps)

### Step 1: Make build.sh Executable
```bash
chmod +x build.sh
git add build.sh
git commit -m "Add build script"
git push
```

### Step 2: Update Render Build Command
Go to Render Dashboard → Your Service → Settings

**Build Command:**
```bash
./build.sh
```

**Start Command:**
```bash
daphne -b 0.0.0.0 -p $PORT rdfs.asgi:application
```

### Step 3: Deploy
Click "Manual Deploy" or push changes to trigger auto-deploy

## Verify It Works
1. Wait for deployment to complete
2. Hard refresh browser: **Ctrl + Shift + R** (Windows) or **Cmd + Shift + R** (Mac)
3. Check if "Sort By" dropdown has styling
4. Open DevTools → Network tab → Check CSS files return 200 status

## What the build.sh Does
```bash
1. Installs Python packages
2. Collects static files (CSS, JS) → staticfiles/
3. Runs database migrations
```

## If It Still Doesn't Work
1. Check Render logs for errors
2. Clear browser cache completely
3. Verify STATIC_ROOT in settings.py: `STATIC_ROOT = BASE_DIR / 'staticfiles'`
4. Verify WhiteNoise is in MIDDLEWARE

## Future Deployments
✓ No action needed - build.sh runs automatically
✓ All CSS/JS changes will be collected automatically
✓ Just push your code and deploy

## Files Created
- ✓ `build.sh` - Automated build script
- ✓ `STATIC_FILES_FIX.md` - Detailed guide
- ✓ `QUICK_FIX_STATIC_FILES.md` - This file
