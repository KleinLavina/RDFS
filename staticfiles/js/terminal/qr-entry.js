/* =====================================================
   QR ENTRY & DEPARTURE - JAVASCRIPT
   ===================================================== */

// Audio feedback
const successSound = new Audio("https://actions.google.com/sounds/v1/cartoon/clang_and_wobble.ogg");
const errorSound = new Audio("https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg");

// State management
let qrScanner = null;
let paused = false;
let awaitingReset = false;
let queuedQr = "";
let queueResetCooldown = false;
let lastScannedQr = "";

// DOM elements
const startCameraSection = document.getElementById("startCameraSection");
const startCameraBtn = document.getElementById("startCameraBtn");
const qrScannerWrap = document.getElementById("qrScannerWrap");
const feedbackArea = document.getElementById("feedbackArea");
const resetHint = document.getElementById("rdfsQrResetHint");
const resetOverlay = document.getElementById("rdfsQrResetCooldown");
const scannerStatus = document.getElementById("scannerStatus");
const container = document.querySelector(".qr-entry-container");

/* =====================================================
   FEEDBACK DISPLAY
   ===================================================== */
function showFeedback(message, type = "info") {
  // Clear existing feedback
  feedbackArea.innerHTML = "";
  
  // Create feedback element
  const feedback = document.createElement("div");
  feedback.className = `feedback-message feedback-${type}`;
  
  // Add icon based on type
  let icon = "bi-info-circle-fill";
  if (type === "success") icon = "bi-check-circle-fill";
  else if (type === "error") icon = "bi-x-circle-fill";
  else if (type === "warning") icon = "bi-exclamation-triangle-fill";
  
  feedback.innerHTML = `
    <i class="bi ${icon}"></i>
    <span>${message}</span>
  `;
  
  feedbackArea.appendChild(feedback);
  
  // Flash animation
  container.classList.remove("flash-success", "flash-error");
  if (type === "success") {
    container.classList.add("flash-success");
    playSound(successSound);
  } else if (type === "error") {
    container.classList.add("flash-error");
    playSound(errorSound);
  }
  
  // Update scanner status
  updateScannerStatus(type);
}

function updateScannerStatus(type) {
  const statusText = scannerStatus.querySelector(".status-text");
  const statusDot = scannerStatus.querySelector(".status-dot");
  
  if (type === "success") {
    statusText.textContent = "Success";
    statusDot.style.background = "#10b981";
  } else if (type === "error") {
    statusText.textContent = "Error";
    statusDot.style.background = "#ef4444";
  } else if (type === "warning") {
    statusText.textContent = "Warning";
    statusDot.style.background = "#f59e0b";
  } else {
    statusText.textContent = "Ready";
    statusDot.style.background = "#10b981";
  }
}

function playSound(audio) {
  audio.play().catch(() => {
    // Ignore audio play errors
  });
}

/* =====================================================
   RESET HINT & OVERLAY
   ===================================================== */
function toggleResetHint(show) {
  if (!resetHint) return;
  if (show) {
    resetHint.classList.add("active");
  } else {
    resetHint.classList.remove("active");
  }
}

function toggleResetCooldownOverlay(show) {
  if (!resetOverlay) return;
  if (show) {
    resetOverlay.classList.add("active");
  } else {
    resetOverlay.classList.remove("active");
  }
}

function startResetCooldown() {
  queueResetCooldown = true;
  toggleResetCooldownOverlay(true);
  
  setTimeout(() => {
    queueResetCooldown = false;
    toggleResetCooldownOverlay(false);
  }, 2000);
}

/* =====================================================
   QR CODE PROCESSING
   ===================================================== */
async function processQRCode(qrCode) {
  try {
    // Check if different QR scanned while awaiting reset
    if (awaitingReset && queuedQr && queuedQr !== qrCode) {
      awaitingReset = false;
      queuedQr = "";
      toggleResetHint(false);
    }
    
    // Check cooldown for reset confirmation
    if (awaitingReset && queueResetCooldown && queuedQr === qrCode) {
      showFeedback("⏳ Please wait 2 seconds before confirming your reset", "warning");
      return;
    }
    
    // Prepare request payload
    const payload = new URLSearchParams({ qr_code: qrCode });
    if (awaitingReset && queuedQr === qrCode) {
      payload.append("confirm_reset", "1");
    }
    
    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Send request
    const response = await fetch(window.location.href, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest"
      },
      body: payload
    });
    
    const data = await response.json();
    
    // Handle response
    if (data.status === "success") {
      awaitingReset = false;
      queuedQr = "";
      toggleResetHint(false);
      toggleResetCooldownOverlay(false);
      showFeedback(data.message, "success");
      pauseScanning(4000);
    } else if (data.status === "queued") {
      awaitingReset = true;
      queuedQr = qrCode;
      toggleResetHint(true);
      startResetCooldown();
      showFeedback(data.message, "warning");
      // Don't pause for queued status
    } else {
      awaitingReset = false;
      queuedQr = "";
      toggleResetHint(false);
      toggleResetCooldownOverlay(false);
      showFeedback(data.message, "error");
      pauseScanning(3000);
    }
    
  } catch (error) {
    console.error("QR processing error:", error);
    awaitingReset = false;
    queuedQr = "";
    toggleResetHint(false);
    showFeedback("Network error. Please try again.", "error");
    pauseScanning(3000);
  }
}

function pauseScanning(duration) {
  paused = true;
  
  setTimeout(() => {
    paused = false;
    lastScannedQr = "";
    showFeedback("Ready for next scan", "info");
  }, duration);
}

/* =====================================================
   CAMERA CONTROL
   ===================================================== */
function startCamera() {
  if (qrScanner) {
    showFeedback("Camera already started", "warning");
    return;
  }
  
  // Hide start section, show scanner
  startCameraSection.style.display = "none";
  qrScannerWrap.classList.add("active");
  
  // Initialize QR scanner
  qrScanner = new Html5Qrcode("rdfsQrReader");
  
  qrScanner.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: 250 },
    (decodedText) => {
      // Ignore if paused or duplicate scan (unless awaiting reset)
      if (paused || (decodedText === lastScannedQr && !awaitingReset)) {
        return;
      }
      
      lastScannedQr = decodedText;
      processQRCode(decodedText);
    }
  ).catch((error) => {
    console.error("Camera error:", error);
    showFeedback(`Camera error: ${error}`, "error");
    
    // Show start section again on error
    startCameraSection.style.display = "block";
    qrScannerWrap.classList.remove("active");
    qrScanner = null;
  });
  
  showFeedback("Camera started. Ready to scan.", "info");
}

/* =====================================================
   INITIALIZATION
   ===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  if (startCameraBtn) {
    startCameraBtn.addEventListener("click", startCamera);
  }
  
  // Initial feedback
  showFeedback("Click 'Start Camera' to begin scanning", "info");
});
