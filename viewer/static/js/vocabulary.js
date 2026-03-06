/**
 * Vocabulary list with API-driven pagination and server-side filtering.
 *
 * Fetches words from /api/vocabulary with pagination, renders table rows
 * dynamically, and passes current filters to the flashcard study page.
 */
document.addEventListener('DOMContentLoaded', function() {
    var config = window.VOCAB_CONFIG;
    if (!config) return;

    // DOM elements
    var cefrButtons = document.querySelectorAll('.cefr-filter-btn');
    var lessonSelect = document.getElementById('lesson-filter');
    var searchInput = document.getElementById('vocab-search-input');
    var showingCount = document.getElementById('showing-count');
    var vocabTbody = document.getElementById('vocab-tbody');
    var vocabEmpty = document.getElementById('vocab-empty');
    var vocabTable = document.querySelector('.vocab-table-wrap');
    var studyBtn = document.getElementById('study-flashcards-btn');
    var pagination = document.getElementById('vocab-pagination');
    var pageInfo = document.getElementById('page-info');
    var prevBtn = document.getElementById('page-prev');
    var nextBtn = document.getElementById('page-next');
    var loadingEl = document.getElementById('vocab-loading');

    // State
    var activeCefr = 'all';
    var activeLesson = 'all';
    var searchQuery = '';
    var currentPage = 1;
    var totalPages = 1;
    var totalFiltered = 0;
    var loading = false;

    // Set initial state from active buttons / select
    cefrButtons.forEach(function(btn) {
        if (btn.classList.contains('active') && btn.dataset.level !== 'all') {
            activeCefr = btn.dataset.level;
        }
    });
    if (lessonSelect && lessonSelect.value !== 'all') {
        activeLesson = lessonSelect.value;
    }
    if (searchInput && searchInput.value.trim()) {
        searchQuery = searchInput.value.trim();
    }

    // --- CEFR Filter ---
    cefrButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            cefrButtons.forEach(function(b) { b.classList.remove('active'); });
            this.classList.add('active');
            activeCefr = this.dataset.level;
            currentPage = 1;
            fetchWords();
        });
    });

    // --- Lesson Filter ---
    if (lessonSelect) {
        lessonSelect.addEventListener('change', function() {
            activeLesson = this.value;
            currentPage = 1;
            fetchWords();
        });
    }

    // --- Search Filter ---
    if (searchInput) {
        var debounceTimer;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                searchQuery = searchInput.value.trim();
                currentPage = 1;
                fetchWords();
            }, 300);
        });
    }

    // --- Pagination ---
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            if (currentPage > 1) {
                currentPage--;
                fetchWords();
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            if (currentPage < totalPages) {
                currentPage++;
                fetchWords();
            }
        });
    }

    /**
     * Fetch words from the API and render the table.
     */
    function fetchWords() {
        if (loading) return;
        loading = true;
        showLoading(true);

        var params = new URLSearchParams();
        params.set('course', config.course);
        params.set('lang', config.lang);
        params.set('page', currentPage);
        params.set('per_page', config.perPage);
        if (activeCefr !== 'all') params.set('cefr', activeCefr);
        if (activeLesson !== 'all') params.set('lesson', activeLesson);
        if (searchQuery) params.set('q', searchQuery);

        fetch(config.apiUrl + '?' + params.toString())
            .then(function(res) { return res.json(); })
            .then(function(data) {
                totalFiltered = data.total;
                totalPages = data.total_pages;
                currentPage = data.page;
                renderWords(data.words);
                updateUI();
                loading = false;
                showLoading(false);
            })
            .catch(function() {
                loading = false;
                showLoading(false);
            });
    }

    /**
     * Render word rows into the table body.
     */
    function renderWords(words) {
        vocabTbody.innerHTML = '';
        var frag = document.createDocumentFragment();

        for (var i = 0; i < words.length; i++) {
            var w = words[i];
            var tr = document.createElement('tr');
            tr.className = 'vocab-row';

            // Word cell with TTS button
            var tdWord = document.createElement('td');
            tdWord.className = 'vocab-row__word';
            tdWord.textContent = w.target || '';
            var ttsBtn = document.createElement('button');
            ttsBtn.className = 'tts-btn';
            ttsBtn.type = 'button';
            ttsBtn.setAttribute('data-text', w.target || '');
            ttsBtn.innerHTML = config.speakerSvg;
            ttsBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                if (window.TTS) TTS.speak(this.dataset.text);
            });
            tdWord.appendChild(ttsBtn);
            tr.appendChild(tdWord);

            // Translation
            var tdTrans = document.createElement('td');
            tdTrans.className = 'vocab-row__translation';
            tdTrans.textContent = w.translation || '';
            tr.appendChild(tdTrans);

            // Gender
            var tdGender = document.createElement('td');
            tdGender.className = 'vocab-row__gender';
            if (w.gender) {
                var badge = document.createElement('span');
                badge.className = 'gender-badge gender-badge--' + w.gender;
                badge.textContent = w.gender;
                tdGender.appendChild(badge);
            }
            tr.appendChild(tdGender);

            // CEFR/Level
            var tdCefr = document.createElement('td');
            tdCefr.className = 'vocab-row__cefr';
            if (w.cefr) {
                var cefrBadge = document.createElement('span');
                cefrBadge.className = 'cefr-badge cefr-badge--' + w.cefr.toLowerCase();
                cefrBadge.textContent = w.cefr;
                tdCefr.appendChild(cefrBadge);
            }
            tr.appendChild(tdCefr);

            // Lesson
            var tdLesson = document.createElement('td');
            tdLesson.className = 'vocab-row__lesson';
            tdLesson.textContent = w.lesson || '';
            tr.appendChild(tdLesson);

            frag.appendChild(tr);
        }
        vocabTbody.appendChild(frag);
    }

    /**
     * Update pagination controls, counts, empty state, and study link.
     */
    function updateUI() {
        // Count
        showingCount.textContent = totalFiltered;

        // Empty state
        if (totalFiltered === 0) {
            vocabEmpty.style.display = 'block';
            vocabTable.style.display = 'none';
            pagination.style.display = 'none';
        } else {
            vocabEmpty.style.display = 'none';
            vocabTable.style.display = '';

            // Pagination
            if (totalPages > 1) {
                pagination.style.display = 'flex';
                pageInfo.textContent = currentPage + ' / ' + totalPages;
                prevBtn.disabled = currentPage <= 1;
                nextBtn.disabled = currentPage >= totalPages;
            } else {
                pagination.style.display = 'none';
            }
        }

        // Flashcard study link
        updateStudyLink();
    }

    function updateStudyLink() {
        if (!studyBtn) return;
        var params = new URLSearchParams();
        if (activeCefr !== 'all') params.set('cefr', activeCefr);
        if (activeLesson !== 'all') params.set('lesson', activeLesson);
        if (searchQuery) params.set('q', searchQuery);
        var qs = params.toString();
        studyBtn.href = qs ? config.flashcardUrl + '?' + qs : config.flashcardUrl;
    }

    function showLoading(show) {
        if (loadingEl) loadingEl.style.display = show ? 'block' : 'none';
    }

    // --- Row click highlight ---
    vocabTbody.addEventListener('click', function(e) {
        var row = e.target.closest('.vocab-row');
        if (!row || e.target.closest('.tts-btn')) return;
        var prev = vocabTbody.querySelector('.vocab-row--active');
        if (prev && prev !== row) prev.classList.remove('vocab-row--active');
        row.classList.toggle('vocab-row--active');
    });

    // Initial load
    fetchWords();
});
