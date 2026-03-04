/**
 * Quiz interaction logic
 *
 * Handles multiple question types (vocab, fill_blank, conjugation, mixed),
 * answer submission, feedback display, score tracking, and session completion.
 * Follows the same pattern as practice.js (conjugation drill).
 */
document.addEventListener('DOMContentLoaded', function() {
    var config = window.QUIZ_CONFIG;
    if (!config) return;

    // Accent mappings: base letter -> accented version
    var ACCENT_MAP = {
        'a': '\u00e1',
        'e': '\u00e9',
        'i': '\u00ed',
        'o': '\u00f3',
        'u': '\u00fa',
        'n': '\u00f1',
        'u-diaeresis': '\u00fc'
    };

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // DOM elements
    var quizTypeFilter = document.getElementById('quiz-type-filter');
    var cefrFilter = document.getElementById('cefr-filter');
    var lessonFilter = document.getElementById('lesson-filter');
    var startBtn = document.getElementById('start-quiz-btn');
    var scoreEl = document.getElementById('quiz-score');
    var streakCount = document.getElementById('streak-count');
    var streakIcon = document.getElementById('streak-icon');
    var correctCountEl = document.getElementById('correct-count');
    var totalCountEl = document.getElementById('total-count');
    var loadingEl = document.getElementById('quiz-loading');
    var emptyEl = document.getElementById('quiz-empty');
    var cardEl = document.getElementById('quiz-card');
    var promptEl = document.getElementById('quiz-prompt');
    var hintEl = document.getElementById('quiz-hint');
    var choicesEl = document.getElementById('quiz-choices');
    var fillArea = document.getElementById('quiz-fill-area');
    var answerInput = document.getElementById('quiz-answer-input');
    var submitBtn = document.getElementById('quiz-submit-btn');
    var accentHelpers = document.getElementById('quiz-accent-helpers');
    var feedbackEl = document.getElementById('quiz-feedback');
    var feedbackContent = document.getElementById('quiz-feedback-content');
    var feedbackText = document.getElementById('quiz-feedback-text');
    var feedbackIcon = document.getElementById('quiz-feedback-icon');
    var feedbackExpected = document.getElementById('quiz-feedback-expected');
    var expectedValue = document.getElementById('quiz-expected-value');
    var nextBtn = document.getElementById('quiz-next-btn');
    var completeEl = document.getElementById('quiz-complete');
    var restartBtn = document.getElementById('quiz-restart-btn');

    // Summary elements
    var summaryCorrect = document.getElementById('summary-correct');
    var summaryTotal = document.getElementById('summary-total');
    var summaryAccuracy = document.getElementById('summary-accuracy');
    var summaryStreak = document.getElementById('summary-streak');

    // Session state
    var questions = [];
    var currentIndex = 0;
    var correct = 0;
    var total = 0;
    var streak = 0;
    var bestStreak = 0;
    var isSubmitting = false;
    var feedbackShown = false;
    var currentQuizType = 'mixed';

    // --- Event Listeners ---

    startBtn.addEventListener('click', startQuiz);

    submitBtn.addEventListener('click', submitFillAnswer);

    nextBtn.addEventListener('click', nextQuestion);

    if (restartBtn) {
        restartBtn.addEventListener('click', function() {
            completeEl.style.display = 'none';
            startQuiz();
        });
    }

    // Enter key for fill_blank questions
    answerInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (feedbackShown) {
                nextQuestion();
            } else {
                submitFillAnswer();
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

    // Keyboard shortcuts: 1-4 for multiple choice
    document.addEventListener('keydown', function(e) {
        // Only handle when quiz card is visible and choices are shown
        if (cardEl.style.display === 'none' || choicesEl.style.display === 'none') return;
        if (isSubmitting || feedbackShown) return;

        var keyNum = parseInt(e.key);
        if (keyNum >= 1 && keyNum <= 4) {
            e.preventDefault();
            var buttons = choicesEl.querySelectorAll('.quiz-choice');
            if (buttons.length >= keyNum) {
                buttons[keyNum - 1].click();
            }
        }
    });

    // Enter key advances after feedback on choice questions too
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && feedbackShown && choicesEl.style.display !== 'none') {
            e.preventDefault();
            nextQuestion();
        }
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
     * Start a new quiz session.
     */
    async function startQuiz() {
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
        params.set('lang', config.lang);

        currentQuizType = quizTypeFilter.value;
        params.set('quiz_type', currentQuizType);

        var selectedCefr = cefrFilter.value;
        if (selectedCefr && selectedCefr !== 'all') {
            params.set('cefr', selectedCefr);
        }

        var selectedLesson = lessonFilter.value;
        if (selectedLesson && selectedLesson !== 'all') {
            params.set('lesson', selectedLesson);
        }

        try {
            var response = await fetch('/api/practice/quiz-set?' + params.toString());
            if (!response.ok) {
                throw new Error('Failed to fetch quiz questions');
            }

            var data = await response.json();
            questions = data.questions || [];

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
            console.error('Error fetching quiz questions:', err);
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
        var qType = q.question_type;

        // Reset visibility
        choicesEl.style.display = 'none';
        fillArea.style.display = 'none';
        feedbackEl.style.display = 'none';
        hintEl.style.display = 'none';

        // Set prompt based on question type
        if (qType === 'vocab') {
            promptEl.innerHTML = '<span class="quiz-prompt__label">' +
                (config.lang === 'ko' ? '이 단어의 뜻은?' : 'What does this word mean?') +
                '</span>' +
                '<span class="quiz-prompt__word">' + escapeHtml(q.prompt) + '</span>';
            if (q.hint) {
                hintEl.textContent = q.hint;
                hintEl.style.display = 'block';
            }
            renderChoices(q.choices);
        } else if (qType === 'fill_blank') {
            promptEl.innerHTML = '<span class="quiz-prompt__label">' +
                (config.lang === 'ko' ? '스페인어로 쓰세요:' : 'Write in Spanish:') +
                '</span>' +
                '<span class="quiz-prompt__word">' + escapeHtml(q.prompt) + '</span>';
            if (q.hint) {
                hintEl.textContent = q.hint;
                hintEl.style.display = 'block';
            }
            fillArea.style.display = 'block';
            answerInput.value = '';
            submitBtn.style.display = 'inline-flex';
            submitBtn.disabled = false;
            answerInput.focus();
        } else if (qType === 'conjugation') {
            var p = q.prompt;
            promptEl.innerHTML =
                '<span class="quiz-prompt__label">' +
                (config.lang === 'ko' ? '올바른 활용형을 고르세요' : 'Choose the correct conjugation') +
                '</span>' +
                '<span class="quiz-prompt__word">' + escapeHtml(p.verb) + '</span>' +
                '<span class="quiz-prompt__meaning">' + escapeHtml(p.meaning) + '</span>' +
                '<span class="quiz-prompt__context">' +
                '<span class="quiz-prompt__tense">' + escapeHtml(p.tense) + '</span>' +
                ' &middot; ' +
                '<span class="quiz-prompt__person">' + escapeHtml(p.person) + '</span>' +
                '</span>';
            renderChoices(q.choices);
        }

        cardEl.style.display = 'block';
    }

    /**
     * Render multiple-choice buttons.
     */
    function renderChoices(choices) {
        choicesEl.innerHTML = '';
        choices.forEach(function(choice, idx) {
            var btn = document.createElement('button');
            btn.className = 'quiz-choice';
            btn.type = 'button';
            btn.dataset.key = choice.key;
            btn.innerHTML = '<span class="quiz-choice__number">' + (idx + 1) + '</span>' +
                            '<span class="quiz-choice__text">' + escapeHtml(choice.text) + '</span>';
            btn.addEventListener('click', function() {
                if (isSubmitting || feedbackShown) return;
                submitChoiceAnswer(choice.key, btn);
            });
            choicesEl.appendChild(btn);
        });
        choicesEl.style.display = 'grid';
    }

    /**
     * Submit a multiple-choice answer.
     */
    async function submitChoiceAnswer(selectedKey, selectedBtn) {
        if (isSubmitting || feedbackShown) return;
        isSubmitting = true;

        var q = questions[currentIndex];

        // Visually highlight selected
        selectedBtn.classList.add('quiz-choice--selected');

        try {
            var response = await fetch('/api/practice/quiz-answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    question_type: q.question_type,
                    answer: selectedKey,
                    answer_key: q.answer_key
                })
            });

            if (!response.ok) {
                throw new Error('Failed to check answer');
            }

            var data = await response.json();
            total++;

            // Mark correct/incorrect on buttons
            var buttons = choicesEl.querySelectorAll('.quiz-choice');
            buttons.forEach(function(btn) {
                btn.disabled = true;
                if (btn.dataset.key === 'correct') {
                    btn.classList.add('quiz-choice--correct');
                }
                if (btn.dataset.key === selectedKey && !data.correct) {
                    btn.classList.add('quiz-choice--incorrect');
                }
            });

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
        }
    }

    /**
     * Submit a fill-in-the-blank answer.
     */
    async function submitFillAnswer() {
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
            var response = await fetch('/api/practice/quiz-answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    question_type: q.question_type,
                    answer: answer,
                    answer_key: q.answer_key
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

        // Hide submit button for fill_blank
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
        correctCountEl.textContent = correct;
        totalCountEl.textContent = total;
        streakCount.textContent = streak;

        if (streak >= 3) {
            streakIcon.classList.add('active');
        } else {
            streakIcon.classList.remove('active');
        }
    }

    /**
     * Show session completion summary and save results.
     */
    async function showComplete() {
        cardEl.style.display = 'none';
        feedbackEl.style.display = 'none';
        scoreEl.style.display = 'none';

        var accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
        summaryCorrect.textContent = correct;
        summaryTotal.textContent = total;
        summaryAccuracy.textContent = accuracy + '%';
        summaryStreak.textContent = bestStreak;

        completeEl.style.display = 'block';

        // Save quiz attempt
        try {
            var selectedCefr = cefrFilter.value;
            var selectedLesson = lessonFilter.value;

            await fetch('/api/practice/quiz-complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    course: config.course,
                    quiz_type: currentQuizType,
                    score: correct,
                    total: total,
                    cefr_filter: (selectedCefr && selectedCefr !== 'all') ? selectedCefr : null,
                    lesson_filter: (selectedLesson && selectedLesson !== 'all') ? selectedLesson : null
                })
            });
        } catch (err) {
            console.error('Error saving quiz attempt:', err);
        }
    }

    /**
     * Escape HTML entities to prevent XSS.
     */
    function escapeHtml(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }
});
