// =====================================================
// RDFS – DEPOSIT MANAGEMENT JAVASCRIPT
// =====================================================

document.addEventListener("DOMContentLoaded", function () {
  
  // ============================================
  // TAB SWITCHING
  // ============================================
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  
  // Check URL for tab parameter
  const urlParams = new URLSearchParams(window.location.search);
  const activeTab = urlParams.get('tab') || 'wallets';
  
  // Activate correct tab on load
  tabBtns.forEach(btn => {
    if (btn.dataset.tab === activeTab) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  tabContents.forEach(content => {
    if (content.id === `${activeTab}-tab`) {
      content.classList.add('active');
    } else {
      content.classList.remove('active');
    }
  });
  
  // Tab click handlers
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      
      // Update buttons
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // Update content
      tabContents.forEach(content => {
        content.classList.remove('active');
        if (content.id === `${targetTab}-tab`) {
          content.classList.add('active');
        }
      });
      
      // Update URL without reload
      const newUrl = new URL(window.location);
      newUrl.searchParams.set('tab', targetTab);
      window.history.pushState({}, '', newUrl);
    });
  });
  
  // ============================================
  // LIVE SEARCH & FILTER (WALLETS TAB)
  // ============================================
  const searchInput = document.getElementById("liveSearchInput");
  const sortSelect = document.getElementById("liveSortSelect");
  const tableBody = document.getElementById("walletsTableBody");
  const loadingIndicator = document.getElementById("loadingIndicator");
  const visibleCountEl = document.getElementById("visibleCount");
  
  if (searchInput && sortSelect && tableBody) {
    let debounceTimer = null;
    const allRows = Array.from(tableBody.querySelectorAll("tr[data-driver]"));
    
    function filterAndSort() {
      const query = searchInput.value.toLowerCase().trim();
      const sortBy = sortSelect.value;
      
      // Show loading
      if (loadingIndicator) {
        loadingIndicator.classList.add("active");
      }
      
      // Filter rows
      let visibleRows = allRows.filter(row => {
        if (!query) return true;
        const driver = row.dataset.driver || "";
        const plate = row.dataset.plate || "";
        const license = row.dataset.license || "";
        return driver.includes(query) || plate.includes(query) || license.includes(query);
      });
      
      // Sort rows
      visibleRows.sort((a, b) => {
        switch (sortBy) {
          case "largest":
            return parseFloat(b.dataset.balance || 0) - parseFloat(a.dataset.balance || 0);
          case "smallest":
            return parseFloat(a.dataset.balance || 0) - parseFloat(b.dataset.balance || 0);
          case "driver_asc":
            return (a.dataset.driver || "").localeCompare(b.dataset.driver || "");
          case "driver_desc":
            return (b.dataset.driver || "").localeCompare(a.dataset.driver || "");
          case "newest":
          default:
            return (b.dataset.date || "").localeCompare(a.dataset.date || "");
        }
      });
      
      // Hide all rows first
      allRows.forEach(row => row.style.display = "none");
      
      // Show and reorder visible rows
      visibleRows.forEach((row, index) => {
        row.style.display = "";
        const rowNumber = row.querySelector(".row-number");
        if (rowNumber) {
          rowNumber.textContent = index + 1;
        }
        tableBody.appendChild(row); // Move to end to maintain order
      });
      
      // Update count
      if (visibleCountEl) {
        visibleCountEl.textContent = visibleRows.length;
      }
      
      // Show empty state if no results
      let emptyRow = tableBody.querySelector("#emptyRow");
      if (visibleRows.length === 0) {
        if (!emptyRow) {
          emptyRow = document.createElement("tr");
          emptyRow.id = "emptyRow";
          emptyRow.innerHTML = `
            <td colspan="8" class="text-center text-muted py-4">
              <i class="fas fa-search fs-1 d-block mb-2 opacity-50"></i>
              No wallets match "${searchInput.value}"
            </td>
          `;
          tableBody.appendChild(emptyRow);
        }
        emptyRow.style.display = "";
      } else if (emptyRow) {
        emptyRow.style.display = "none";
      }
      
      // Hide loading
      setTimeout(() => {
        if (loadingIndicator) {
          loadingIndicator.classList.remove("active");
        }
      }, 150);
    }
    
    // Debounced search
    searchInput.addEventListener("input", function() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(filterAndSort, 200);
    });
    
    // Instant sort change
    sortSelect.addEventListener("change", filterAndSort);
    
    // Initial filter/sort on page load
    filterAndSort();
  }
  
  // ============================================
  // ADD DEPOSIT MODAL LOGIC
  // ============================================
  const driverInput = document.getElementById("driverSearch");
  const suggestionBox = document.getElementById("driverSuggestions");
  const vehicleField = document.getElementById("vehicleId");
  const walletInfo = document.getElementById("walletInfo");
  const submitButton = document.getElementById("submitDepositBtn");
  const selectedLabel = document.getElementById("selectedLabel");
  const depositAmount = document.getElementById("depositAmount");
  
  if (driverInput && suggestionBox && vehicleField) {
    
    function renderSuggestions(value) {
      suggestionBox.innerHTML = "";
      const query = value.trim().toLowerCase();
      if (!query) return;

      const matches = driverOptions.filter(option => {
        return (
          option.driver_name.toLowerCase().includes(query) ||
          option.license_plate.toLowerCase().includes(query) ||
          (option.license_number || "").toLowerCase().includes(query)
        );
      }).slice(0, 6);

      if (!matches.length) {
        const item = document.createElement("div");
        item.className = "suggestion-item empty";
        item.innerHTML = '<i class="fas fa-user-slash me-2 opacity-50"></i> No matching driver found';
        suggestionBox.appendChild(item);
        return;
      }

      matches.forEach(option => {
        const item = document.createElement("div");
        item.className = "suggestion-item";
        item.dataset.vehicleId = option.vehicle_id;
        item.dataset.display = option.display;
        item.innerHTML = `
          <div class="suggestion-name">${option.display}</div>
          <div class="suggestion-details">License: ${option.license_number || 'N/A'}</div>
        `;
        suggestionBox.appendChild(item);
      });
    }

    function toggleSubmitState() {
      if (submitButton) {
        submitButton.disabled = !vehicleField.value || !depositAmount.value || parseFloat(depositAmount.value) <= 0;
      }
    }

    driverInput.addEventListener("input", function () {
      suggestionBox.innerHTML = "";
      if (walletInfo) walletInfo.textContent = "";
      vehicleField.value = "";
      if (selectedLabel) {
        selectedLabel.textContent = driverInput.value
          ? `Searching for "${driverInput.value}"...`
          : 'Select a driver to proceed';
      }
      toggleSubmitState();
      renderSuggestions(driverInput.value);
    });

    suggestionBox.addEventListener("click", function (event) {
      const entry = event.target.closest(".suggestion-item");
      if (!entry || !entry.dataset.vehicleId || entry.classList.contains('empty')) return;
      
      vehicleField.value = entry.dataset.vehicleId;
      driverInput.value = entry.dataset.display;
      if (selectedLabel) {
        selectedLabel.innerHTML = `<i class="fas fa-user-check me-1 text-success"></i> ${entry.dataset.display}`;
      }
      suggestionBox.innerHTML = "";
      toggleSubmitState();
      fetchBalance(entry.dataset.vehicleId);
    });

    document.addEventListener("click", function (event) {
      if (!suggestionBox.contains(event.target) && event.target !== driverInput) {
        suggestionBox.innerHTML = "";
      }
    });

    if (depositAmount) {
      depositAmount.addEventListener("input", toggleSubmitState);
    }

    function fetchBalance(vehicleId) {
      if (!walletInfo) return;
      
      walletInfo.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Checking balance...';
      
      const url = new URL(window.location.origin + '/terminal/ajax-get-wallet-balance/');
      url.searchParams.append('vehicle_id', vehicleId);
      
      fetch(url)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            walletInfo.innerHTML = `<i class="fas fa-wallet me-1"></i> Current balance: <strong>₱${data.balance.toFixed(2)}</strong>`;
          } else {
            walletInfo.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i> ${data.message}</span>`;
          }
        })
        .catch(() => {
          walletInfo.innerHTML = '<span class="text-muted">Unable to fetch balance</span>';
        });
    }

    toggleSubmitState();
  }
  
  // ============================================
  // QUICK DEPOSIT BUTTONS
  // ============================================
  const addDepositModalEl = document.getElementById("addDepositModal");
  const bootstrapModal = addDepositModalEl && window.bootstrap ? new bootstrap.Modal(addDepositModalEl) : null;

  document.querySelectorAll(".btn-deposit").forEach(btn => {
    btn.addEventListener("click", () => {
      const vehicleId = btn.dataset.vehicle;
      const display = btn.dataset.display;
      if (!vehicleId || !driverInput || !vehicleField) return;

      driverInput.value = display;
      vehicleField.value = vehicleId;
      if (selectedLabel) {
        selectedLabel.innerHTML = `<i class="fas fa-user-check me-1 text-success"></i> ${display}`;
      }
      if (suggestionBox) {
        suggestionBox.innerHTML = "";
      }
      
      toggleSubmitState();
      fetchBalance(vehicleId);

      if (bootstrapModal) {
        bootstrapModal.show();
      }
    });
  });
  
  // ============================================
  // RESET MODAL ON CLOSE
  // ============================================
  if (addDepositModalEl) {
    addDepositModalEl.addEventListener('hidden.bs.modal', function () {
      if (driverInput) driverInput.value = '';
      if (vehicleField) vehicleField.value = '';
      if (depositAmount) depositAmount.value = '';
      if (walletInfo) walletInfo.innerHTML = '';
      if (selectedLabel) selectedLabel.textContent = 'Select a driver to proceed';
      if (suggestionBox) suggestionBox.innerHTML = '';
      toggleSubmitState();
    });
  }
  
});
