/**
 * Conjugation drill interaction
 *
 * Fetches drill questions from the API, handles answer submission,
 * feedback display, score tracking, and accent input helpers.
 */
document.addEventListener('DOMContentLoaded', function() {
    const config = window.DRILL_CONFIG;
    if (!config) return;

    // Accent mappings: base letter -> accented version
    const ACCENT_MAP = {
        'a': '\u00e1',  // a
        'e': '\u00e9',  // e
        'i': '\u00ed',  // i
        'o': '\u00f3',  // o
        'u': '\u00fa',  // u
        'n': '\u00f1',  // n
        'u-diaeresis': '\u00fc'  // u
    };

    // DOM elements
    const verbFilter = document.getElementById('verb-filter');
    const tenseFilter = document.getElementById('tense-filter');
    const startBtn = document.getElementById('start-drill-btn');
    const scoreEl = document.getElementById('drill-score');
    const streakCount = document.getElementById('streak-count');
    const streakIcon = document.getElementById('streak-icon');
    const correctCount = document.getElementById('correct-count');
    const totalCount = document.getElementById('total-count');
    const loadingEl = document.getElementById('drill-loading');
    const emptyEl = document.getElementById('drill-empty');
    const cardEl = document.getElementById('drill-card');
    const feedbackEl = document.getElementById('drill-feedback');
    const feedbackContent = document.getElementById('drill-feedback-content');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackIcon = document.getElementById('feedback-icon');
    const feedbackExpected = document.getElementById('feedback-expected');
    const expectedValue = document.getElementById('expected-value');
    const completeEl = document.getElementById('drill-complete');
    const answerInput = document.getElementById('drill-answer');
    const submitBtn = document.getElementById('drill-submit-btn');
    const nextBtn = document.getElementById('drill-next-btn');
    const restartBtn = document.getElementById('drill-restart-btn');
    const infinitiveEl = document.getElementById('drill-infinitive');
    const meaningEl = document.getElementById('drill-meaning');
    const tenseEl = document.getElementById('drill-tense');
    const personEl = document.getElementById('drill-person');
    const accentHelpers = document.getElementById('accent-helpers');

    // Summary elements
    const summaryCorrect = document.getElementById('summary-correct');
    const summaryTotal = document.getElementById('summary-total');
    const summaryAccuracy = document.getElementById('summary-accuracy');
    const summaryStreak = document.getElementById('summary-streak');

    // Session state
    let questions = [];
    let currentIndex = 0;
    let correct = 0;
    let total = 0;
    let streak = 0;
    let bestStreak = 0;
    let isSubmitting = false;
    let feedbackShown = false;

    // Pre-select verb filter from URL params
    var urlParams = new URLSearchParams(window.location.search);
    var verbParam = urlParams.get('verb');
    if (verbParam && verbFilter) {
        for (var i = 0; i < verbFilter.options.length; i++) {
            if (verbFilter.options[i].value === verbParam) {
                verbFilter.selectedIndex = i;
                break;
            }
        }
    }

    // --- Event Listeners ---

    startBtn.addEventListener('click', startDrill);

    submitBtn.addEventListener('click', submitAnswer);

    nextBtn.addEventListener('click', nextQuestion);

    if (restartBtn) {
        restartBtn.addEventListener('click', function() {
            completeEl.style.display = 'none';
            startDrill();
        });
    }

    // Enter key to submit or advance
    answerInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (feedbackShown) {
                nextQuestion();
            } else {
                submitAnswer();
            }
        }
    });

    // Accent helper buttons
    accentHelpers.addEventListener('click', function(e) {
        var btn = e.target.closest('.accent-btn');
        if (!btn) return;
        e.preventDefault();

        var charKey = btn.dataset.char;
        var accentChar = ACCENT_MAP[charKey];
        if (!accentChar) return;

        insertAtCursor(answerInput, accentChar);
        answerInput.focus();
    });

    /**
     * Insert a character at the current cursor position in an input.
     */
    function insertAtCursor(input, char) {
        var start = input.selectionStart;
        var end = input.selectionEnd;
        var value = input.value;
        input.value = value.substring(0, start) + char + value.substring(end);
        input.selectionStart = input.selectionEnd = start + char.length;
    }

    /**
     * Start a new drill session by fetching questions from the API.
     */
    async function startDrill() {
        // Reset state
        questions = [];
        currentIndex = 0;
        correct = 0;
        total = 0;
        streak = 0;
        bestStreak = 0;
        isSubmitting = false;
        feedbackShown = false;

        // Hide everything, show loading
        cardEl.style.display = 'none';
        feedbackEl.style.display = 'none';
        emptyEl.style.display = 'none';
        completeEl.style.display = 'none';
        scoreEl.style.display = 'none';
        loadingEl.style.display = 'flex';

        // Build query params
        var params = new URLSearchParams();
        params.set('course', config.course);

        var selectedVerb = verbFilter.value;
        if (selectedVerb && selectedVerb !== 'all') {
            params.set('verb', selectedVerb);
        }

        var selectedTense = tenseFilter.value;
        if (selectedTense && selectedTense !== 'all') {
            params.set('tense', selectedTense);
        }

        try {
            var response = await fetch('/api/practice/drill-set?' + params.toString());
            if (!response.ok) {
                throw new Error('Failed to fetch drill questions');
            }

            var data = await response.json();
            questions = data.items || [];

            loadingEl.style.display = 'none';

            if (questions.length === 0) {
                emptyEl.style.display = 'block';
                return;
            }

            // Show score and first question
            updateScoreDisplay();
            scoreEl.style.display = 'flex';
            showQuestion(0);
        } catch (err) {
            console.error('Error fetching drill questions:', err);
            loadingEl.style.display = 'none';
            emptyEl.style.display = 'block';
        }
    }

    /**
     * Display the question at the given index.
     */
    function showQuestion(index) {
        if (index >= questions.length) {
            showComplete();
            return;
        }

        currentIndex = index;
        feedbackShown = false;
        isSubmitting = false;

        var q = questions[currentIndex];

        infinitiveEl.textContent = q.verb || '';
        meaningEl.textContent = q.meaning_text || '';
        tenseEl.textContent = q.tense || '';
        personEl.textContent = q.person || '';

        // Clear input and show card
        answerInput.value = '';
        feedbackEl.style.display = 'none';
        cardEl.style.display = 'block';
        submitBtn.style.display = 'inline-flex';

        // Focus input
        answerInput.focus();
    }

    /**
     * Submit the current answer to the API for checking.
     */
    async function submitAnswer() {
        if (isSubmitting || feedbackShown) return;

        var answer = answerInput.value.trim();
        if (!answer) {
            answerInput.focus();
            return;
        }

        isSubmitting = true;
        submitBtn.disabled = true;

        var q = questions[currentIndex];

        try {
            var response = await fetch('/api/practice/conjugation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    course: config.course,
                    verb: q.verb,
                    tense: q.tense,
                    person: q.person,
                    answer: answer
                })
            });

            if (!response.ok) {
                throw new Error('Failed to check answer');
            }

            var data = await response.json();
            total++;

            if (data.correct) {
                correct++;
                streak++;
                if (streak > bestStreak) {
                    bestStreak = streak;
                }
                showFeedback(true, null);
            } else {
                streak = 0;
                showFeedback(false, data.expected || '');
            }

            updateScoreDisplay();
        } catch (err) {
            console.error('Error checking answer:', err);
            isSubmitting = false;
            submitBtn.disabled = false;
        }
    }

    /**
     * Show feedback for the current answer.
     */
    function showFeedback(isCorrect, expected) {
        feedbackShown = true;
        submitBtn.style.display = 'none';

        if (isCorrect) {
            feedbackContent.className = 'drill-feedback__content drill-feedback__content--correct';
            feedbackIcon.textContent = '\u2713';
            feedbackText.textContent = config.lang === 'ko' ? '\uc815\ub2f5!' : 'Correct!';
            feedbackExpected.style.display = 'none';
        } else {
            feedbackContent.className = 'drill-feedback__content drill-feedback__content--incorrect';
            feedbackIcon.textContent = '\u2717';
            feedbackText.textContent = config.lang === 'ko' ? '\uc624\ub2f5' : 'Incorrect';
            expectedValue.textContent = expected;
            feedbackExpected.style.display = 'block';
        }

        feedbackEl.style.display = 'block';

        // Auto-advance after correct answer
        if (isCorrect) {
            setTimeout(function() {
                if (feedbackShown) {
                    nextQuestion();
                }
            }, 1200);
        }
    }

    /**
     * Advance to the next question.
     */
    function nextQuestion() {
        feedbackShown = false;
        isSubmitting = false;
        submitBtn.disabled = false;
        feedbackEl.style.display = 'none';
        showQuestion(currentIndex + 1);
    }

    /**
     * Update the score display.
     */
    function updateScoreDisplay() {
        correctCount.textContent = correct;
        totalCount.textContent = total;
        streakCount.textContent = streak;

        // Animate streak icon when active
        if (streak >= 3) {
            streakIcon.classList.add('active');
        } else {
            streakIcon.classList.remove('active');
        }
    }

    /**
     * Show the session completion summary.
     */
    function showComplete() {
        cardEl.style.display = 'none';
        feedbackEl.style.display = 'none';
        scoreEl.style.display = 'none';

        var accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
        summaryCorrect.textContent = correct;
        summaryTotal.textContent = total;
        summaryAccuracy.textContent = accuracy + '%';
        summaryStreak.textContent = bestStreak;

        completeEl.style.display = 'block';
    }
});
