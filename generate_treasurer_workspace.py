#!/usr/bin/env python
"""Generate the complete treasurer workspace HTML file"""

html_content = '''{% extends "base.html" %}
{% load static %}
{% block title %}Treasurer Workspace | RDFS{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="{% static 'styles/accounts/treasurer-workspace.css' %}">
{% endblock %}

{% block content %}
<div class="treasurer-workspace">
  <div class="workspace-container">
    
    <div class="workspace-header">
      <h1 class="workspace-title">
        <i class="fas fa-briefcase"></i>
        Treasurer Workspace
      </h1>
      <button class="btn-new-deposit" id="openModalBtn">
        <i class="fas fa-plus-circle"></i>
        New Deposit Request
      </button>
    </div>

    <div class="workspace-tabs">
      <button class="tab-btn active" data-tab="dashboard">
        <i class="fas fa-chart-line"></i>
        Dashboard
      </button>
      <button class="tab-btn" data-tab="deposit-history">
        <i class="fas fa-history"></i>
        Deposit History
      </button>
    </div>

    <!-- Dashboard Tab -->
    <div class="tab-content active" id="dashboard-tab">
      <div class="stats-grid">
        <div class="stat-card pending">
          <div class="stat-icon">
            <i class="bi bi-clock-history"></i>
          </div>
          <div class="stat-content">
            <h3>{{ my_pending }}</h3>
            <p>Pending Requests</p>
          </div>
        </div>

        <div class="stat-card approved">
          <div class="stat-icon">
            <i class="bi bi-check-circle"></i>
          </div>
          <div class="stat-content">
            <h3>{{ my_approved }}</h3>
            <p>Approved</p>
          </div>
        </div>

        <div class="stat-card rejected">
          <div class="stat-icon">
            <i class="bi bi-x-circle"></i>
          </div>
          <div class="stat-content">
            <h3>{{ my_rejected }}</h3>
            <p>Rejected</p>
          </div>
        </div>
      </div>

      <div class="deposits-card">
        <div class="card-header">
          <h2 class="card-title">
            <i class="fas fa-clock"></i>
            Recent Deposits
          </h2>
        </div>
        {% if recent_deposits %}
        <div class="table-responsive">
          <table class="deposits-table">
            <thead>
              <tr>
                <th>OR Code</th>
                <th>Vehicle</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date</th>
                <th>Approved By</th>
              </tr>
            </thead>
            <tbody>
              {% for deposit in recent_deposits %}
              <tr>
                <td><strong>{{ deposit.or_code }}</strong></td>
                <td>{{ deposit.wallet.vehicle.vehicle_name }} ({{ deposit.wallet.vehicle.license_plate }})</td>
                <td>₱{{ deposit.amount|floatformat:2 }}</td>
                <td>
                  <span class="status-badge status-{{ deposit.status }}">
                    {{ deposit.get_status_display }}
                  </span>
                </td>
                <td>{{ deposit.created_at|date:"M d, Y g:i A" }}</td>
                <td>
                  {% if deposit.approved_by %}
                    {{ deposit.approved_by.get_full_name }}
                  {% else %}
                    <span class="text-muted">—</span>
                  {% endif %}
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        {% else %}
        <p class="no-data">No deposit requests yet. Create your first request above.</p>
        {% endif %}
      </div>
    </div>

    <!-- Deposit History Tab -->
    <div class="tab-content" id="deposit-history-tab">
      <div class="deposits-card">
        <div class="card-header">
          <h2 class="card-title">
            <i class="fas fa-history"></i>
            All Deposit Requests
          </h2>
          <div class="filter-group">
            <label for="statusFilter">Filter:</label>
            <select id="statusFilter" onchange="filterDeposits(this.value)">
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>
        {% if all_deposits %}
        <div class="table-responsive">
          <table class="deposits-table">
            <thead>
              <tr>
                <th>OR Code</th>
                <th>Driver</th>
                <th>Vehicle</th>
                <th>License Plate</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date Created</th>
                <th>Approved By</th>
                <th>Approved At</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody id="depositsTableBody">
              {% for deposit in all_deposits %}
              <tr data-status="{{ deposit.status }}">
                <td><strong>{{ deposit.or_code }}</strong></td>
                <td>{{ deposit.wallet.vehicle.assigned_driver.first_name }} {{ deposit.wallet.vehicle.assigned_driver.last_name }}</td>
                <td>{{ deposit.wallet.vehicle.vehicle_name }}</td>
                <td>{{ deposit.wallet.vehicle.license_plate }}</td>
                <td><strong>₱{{ deposit.amount|floatformat:2 }}</strong></td>
                <td>
                  <span class="status-badge status-{{ deposit.status }}">
                    {{ deposit.get_status_display }}
                  </span>
                </td>
                <td>{{ deposit.created_at|date:"M d, Y g:i A" }}</td>
                <td>
                  {% if deposit.approved_by %}
                    {{ deposit.approved_by.get_full_name }}
                  {% else %}
                    <span style="color: #6c757d;">—</span>
                  {% endif %}
                </td>
                <td>
                  {% if deposit.approved_at %}
                    {{ deposit.approved_at|date:"M d, Y g:i A" }}
                  {% else %}
                    <span style="color: #6c757d;">—</span>
                  {% endif %}
                </td>
                <td>
                  {% if deposit.notes %}
                    {{ deposit.notes|truncatewords:10 }}
                  {% else %}
                    <span style="color: #6c757d;">—</span>
                  {% endif %}
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        {% else %}
        <p class="no-data">No deposit requests found.</p>
        {% endif %}
      </div>
    </div>

  </div>
</div>

<!-- Modal Overlay -->
<div class="modal-overlay" id="modalOverlay"></div>

<!-- Modal Container -->
<div class="modal-container" id="depositModal">
  <div class="modal-header">
    <h2 class="modal-title">
      <i class="fas fa-money-bill-wave"></i>
      New Deposit Request
    </h2>
    <button class="modal-close" id="closeModalBtn">
      <i class="fas fa-times"></i>
    </button>
  </div>
  <div class="modal-body">
    <iframe id="depositFormFrame" src="{% url 'terminal:treasurer_request_deposit' %}" style="width:100%; height:600px; border:none;"></iframe>
  </div>
</div>

<script>
// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', function() {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    // Add active class to clicked tab
    this.classList.add('active');
    
    // Show corresponding content
    const tabName = this.dataset.tab;
    document.getElementById(tabName + '-tab').classList.add('active');
  });
});

// Modal Controls
const modal = document.getElementById('depositModal');
const overlay = document.getElementById('modalOverlay');
const openBtn = document.getElementById('openModalBtn');
const closeBtn = document.getElementById('closeModalBtn');

function openModal() {
  modal.classList.add('show');
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  modal.classList.remove('show');
  overlay.classList.remove('show');
  document.body.style.overflow = '';
}

openBtn.addEventListener('click', openModal);
closeBtn.addEventListener('click', closeModal);
overlay.addEventListener('click', closeModal);

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && modal.classList.contains('show')) {
    closeModal();
  }
});

// Listen for form submission success from iframe
window.addEventListener('message', function(e) {
  if (e.data === 'deposit_success') {
    closeModal();
    // Reload page to show new deposit
    window.location.reload();
  }
});

// Filter deposits
function filterDeposits(status) {
  const rows = document.querySelectorAll('#depositsTableBody tr');
  rows.forEach(row => {
    if (!status || row.dataset.status === status) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}
</script>
{% endblock %}
'''

# Write to file
with open('templates/accounts/treasurer_workspace.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("File created successfully!")
