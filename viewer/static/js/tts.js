/**
 * Text-to-Speech utility using Web Speech API.
 * Provides speakSpanish() for playing Spanish pronunciation.
 */
(function() {
    'use strict';

    // Check browser support
    var supported = 'speechSynthesis' in window;

    /**
     * Speak text in Spanish using Web Speech API.
     * @param {string} text - The Spanish text to speak
     * @param {number} rate - Speech rate (0.1 to 2.0, default 0.85)
     */
    function speakSpanish(text, rate) {
        if (!supported || !text) return;
        // Cancel any ongoing speech
        speechSynthesis.cancel();
        var utterance = new SpeechSynthesisUtterance(text.trim());
        utterance.lang = 'es-ES';
        utterance.rate = rate || 0.85;
        utterance.pitch = 1.0;
        // Try to find a Spanish voice
        var voices = speechSynthesis.getVoices();
        var spanishVoice = voices.find(function(v) { return v.lang.startsWith('es'); });
        if (spanishVoice) utterance.voice = spanishVoice;
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
        speak: speakSpanish,
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
