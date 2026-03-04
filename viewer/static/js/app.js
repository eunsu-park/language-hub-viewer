/**
 * Language Viewer - Main JavaScript
 */

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initSidebar();
    initSearch();
    initSidebarCollapse();
});

function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;

    if (!html.getAttribute('data-theme')) {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        html.setAttribute('data-theme', localStorage.getItem('theme') || (prefersDark ? 'dark' : 'light'));
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('theme')) {
            html.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}

function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const sidebarToggle = document.getElementById('sidebar-toggle');

    function openSidebar() {
        sidebar.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        document.body.style.overflow = '';
    }

    if (menuToggle) {
        menuToggle.addEventListener('click', openSidebar);
    }
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', closeSidebar);
    }

    document.addEventListener('click', function(e) {
        if (sidebar && sidebar.classList.contains('open')) {
            if (!sidebar.contains(e.target) && e.target !== menuToggle) {
                closeSidebar();
            }
        }
    });
}

function initSearch() {
    const searchInput = document.querySelector('.sidebar-search input');

    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                if (this.value.trim().length >= 2) {
                    this.form.submit();
                }
            }, 500);
        });

        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && this.value.trim().length >= 2) {
                clearTimeout(timeout);
                this.form.submit();
            }
        });
    }
}

function initSidebarCollapse() {
    const collapseBtn = document.getElementById('sidebar-collapse');
    const sidebar = document.getElementById('sidebar');
    if (!collapseBtn || !sidebar) return;

    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        sidebar.classList.add('collapsed');
        collapseBtn.innerHTML = '&raquo;';
    }

    collapseBtn.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
        this.innerHTML = isCollapsed ? '&raquo;' : '&laquo;';
    });
}

window.addEventListener('pageshow', function(e) {
    if (e.persisted) location.reload();
});

document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.sidebar-search input');
        if (searchInput) {
            searchInput.focus();
        }
    }

    if (e.key === 'Escape') {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    }
});
