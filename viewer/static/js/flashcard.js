/**
 * Flashcard study session
 *
 * Loads cards from the API, handles card flipping, grading,
 * and session progress tracking.
 */
document.addEventListener('DOMContentLoaded', function() {
    const config = window.FLASHCARD_CONFIG;
    if (!config) return;

    // DOM elements
    const loadingEl = document.getElementById('flashcard-loading');
    const emptyEl = document.getElementById('flashcard-empty');
    const containerEl = document.getElementById('flashcard-container');
    const completeEl = document.getElementById('session-complete');
    const flashcardEl = document.getElementById('flashcard');
    const flashcardInner = document.getElementById('flashcard-inner');
    const progressFill = document.getElementById('progress-fill');
    const currentCardEl = document.getElementById('current-card');
    const totalCardsEl = document.getElementById('total-cards');
    const accuracyEl = document.getElementById('accuracy');
    const cardWord = document.getElementById('card-word');
    const cardWordBack = document.getElementById('card-word-back');
    const cardGender = document.getElementById('card-gender');
    const cardTranslation = document.getElementById('card-translation');
    const cardLesson = document.getElementById('card-lesson');
    const cardCefr = document.getElementById('card-cefr');
    const gradeButtons = document.getElementById('grade-buttons');
    const restartBtn = document.getElementById('restart-btn');
    const summaryTotal = document.getElementById('summary-total');
    const summaryCorrect = document.getElementById('summary-correct');
    const summaryAccuracy = document.getElementById('summary-accuracy');

    // Session state
    let cards = [];
    let currentIndex = 0;
    let isFlipped = false;
    let correctCount = 0;
    let reviewedCount = 0;
    let isGrading = false;

    // Initialize
    fetchCards();

    /**
     * Fetch session cards from the API.
     */
    async function fetchCards() {
        try {
            const params = new URLSearchParams(window.location.search);
            params.set('course', config.course);
            params.set('lang', config.lang);
            if (config.sessionId) {
                params.set('session_id', config.sessionId);
            }

            const response = await fetch('/api/flashcard/session?' + params.toString());
            if (!response.ok) {
                throw new Error('Failed to fetch cards');
            }

            const data = await response.json();
            cards = data.cards || [];

            loadingEl.style.display = 'none';

            if (cards.length === 0) {
                emptyEl.style.display = 'block';
                return;
            }

            totalCardsEl.textContent = cards.length;
            containerEl.style.display = 'block';
            showCard(0);
        } catch (err) {
            console.error('Error fetching flashcard session:', err);
            loadingEl.style.display = 'none';
            emptyEl.style.display = 'block';
        }
    }

    /**
     * Display the card at the given index.
     */
    function showCard(index) {
        if (index >= cards.length) {
            showComplete();
            return;
        }

        currentIndex = index;
        isFlipped = false;
        isGrading = false;
        flashcardInner.classList.remove('flipped');

        const card = cards[currentIndex];

        // Front
        cardWord.textContent = card.target || card.word || '';

        if (card.gender) {
            cardGender.textContent = card.gender;
            cardGender.className = 'gender-badge gender-badge--' + card.gender;
            cardGender.style.display = 'inline-block';
        } else {
            cardGender.style.display = 'none';
        }

        // Back
        cardWordBack.textContent = card.target || card.word || '';
        cardTranslation.textContent = card.translation || '';

        if (card.lesson) {
            cardLesson.textContent = 'Lesson ' + card.lesson;
        } else {
            cardLesson.textContent = '';
        }

        if (card.cefr) {
            cardCefr.textContent = card.cefr;
        } else {
            cardCefr.textContent = '';
        }

        // Update progress
        currentCardEl.textContent = currentIndex + 1;
        updateProgress();
    }

    /**
     * Flip the card to show the back.
     */
    function flipCard() {
        if (isFlipped || isGrading) return;
        isFlipped = true;
        flashcardInner.classList.add('flipped');
    }

    /**
     * Grade the current card and move to the next.
     */
    async function gradeCard(quality) {
        if (!isFlipped || isGrading) return;
        isGrading = true;

        const card = cards[currentIndex];
        reviewedCount++;

        // Quality 3 (Good) or 4 (Easy) count as correct
        if (quality >= 3) {
            correctCount++;
        }

        // Post grade to API
        try {
            await fetch('/api/flashcard/grade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    course: config.course,
                    word_key: card.word_key || card.target || card.word,
                    quality: quality
                })
            });
        } catch (err) {
            console.error('Error grading card:', err);
        }

        updateProgress();

        // Brief delay before showing next card
        setTimeout(function() {
            showCard(currentIndex + 1);
        }, 200);
    }

    /**
     * Update the progress bar and accuracy display.
     */
    function updateProgress() {
        const total = cards.length;
        const percentage = total > 0 ? Math.round((reviewedCount / total) * 100) : 0;
        progressFill.style.width = percentage + '%';

        const acc = reviewedCount > 0 ? Math.round((correctCount / reviewedCount) * 100) : 0;
        accuracyEl.textContent = acc;
    }

    /**
     * Show the session complete summary.
     */
    function showComplete() {
        containerEl.style.display = 'none';
        completeEl.style.display = 'block';

        const acc = reviewedCount > 0 ? Math.round((correctCount / reviewedCount) * 100) : 0;
        summaryTotal.textContent = reviewedCount;
        summaryCorrect.textContent = correctCount;
        summaryAccuracy.textContent = acc + '%';
    }

    /**
     * Restart the session with shuffled cards.
     */
    function restartSession() {
        currentIndex = 0;
        isFlipped = false;
        isGrading = false;
        correctCount = 0;
        reviewedCount = 0;

        // Shuffle cards
        for (let i = cards.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [cards[i], cards[j]] = [cards[j], cards[i]];
        }

        completeEl.style.display = 'none';
        containerEl.style.display = 'block';
        progressFill.style.width = '0%';
        accuracyEl.textContent = '0';
        showCard(0);
    }

    // --- Event Listeners ---

    // Click to flip
    flashcardEl.addEventListener('click', function(e) {
        // Don't flip if clicking a grade button
        if (e.target.closest('.grade-buttons')) return;
        if (!isFlipped) {
            flipCard();
        }
    });

    // Grade button clicks
    gradeButtons.addEventListener('click', function(e) {
        const btn = e.target.closest('.grade-btn');
        if (!btn) return;
        const quality = parseInt(btn.dataset.quality, 10);
        gradeCard(quality);
    });

    // Restart button
    if (restartBtn) {
        restartBtn.addEventListener('click', restartSession);
    }

    // Keyboard controls
    document.addEventListener('keydown', function(e) {
        // Ignore when typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            return;
        }

        // Space to flip
        if (e.key === ' ' || e.code === 'Space') {
            e.preventDefault();
            if (!isFlipped) {
                flipCard();
            }
            return;
        }

        // Number keys 1-4 to grade
        if (isFlipped && !isGrading) {
            const num = parseInt(e.key, 10);
            if (num >= 1 && num <= 4) {
                e.preventDefault();
                gradeCard(num);
            }
        }
    });
});
