/**
 * Dashboard: animated progress bars, CEFR section toggling, clear data.
 */
document.addEventListener('DOMContentLoaded', function () {
    // --- Animated progress bars ---
    // All progress-fill elements with data-target-width get animated on load
    const fills = document.querySelectorAll('.progress-fill[data-target-width]');
    if (fills.length) {
        // Use requestAnimationFrame to ensure the initial 0% is painted first
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                fills.forEach(function (fill) {
                    var target = fill.getAttribute('data-target-width');
                    fill.style.width = target + '%';
                });
            });
        });
    }

    // --- CEFR card click to toggle highlight ---
    var cefrCards = document.querySelectorAll('.dashboard-cefr-card');
    cefrCards.forEach(function (card) {
        card.style.cursor = 'pointer';
        card.addEventListener('click', function () {
            // Toggle an "active" visual state
            var isActive = card.classList.toggle('dashboard-cefr-card--active');
            var badge = card.querySelector('.dashboard-cefr-card__badge');
            if (isActive && badge) {
                card.style.borderColor = badge.style.background || 'var(--accent-color)';
            } else {
                card.style.borderColor = '';
            }
        });
    });

    // --- Clear data button ---
    var clearBtn = document.getElementById('clear-data-btn');
    if (!clearBtn) return;

    clearBtn.addEventListener('click', async function () {
        var lang = document.documentElement.lang || 'en';
        var message = lang === 'ko'
            ? '모든 진행 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.'
            : 'Are you sure you want to delete all progress data? This cannot be undone.';

        if (!confirm(message)) return;

        var response = await fetch('/api/clear-user-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
        });

        if (response.ok) {
            location.reload();
        }
    });
});
