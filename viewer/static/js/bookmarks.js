/**
 * Bookmarks page: remove bookmark with undo.
 */
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-action="remove-bookmark"]').forEach(btn => {
        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            const item = this.closest('.bookmark-item');
            const lang = item.dataset.lang;
            const topic = item.dataset.topic;
            const filename = item.dataset.filename;

            const response = await fetch('/api/bookmark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ lang, topic, filename })
            });

            if (response.ok) {
                item.style.opacity = '0';
                setTimeout(() => item.remove(), 300);
            }
        });
    });
});
