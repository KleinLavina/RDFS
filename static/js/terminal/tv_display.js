/**
 * TV Display - Auto-refresh departure board
 * Fetches updated data every 15 seconds without full page reload
 */

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

// Fetch and update departure data
async function refreshDepartureBoard() {
  const config = window.TV_DISPLAY_CONFIG;
  if (!config || !config.apiUrl) return;
  
  try {
    const response = await fetch(config.apiUrl);
    if (!response.ok) throw new Error('Failed to fetch');
    
    const data = await response.json();
    updateDepartureBoard(data);
    
  } catch (error) {
    console.error('Error refreshing departure board:', error);
  }
}

// Update the departure board with new data
function updateDepartureBoard(data) {
  const listEl = document.getElementById('departureList');
  const emptyEl = document.getElementById('emptyState');
  
  if (!listEl) return;
  
  // Extract all entries from route sections
  let allEntries = [];
  if (data.route_sections && Array.isArray(data.route_sections)) {
    data.route_sections.forEach(section => {
      if (section.entries && Array.isArray(section.entries)) {
        section.entries.forEach(entry => {
          // Only show boarding or departing status
          if (entry.status === 'Boarding' || entry.status === 'Departing') {
            allEntries.push({
              ...entry,
              route: section.name || 'Unknown Route'
            });
          }
        });
      }
    });
  }
  
  // Clear current list
  listEl.innerHTML = '';
  
  // Show empty state if no entries
  if (allEntries.length === 0) {
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }
  
  if (emptyEl) emptyEl.style.display = 'none';
  
  // Sort by departure time (earliest first)
  allEntries.sort((a, b) => {
    const timeA = a.departure_time || a.entry_time || '';
    const timeB = b.departure_time || b.entry_time || '';
    return timeA.localeCompare(timeB);
  });
  
  // Create rows
  allEntries.forEach(entry => {
    const row = createDepartureRow(entry);
    listEl.appendChild(row);
  });
}

// Create a departure row element
function createDepartureRow(entry) {
  const row = document.createElement('div');
  row.className = 'departure-row';
  
  // Departure time
  const timeCol = document.createElement('div');
  timeCol.className = 'col-time';
  timeCol.textContent = formatTime(entry.departure_time || entry.entry_time);
  
  // Route
  const routeCol = document.createElement('div');
  routeCol.className = 'col-route';
  routeCol.textContent = entry.route || 'N/A';
  
  // Destination
  const destCol = document.createElement('div');
  destCol.className = 'col-destination';
  destCol.innerHTML = `<i class="fa-solid fa-location-dot"></i>${entry.destination || entry.route || 'N/A'}`;
  
  // Vehicle
  const vehicleCol = document.createElement('div');
  vehicleCol.className = 'col-vehicle';
  vehicleCol.textContent = entry.vehicle || entry.license_plate || 'N/A';
  
  // Status
  const statusCol = document.createElement('div');
  statusCol.className = 'col-status';
  
  const statusBadge = document.createElement('div');
  const status = entry.status || 'Unknown';
  statusBadge.className = `status-badge status-${status.toLowerCase()}`;
  
  let icon = 'fa-circle-info';
  if (status === 'Boarding') icon = 'fa-door-open';
  else if (status === 'Departing') icon = 'fa-bus';
  else if (status === 'Departed') icon = 'fa-check-circle';
  
  statusBadge.innerHTML = `<i class="fa-solid ${icon}"></i>${status}`;
  statusCol.appendChild(statusBadge);
  
  // Append all columns
  row.appendChild(timeCol);
  row.appendChild(routeCol);
  row.appendChild(destCol);
  row.appendChild(vehicleCol);
  row.appendChild(statusCol);
  
  return row;
}

// Format time string
function formatTime(timeStr) {
  if (!timeStr) return '--:--';
  
  try {
    // If it's already in HH:MM format
    if (/^\d{1,2}:\d{2}/.test(timeStr)) {
      return timeStr.substring(0, 5);
    }
    
    // Try to parse as date
    const date = new Date(timeStr);
    if (!isNaN(date.getTime())) {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    }
    
    return timeStr;
  } catch (e) {
    return '--:--';
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  const config = window.TV_DISPLAY_CONFIG;
  
  // Update date/time immediately and every second
  updateDateTime();
  setInterval(updateDateTime, 1000);
  
  // Load initial data if provided
  if (config && config.initialData) {
    updateDepartureBoard({ route_sections: config.initialData });
  }
  
  // Set up auto-refresh
  const refreshInterval = (config && config.refreshInterval) || 15;
  setInterval(refreshDepartureBoard, refreshInterval * 1000);
  
  console.log(`TV Display initialized - Auto-refresh every ${refreshInterval} seconds`);
});
