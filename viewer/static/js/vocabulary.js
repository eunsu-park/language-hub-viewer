/**
 * Vocabulary list filtering and interaction
 *
 * Client-side filtering by CEFR level, lesson number, and search text.
 * Updates the visible word count and passes current filters to the
 * flashcard study page.
 */
document.addEventListener('DOMContentLoaded', function() {
    const config = window.VOCAB_CONFIG;
    if (!config) return;

    // DOM elements
    const cefrButtons = document.querySelectorAll('.cefr-filter-btn');
    const lessonSelect = document.getElementById('lesson-filter');
    const searchInput = document.getElementById('vocab-search-input');
    const showingCount = document.getElementById('showing-count');
    const vocabTbody = document.getElementById('vocab-tbody');
    const vocabEmpty = document.getElementById('vocab-empty');
    const vocabTable = document.querySelector('.vocab-table-wrap');
    const studyBtn = document.getElementById('study-flashcards-btn');

    // Current filter state
    let activeCefr = 'all';
    let activeLesson = 'all';
    let searchQuery = '';

    // Set initial state from active buttons
    cefrButtons.forEach(function(btn) {
        if (btn.classList.contains('active') && btn.dataset.level !== 'all') {
            activeCefr = btn.dataset.level;
        }
    });
    if (lessonSelect && lessonSelect.value !== 'all') {
        activeLesson = lessonSelect.value;
    }

    // --- CEFR Filter ---
    cefrButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            cefrButtons.forEach(function(b) { b.classList.remove('active'); });
            this.classList.add('active');
            activeCefr = this.dataset.level;
            applyFilters();
        });
    });

    // --- Lesson Filter ---
    if (lessonSelect) {
        lessonSelect.addEventListener('change', function() {
            activeLesson = this.value;
            applyFilters();
        });
    }

    // --- Search Filter ---
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                searchQuery = searchInput.value.trim().toLowerCase();
                applyFilters();
            }, 200);
        });
    }

    /**
     * Apply all active filters to the vocabulary table rows.
     */
    function applyFilters() {
        const rows = vocabTbody.querySelectorAll('.vocab-row');
        let visibleCount = 0;

        rows.forEach(function(row) {
            let show = true;

            // CEFR filter
            if (activeCefr !== 'all') {
                if (row.dataset.cefr !== activeCefr) {
                    show = false;
                }
            }

            // Lesson filter
            if (show && activeLesson !== 'all') {
                if (row.dataset.lesson !== activeLesson) {
                    show = false;
                }
            }

            // Search filter
            if (show && searchQuery) {
                const word = (row.dataset.word || '').toLowerCase();
                const translation = (row.dataset.translation || '').toLowerCase();
                if (word.indexOf(searchQuery) === -1 && translation.indexOf(searchQuery) === -1) {
                    show = false;
                }
            }

            row.style.display = show ? '' : 'none';
            if (show) visibleCount++;
        });

        // Update count
        showingCount.textContent = visibleCount;

        // Toggle empty state
        if (visibleCount === 0) {
            vocabEmpty.style.display = 'block';
            vocabTable.style.display = 'none';
        } else {
            vocabEmpty.style.display = 'none';
            vocabTable.style.display = '';
        }

        // Update study button URL with current filters
        updateStudyLink();
    }

    /**
     * Update the "Study Flashcards" link to pass current filters as query params.
     */
    function updateStudyLink() {
        if (!studyBtn) return;

        const params = new URLSearchParams();
        if (activeCefr !== 'all') {
            params.set('cefr', activeCefr);
        }
        if (activeLesson !== 'all') {
            params.set('lesson', activeLesson);
        }
        if (searchQuery) {
            params.set('q', searchQuery);
        }

        const base = config.flashcardUrl;
        const qs = params.toString();
        studyBtn.href = qs ? base + '?' + qs : base;
    }

    // --- Row click highlight ---
    if (vocabTbody) {
        vocabTbody.addEventListener('click', function(e) {
            const row = e.target.closest('.vocab-row');
            if (!row) return;

            // Remove previous highlight
            const prev = vocabTbody.querySelector('.vocab-row--active');
            if (prev && prev !== row) {
                prev.classList.remove('vocab-row--active');
            }

            // Toggle current
            row.classList.toggle('vocab-row--active');
        });
    }
});
