// =====================================================
// DRIVER LIST - AUTO-FILTERING SEARCH & SORTING
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('driverSearch');
  const sortSelect = document.getElementById('sortBy');
  const clearBtn = document.getElementById('clearSearch');
  const tableBody = document.getElementById('driversTableBody');
  const resultsText = document.getElementById('resultsText');
  const loadingIndicator = document.getElementById('loadingIndicator');
  
  let searchTimeout;
  const DEBOUNCE_DELAY = 300; // ms

  // Show/hide clear button based on input
  function updateClearButton() {
    if (searchInput && clearBtn) {
      clearBtn.style.display = searchInput.value.trim() ? 'block' : 'none';
    }
  }

  // Clear search
  if (clearBtn) {
    clearBtn.addEventListener('click', function() {
      searchInput.value = '';
      updateClearButton();
      performSearch();
    });
  }

  // Debounced search on input
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      updateClearButton();

      // Clear previous timeout
      clearTimeout(searchTimeout);

      // Show loading indicator
      if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
      }

      // Debounce the search
      searchTimeout = setTimeout(() => {
        performSearch();
      }, DEBOUNCE_DELAY);
    });

    // Initial state
    updateClearButton();
  }

  // Sort change handler
  if (sortSelect) {
    sortSelect.addEventListener('change', function() {
      performSearch();
    });

    // Restore sort from URL
    const urlParams = new URLSearchParams(window.location.search);
    const sortParam = urlParams.get('sort');
    if (sortParam) {
      sortSelect.value = sortParam;
    }
  }

  // Perform the actual search
  function performSearch() {
    const query = searchInput ? searchInput.value.trim() : '';
    const sortBy = sortSelect ? sortSelect.value : 'name-asc';
    
    const url = new URL(window.location.href);
    
    if (query) {
      url.searchParams.set('q', query);
    } else {
      url.searchParams.delete('q');
    }

    if (sortBy && sortBy !== 'name-asc') {
      url.searchParams.set('sort', sortBy);
    } else {
      url.searchParams.delete('sort');
    }

    // Show loading
    if (loadingIndicator) {
      loadingIndicator.style.display = 'flex';
    }

    // Fetch filtered results
    fetch(url.toString(), {
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.text())
    .then(html => {
      // Parse the response HTML
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      
      // Extract the table body
      const newTableBody = doc.getElementById('driversTableBody');
      if (newTableBody && tableBody) {
        tableBody.innerHTML = newTableBody.innerHTML;
      }

      // Update results counter
      const newResultsText = doc.getElementById('resultsText');
      if (newResultsText && resultsText) {
        resultsText.innerHTML = newResultsText.innerHTML;
      }

      // Update URL without reload
      window.history.replaceState({}, '', url.toString());

      // Hide loading indicator
      if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
      }
    })
    .catch(error => {
      console.error('Search error:', error);
      
      // Hide loading indicator
      if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
      }
    });
  }
});
