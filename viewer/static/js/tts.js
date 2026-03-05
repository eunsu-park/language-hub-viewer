/**
 * Text-to-Speech utility using Web Speech API.
 * Provides speak() for playing pronunciation in the current course language.
 * The locale is read from window.COURSE_LANG (set by base.html), defaulting to 'es-ES'.
 */
(function() {
    'use strict';

    // Check browser support
    var supported = 'speechSynthesis' in window;

    /**
     * Speak text using Web Speech API in the course target language.
     * @param {string} text - The text to speak
     * @param {number} rate - Speech rate (0.1 to 2.0, default 0.85)
     */
    function speak(text, rate) {
        if (!supported || !text) return;
        // Cancel any ongoing speech
        speechSynthesis.cancel();

        var locale = window.COURSE_LANG || 'es-ES';
        var langPrefix = locale.split('-')[0]; // "es-ES" -> "es", "de-DE" -> "de"

        var utterance = new SpeechSynthesisUtterance(text.trim());
        utterance.lang = locale;
        utterance.rate = rate || 0.85;
        utterance.pitch = 1.0;

        // Try to find a voice matching the locale
        var voices = speechSynthesis.getVoices();
        var voice = voices.find(function(v) { return v.lang.startsWith(langPrefix); });
        if (voice) utterance.voice = voice;

        speechSynthesis.speak(utterance);
    }

    /**
     * Check if TTS is supported.
     */
    function isTtsSupported() {
        return supported;
    }

    // Export globally
    window.TTS = {
        speak: speak,
        isSupported: isTtsSupported
    };

    // Preload voices (Chrome requires this)
    if (supported) {
        speechSynthesis.getVoices();
        speechSynthesis.onvoiceschanged = function() {
            speechSynthesis.getVoices();
        };
    }
})();
