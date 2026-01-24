document.addEventListener('DOMContentLoaded', () => {
  const toastContainer = document.querySelector('.toast-container');
  const toastDataElement = document.getElementById('toastMessages');

  if (toastContainer && toastDataElement) {
    let toastMessages = [];

    try {
      toastMessages = JSON.parse(toastDataElement.textContent || '[]');
    } catch (error) {
      toastMessages = [];
    }

    toastMessages.forEach((toastItem) => {
      const tags = toastItem.tags === 'error' ? 'danger' : toastItem.tags || 'info';
      const toast = document.createElement('div');
      toast.className = `toast align-items-center text-bg-${tags} border-0`;
      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body fw-semibold">${toastItem.message}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>`;
      toastContainer.appendChild(toast);
      new bootstrap.Toast(toast, { delay: 3500 }).show();
    });
  }

  const toggle = document.getElementById('sidebarToggle');
  if (!toggle) {
    return;
  }

  const backdrop = document.getElementById('sidebarBackdrop');
  const body = document.body;
  const collapseQuery = window.matchMedia('(max-width: 992px)');
  const icon = toggle.querySelector('i');
  const storage = window.localStorage;
  const COLLAPSED_KEY = 'rdfs-sidebar-collapsed';
  const GROUPS_KEY = 'rdfs-sidebar-open-groups';

  body.classList.remove('sidebar-open');

  const applyCollapsedFromStorage = () => {
    if (storage) {
      const stored = storage.getItem(COLLAPSED_KEY);
      if (stored === 'true') {
        body.classList.add('sidebar-collapsed');
      } else {
        body.classList.remove('sidebar-collapsed');
      }
    }
  };

  applyCollapsedFromStorage();

  const updateState = () => {
    const isMobile = collapseQuery.matches;
    const isOpen = isMobile
      ? body.classList.contains('sidebar-open')
      : !body.classList.contains('sidebar-collapsed');

    const tooltipText = isOpen ? 'Collapse sidebar' : 'Expand sidebar';
    toggle.setAttribute('aria-expanded', String(isOpen));
    toggle.setAttribute('aria-label', tooltipText);
    toggle.setAttribute('data-tooltip', tooltipText);
    toggle.dataset.tooltip = tooltipText;
    if (icon) {
      icon.classList.toggle('bi-chevron-left', isOpen);
      icon.classList.toggle('bi-chevron-right', !isOpen);
    }
    if (backdrop) {
      const showBackdrop = isMobile && body.classList.contains('sidebar-open');
      backdrop.classList.toggle('visible', showBackdrop);
    }
  };

  const toggleSidebar = () => {
    if (collapseQuery.matches) {
      body.classList.toggle('sidebar-open');
    } else {
      body.classList.toggle('sidebar-collapsed');
    }
    updateState();
    toggle.blur();
    if (!collapseQuery.matches && storage) {
      storage.setItem(COLLAPSED_KEY, String(body.classList.contains('sidebar-collapsed')));
    }
  };

  toggle.addEventListener('click', toggleSidebar);

    if (backdrop) {
      backdrop.addEventListener('click', () => {
        body.classList.remove('sidebar-open');
        updateState();
      });
    }

  collapseQuery.addEventListener('change', () => {
    body.classList.remove('sidebar-open');
    updateState();
  });

  updateState();

  const activeSidebar = document.querySelector('.rdfs-sidebar, .rdfs-adm-sb');
  if (!activeSidebar) return;
  
  const groupToggleSelector = activeSidebar.classList.contains('rdfs-sidebar') 
    ? '.rdfs-sidebar__group-toggle' 
    : '.rdfs-adm-sb__group-toggle';
  
  const groupButtons = activeSidebar.querySelectorAll(groupToggleSelector);
  const loadGroupState = () => {
    if (!storage) return [];
    try {
      const raw = storage.getItem(GROUPS_KEY);
      if (raw) return JSON.parse(raw);
    } catch (error) {
      return [];
    }
    return [];
  };
  const saveGroupState = (groups) => {
    if (!storage) return;
    storage.setItem(GROUPS_KEY, JSON.stringify(groups));
  };
  const persistedGroups = loadGroupState();
  const toggleGroupState = (button, list, groupId, open) => {
    if (!button) return;
    button.setAttribute('aria-expanded', String(open));
    if (list) {
      list.setAttribute('aria-hidden', String(!open));
      list.style.maxHeight = open ? `${list.scrollHeight}px` : '';
    }
    if (storage && groupId) {
      const currentGroups = loadGroupState();
      const has = currentGroups.includes(groupId);
      if (open && !has) {
        currentGroups.push(groupId);
      } else if (!open && has) {
        currentGroups.splice(currentGroups.indexOf(groupId), 1);
      }
      saveGroupState(currentGroups);
    }
  };

  groupButtons.forEach((button) => {
    const list = button.nextElementSibling;
    const groupId = button.dataset.group;
    if (groupId && persistedGroups.includes(groupId)) {
      toggleGroupState(button, list, groupId, true);
    }

    button.addEventListener('click', () => {
      const isOpen = button.getAttribute('aria-expanded') === 'true';
      toggleGroupState(button, list, groupId, !isOpen);
    });
  });

  const normalizePath = (path) => path.replace(/\/$/, '') || '/';
  const highlightActiveLink = () => {
    const currentPath = normalizePath(window.location.pathname);
    const activeSidebar = document.querySelector('.rdfs-sidebar, .rdfs-adm-sb');
    if (!activeSidebar) return;
    
    const linkSelector = activeSidebar.classList.contains('rdfs-sidebar') 
      ? '.rdfs-sidebar__link' 
      : '.rdfs-adm-sb__link';
    
    activeSidebar.querySelectorAll(linkSelector).forEach((link) => {
      let linkPath = link.getAttribute('href') || '';
      try {
        linkPath = normalizePath(new URL(link.href, window.location.origin).pathname);
      } catch {
        linkPath = normalizePath(linkPath);
      }
      const isActive = linkPath === currentPath;
      link.classList.toggle('active', isActive);
      if (isActive) {
        const groupListClass = activeSidebar.classList.contains('rdfs-sidebar') 
          ? '.rdfs-sidebar__group-list' 
          : '.rdfs-adm-sb__group-list';
        const parentList = link.closest(groupListClass);
        const toggleButton = parentList?.previousElementSibling;
        const groupId = toggleButton?.dataset?.group;
        if (toggleButton && parentList && groupId) {
          toggleGroupState(toggleButton, parentList, groupId, true);
        }
      }
    });
  };

  highlightActiveLink();
});
