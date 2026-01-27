# Static Files Not Loading on Hosting - Fix Guide

## Problem
CSS changes for the "Sort By" dropdown on `/vehicles/registered/` and `/vehicles/registered-drivers/` pages work on localhost but don't appear on the hosting platform.

## Root Cause
The updated CSS files in the `static/` directory are not being copied to the `staticfiles/` directory that Django serves in production. This happens because:

1. **Django serves static files differently in production:**
   - Development: Django serves files directly from `static/` folders
   - Production: Django serves files from `staticfiles/` (collected static files)

2. **`collectstatic` command not running:**
   - The `python manage.py collectstatic` command copies all static files from `static/` to `staticfiles/`
   - This command must run during deployment to update production static files

## Solution

### Option 1: Using Render.com (Recommended)

If you're using Render.com, follow these steps:

#### Step 1: Add Build Script
A `build.sh` file has been created in your project root with the following content:

```bash
#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate
```

#### Step 2: Update Render Configuration

In your Render.com dashboard:

1. Go to your web service
2. Click on "Settings"
3. Update the **Build Command** to:
   ```bash
   ./build.sh
   ```
   OR
   ```bash
   bash build.sh
   ```

4. Make sure the **Start Command** is:
   ```bash
   daphne -b 0.0.0.0 -p $PORT rdfs.asgi:application
   ```

5. Click "Save Changes"

#### Step 3: Make build.sh Executable (if needed)

If you get permission errors, run this locally before pushing:
```bash
chmod +x build.sh
git add build.sh
git commit -m "Make build.sh executable"
git push
```

#### Step 4: Trigger Deployment

1. Push your changes to your repository:
   ```bash
   git add .
   git commit -m "Add build script for static files collection"
   git push
   ```

2. Render will automatically detect the changes and redeploy

3. Or manually trigger a deploy from the Render dashboard

### Option 2: Manual Deployment

If you're deploying manually or using a different platform:

#### Step 1: Run collectstatic
```bash
python manage.py collectstatic --no-input
```

#### Step 2: Commit staticfiles
```bash
git add staticfiles/
git commit -m "Update collected static files"
git push
```

**Note:** This is not recommended as it bloats your repository. Use Option 1 instead.

### Option 3: Using Heroku

If you're using Heroku, add a `Procfile` with:

```
release: python manage.py collectstatic --noinput && python manage.py migrate
web: daphne -b 0.0.0.0 -p $PORT rdfs.asgi:application
```

## Verification Steps

After deployment, verify the fix:

### 1. Check Static Files URL
Open your browser's Developer Tools (F12) and check the Network tab:
- Look for requests to CSS files
- Verify they return 200 status (not 404)
- Check the file content to ensure it has the new CSS

### 2. Check Specific CSS Files
Visit these URLs directly in your browser:
```
https://your-domain.com/static/styles/vehicles/vehicle-list.css
https://your-domain.com/static/styles/vehicles/driver-list.css
```

Look for the `.filter-controls` and `.filter-select` CSS rules.

### 3. Hard Refresh Browser
Clear your browser cache or do a hard refresh:
- **Windows/Linux:** Ctrl + Shift + R or Ctrl + F5
- **Mac:** Cmd + Shift + R

### 4. Check WhiteNoise Configuration
Verify in `rdfs/settings.py`:
```python
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
```

This should already be set correctly.

## Understanding the Static Files Flow

### Development (localhost)
```
Browser Request → Django Dev Server → static/ folder → CSS file
```

### Production (hosting)
```
Browser Request → WhiteNoise → staticfiles/ folder → CSS file
                                      ↑
                                collectstatic command
                                      ↑
                                static/ folder
```

## Common Issues and Solutions

### Issue 1: "Permission denied" when running build.sh
**Solution:**
```bash
chmod +x build.sh
```

### Issue 2: collectstatic fails with "no such file or directory"
**Solution:** Ensure `STATIC_ROOT` is set in settings.py:
```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

### Issue 3: CSS still not loading after deployment
**Solutions:**
1. Clear browser cache (Ctrl + Shift + R)
2. Check browser console for 404 errors
3. Verify `STATIC_URL` in settings.py:
   ```python
   STATIC_URL = '/static/'
   ```
4. Check that WhiteNoise middleware is in MIDDLEWARE list

### Issue 4: Build command not running
**Solution:** Check Render logs:
1. Go to Render dashboard
2. Click on your service
3. Click "Logs"
4. Look for "collectstatic" output

## Files Modified in This Session

The following CSS files were updated and need to be collected:

1. `static/styles/vehicles/vehicle-list.css`
   - Added `.filter-controls` styles
   - Added `.filter-group` styles
   - Added `.filter-select` styles

2. `static/styles/vehicles/driver-list.css`
   - Added `.filter-controls` styles
   - Added `.filter-group` styles
   - Added `.filter-select` styles

3. `static/styles/terminal/qr-entry.css`
   - Reduced padding and margins throughout
   - Made layout more compact

4. `static/styles/terminal/qr-exit.css`
   - Reduced padding and margins throughout
   - Made layout more compact

## Quick Fix Checklist

- [ ] Create `build.sh` file (already done)
- [ ] Make `build.sh` executable: `chmod +x build.sh`
- [ ] Update Render Build Command to: `./build.sh`
- [ ] Commit and push changes
- [ ] Wait for deployment to complete
- [ ] Hard refresh browser (Ctrl + Shift + R)
- [ ] Verify CSS is loading in browser DevTools
- [ ] Test the Sort By dropdown functionality

## Expected Result

After following these steps:
1. The "Sort By" dropdown should appear with proper styling
2. The dropdown should have the RDFS blue color scheme
3. All filter controls should be visible and functional
4. The layout should match what you see on localhost

## Prevention for Future Updates

**Always run collectstatic when deploying CSS/JS changes:**

1. **Automatic (Recommended):** Use the build script
   - Build script runs collectstatic automatically
   - No manual intervention needed

2. **Manual:** Remember to run before deploying
   ```bash
   python manage.py collectstatic --no-input
   ```

## Additional Resources

- [Django Static Files Documentation](https://docs.djangoproject.com/en/stable/howto/static-files/)
- [WhiteNoise Documentation](http://whitenoise.evans.io/)
- [Render Static Files Guide](https://render.com/docs/deploy-django)

## Support

If you continue to have issues after following this guide:

1. Check the deployment logs for errors
2. Verify all environment variables are set correctly
3. Ensure `DEBUG=False` in production
4. Check that `ALLOWED_HOSTS` includes your domain

## Summary

The CSS not loading issue is caused by missing `collectstatic` command during deployment. The `build.sh` script has been created to automate this process. Update your Render build command to use this script, and all future deployments will automatically collect static files.
