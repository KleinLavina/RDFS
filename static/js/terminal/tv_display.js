/**
 * TV Display - Auto-refresh departure board with countdown timers
 * Fetches updated data every 15 seconds without full page reload
 * Calculates countdown based on system settings and scheduled departure time
 */

// Global state
let currentEntries = [];
let countdownIntervals = {};
let serverTimeOffset = 0;

// Vehicle type icons mapping
const VEHICLE_TYPE_ICONS = {
  'jeepney': 'fa-shuttle-van',
  'van': 'fa-van-shuttle',
  'bus': 'fa-bus',
  'default': 'fa-bus'
};

// Update date and time display
function updateDateTime() {
  const now = new Date();
  const dateEl = document.getElementById('current-date');
  const timeEl = document.getElementById('current-time');
  
  if (dateEl) {
    const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    dateEl.textContent = now.toLocaleDateString('en-US', dateOptions);
  }
  
  if (timeEl) {
    const timeOptions = { hour12: true, hour: 'numeric', minute: '2-digit', second: '2-digit' };
    timeEl.textContent = now.toLocaleTimeString('en-US', timeOptions);
  }
}

// Get current server-synced time
function getServerTime() {
  return new Date(Date.now() + serverTimeOffset);
}

// Calculate countdown time remaining in seconds
function calculateCountdown(entryTimestamp, departureDurationMinutes) {
  const now = getServerTime();
  const entryTime = new Date(entryTimestamp);
  const departureTime = new Date(entryTime.getTime() + (departureDurationMinutes * 60 * 1000));
  const remainingMs = departureTime.getTime() - now.getTime();
  
  return Math.max(0, Math.floor(remainingMs / 1000));
}

// Format countdown as MM:SS
function formatCountdown(seconds) {
  if (seconds <= 0) return '00:00';
  
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// Get countdown CSS class based on remaining time
function getCountdownClass(seconds) {
  if (seconds <= 60) return 'critical';  // Last minute
  if (seconds <= 300) return 'warning';  // Last 5 minutes
  return '';
}

// Fetch and update departure data
async function refreshDepartureBoard() {
  const config = window.TV_DISPLAY_CONFIG;
  if (!config || !config.apiUrl) return;
  
  try {
    const response = await fetch(config.apiUrl);
    if (!response.ok) throw new Error('Failed to fetch');
    
    const data = await response.json();
    
    // Sync server time
    if (data.server_time) {
      const clientTime = Date.now();
      const serverTime = data.server_time * 1000;
      serverTimeOffset = serverTime - clientTime;
    }
    
    updateDepartureBoard(data);
    
  } catch (error) {
    console.error('Error refreshing departure board:', error);
  }
}

// Update the departure board with new data
function updateDepartureBoard(data) {
  const listEl = document.getElementById('departureList');
  const emptyEl = document.getElementById('emptyState');
  const config = window.TV_DISPLAY_CONFIG;
  
  if (!listEl) return;
  
  // Clear existing countdown intervals
  Object.values(countdownIntervals).forEach(interval => clearInterval(interval));
  countdownIntervals = {};
  
  // Extract all entries from route sections (only active vehicles)
  let allEntries = [];
  if (data.route_sections && Array.isArray(data.route_sections)) {
    data.route_sections.forEach(section => {
      if (section.entries && Array.isArray(section.entries)) {
        section.entries.forEach(entry => {
          // Only show active vehicles (Queued or Boarding)
          if (entry.status === 'Queued' || entry.status === 'Boarding') {
            allEntries.push({
              ...entry,
              route: section.name || 'Unknown Route'
            });
          }
        });
      }
    });
  }
  
  // Store current entries
  currentEntries = allEntries;
  
  // Clear current list
  listEl.innerHTML = '';
  
  // Show empty state if no entries
  if (allEntries.length === 0) {
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }
  
  if (emptyEl) emptyEl.style.display = 'none';
  
  // Sort by entry time (earliest first)
  allEntries.sort((a, b) => {
    const timeA = a.entry_time_numeric || a.entry_time_display || '';
    const timeB = b.entry_time_numeric || b.entry_time_display || '';
    return timeA.localeCompare(timeB);
  });
  
  // Create rows
  allEntries.forEach((entry, index) => {
    const row = createDepartureRow(entry, index, config.departureDuration);
    listEl.appendChild(row);
  });
}

// Create a departure row element
function createDepartureRow(entry, index, departureDuration) {
  const row = document.createElement('div');
  row.className = 'departure-row';
  row.dataset.entryId = entry.id;
  
  // Entry time column
  const entryTimeCol = document.createElement('div');
  entryTimeCol.className = 'col-entry-time';
  entryTimeCol.textContent = formatEntryTime(entry.entry_time_display);
  
  // Route column
  const routeCol = document.createElement('div');
  routeCol.className = 'col-route';
  routeCol.textContent = entry.route || 'N/A';
  
  // Vehicle column (plate + type with icon)
  const vehicleCol = document.createElement('div');
  vehicleCol.className = 'col-vehicle';
  
  const vehicleInfo = document.createElement('div');
  vehicleInfo.className = 'vehicle-info';
  
  const plateName = document.createElement('div');
  plateName.className = 'vehicle-plate';
  plateName.textContent = entry.vehicle_plate || 'N/A';
  
  // Get vehicle type from entry or infer from data
  const vehicleType = entry.vehicle_type || inferVehicleType(entry.vehicle_plate);
  const vehicleTypeIcon = VEHICLE_TYPE_ICONS[vehicleType] || VEHICLE_TYPE_ICONS.default;
  
  const typeBox = document.createElement('div');
  typeBox.className = 'vehicle-type';
  typeBox.innerHTML = `<i class="fa-solid ${vehicleTypeIcon}"></i>${capitalizeFirst(vehicleType)}`;
  
  vehicleInfo.appendChild(plateName);
  vehicleInfo.appendChild(typeBox);
  vehicleCol.appendChild(vehicleInfo);
  
  // Driver column
  const driverCol = document.createElement('div');
  driverCol.className = 'col-driver';
  driverCol.textContent = entry.driver_name || 'N/A';
  
  // Countdown column
  const countdownCol = document.createElement('div');
  countdownCol.className = 'col-countdown';
  
  const timerEl = document.createElement('div');
  timerEl.className = 'countdown-timer';
  timerEl.id = `countdown-${entry.id}`;
  
  const labelEl = document.createElement('div');
  labelEl.className = 'countdown-label';
  labelEl.textContent = entry.status === 'Boarding' ? 'Departing Soon' : 'Time Remaining';
  
  // Calculate initial countdown
  const entryTimestamp = parseEntryTimestamp(entry.entry_time_display);
  const initialSeconds = calculateCountdown(entryTimestamp, departureDuration);
  timerEl.textContent = formatCountdown(initialSeconds);
  timerEl.className = `countdown-timer ${getCountdownClass(initialSeconds)}`;
  
  countdownCol.appendChild(timerEl);
  countdownCol.appendChild(labelEl);
  
  // Start countdown interval for this entry
  startCountdownInterval(entry.id, entryTimestamp, departureDuration);
  
  // Append all columns
  row.appendChild(entryTimeCol);
  row.appendChild(routeCol);
  row.appendChild(vehicleCol);
  row.appendChild(driverCol);
  row.appendChild(countdownCol);
  
  return row;
}

// Start countdown interval for a specific entry
function startCountdownInterval(entryId, entryTimestamp, departureDuration) {
  // Clear existing interval if any
  if (countdownIntervals[entryId]) {
    clearInterval(countdownIntervals[entryId]);
  }
  
  // Update countdown every second
  countdownIntervals[entryId] = setInterval(() => {
    const timerEl = document.getElementById(`countdown-${entryId}`);
    if (!timerEl) {
      clearInterval(countdownIntervals[entryId]);
      delete countdownIntervals[entryId];
      return;
    }
    
    const remainingSeconds = calculateCountdown(entryTimestamp, departureDuration);
    timerEl.textContent = formatCountdown(remainingSeconds);
    timerEl.className = `countdown-timer ${getCountdownClass(remainingSeconds)}`;
    
    // Stop countdown when time is up
    if (remainingSeconds <= 0) {
      clearInterval(countdownIntervals[entryId]);
      delete countdownIntervals[entryId];
    }
  }, 1000);
}

// Parse entry timestamp from display string
function parseEntryTimestamp(timeStr) {
  if (!timeStr) return new Date();
  
  try {
    // Try parsing as ISO string first
    const date = new Date(timeStr);
    if (!isNaN(date.getTime())) {
      return date;
    }
    
    // If that fails, try parsing common formats
    // Format: "Jan 27, 2026 02:30 PM"
    const parsed = new Date(timeStr);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
    
    return new Date();
  } catch (e) {
    console.error('Error parsing timestamp:', timeStr, e);
    return new Date();
  }
}

// Format entry time for display (HH:MM AM/PM)
function formatEntryTime(timeStr) {
  if (!timeStr) return '--:--';
  
  try {
    const date = new Date(timeStr);
    if (isNaN(date.getTime())) return timeStr;
    
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  } catch (e) {
    return timeStr;
  }
}

// Infer vehicle type from plate or other data (fallback)
function inferVehicleType(plate) {
  // This is a fallback - ideally vehicle type comes from backend
  // You can add logic here to infer from plate patterns if needed
  return 'jeepney'; // Default
}

// Capitalize first letter
function capitalizeFirst(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  const config = window.TV_DISPLAY_CONFIG;
  
  // Sync server time if provided
  if (config && config.serverTime) {
    try {
      const serverTime = new Date(config.serverTime).getTime();
      const clientTime = Date.now();
      serverTimeOffset = serverTime - clientTime;
    } catch (e) {
      console.error('Error syncing server time:', e);
    }
  }
  
  // Update date/time immediately and every second
  updateDateTime();
  setInterval(updateDateTime, 1000);
  
  // Load initial data
  refreshDepartureBoard();
  
  // Set up auto-refresh
  const refreshInterval = (config && config.refreshInterval) || 15;
  setInterval(refreshDepartureBoard, refreshInterval * 1000);
  
  console.log(`TV Display initialized - Auto-refresh every ${refreshInterval} seconds`);
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
  Object.values(countdownIntervals).forEach(interval => clearInterval(interval));
});
