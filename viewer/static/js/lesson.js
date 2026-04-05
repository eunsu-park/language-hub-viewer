/**
 * Lesson page interactivity: mark-read, bookmark, copy, code blocks, scroll-to-top, keyboard nav.
 */
document.addEventListener('DOMContentLoaded', function() {
    const article = document.querySelector('.lesson-article');
    if (!article) return;

    const lang = article.dataset.lang;
    const topic = article.dataset.topic;
    const filename = article.dataset.filename;

    document.querySelectorAll('[data-action="mark-read"]').forEach(btn => {
        btn.addEventListener('click', async function() {
            const isRead = !this.classList.contains('active');
            const response = await fetch('/api/mark-read', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ lang, topic, filename, is_read: isRead })
            });
            if (response.ok) {
                document.querySelectorAll('[data-action="mark-read"]').forEach(b => {
                    b.classList.toggle('active', isRead);
                    b.setAttribute('aria-pressed', isRead);
                    b.querySelector('.text').textContent = isRead ? 'Read' : 'Mark as read';
                });
            }
        });
    });

    document.querySelectorAll('[data-action="bookmark"]').forEach(btn => {
        btn.addEventListener('click', async function() {
            const response = await fetch('/api/bookmark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ lang, topic, filename })
            });
            if (response.ok) {
                const data = await response.json();
                document.querySelectorAll('[data-action="bookmark"]').forEach(b => {
                    b.classList.toggle('active', data.bookmarked);
                    b.setAttribute('aria-pressed', data.bookmarked);
                    b.querySelector('.text').textContent = data.bookmarked ? 'Bookmarked' : 'Bookmark';
                });
            }
        });
    });

    document.querySelectorAll('[data-action="copy-link"]').forEach(btn => {
        btn.addEventListener('click', function() {
            navigator.clipboard.writeText(window.location.href);
            const textEl = this.querySelector('.text');
            const originalText = textEl.textContent;
            textEl.textContent = 'Copied!';
            setTimeout(() => { textEl.textContent = originalText; }, 2000);
        });
    });

    document.querySelectorAll('pre code').forEach((block) => {
        const pre = block.parentNode;
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'code-copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(block.textContent);
            copyBtn.textContent = 'Copied!';
            setTimeout(() => copyBtn.textContent = 'Copy', 2000);
        });
        wrapper.appendChild(copyBtn);
    });

    const scrollBtn = document.getElementById('scroll-to-top');
    if (scrollBtn) {
        window.addEventListener('scroll', function() {
            scrollBtn.classList.toggle('visible', window.scrollY > 300);
        });
        scrollBtn.addEventListener('click', function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // Reading position memory (localStorage)
    (function initReadingPosition() {
        var key = 'reading-pos:' + topic + '/' + filename;
        var saved = localStorage.getItem(key);

        if (saved) {
            var pos = JSON.parse(saved);
            if (pos.scrollY > 100) {
                requestAnimationFrame(function() {
                    window.scrollTo(0, pos.scrollY);
                });
            }
        }

        var saveTimer = null;
        window.addEventListener('scroll', function() {
            if (saveTimer) clearTimeout(saveTimer);
            saveTimer = setTimeout(function() {
                localStorage.setItem(key, JSON.stringify({
                    scrollY: window.scrollY,
                    ts: Date.now()
                }));
            }, 300);
        });

        try {
            var posKeys = [];
            for (var i = 0; i < localStorage.length; i++) {
                var k = localStorage.key(i);
                if (k && k.startsWith('reading-pos:')) posKeys.push(k);
            }
            if (posKeys.length > 100) {
                var entries = posKeys.map(function(k) {
                    var v = JSON.parse(localStorage.getItem(k) || '{}');
                    return { key: k, ts: v.ts || 0 };
                }).sort(function(a, b) { return a.ts - b.ts; });
                entries.slice(0, entries.length - 100).forEach(function(e) {
                    localStorage.removeItem(e.key);
                });
            }
        } catch(_) {}
    })();

    // Floating TOC with scroll-spy
    (function initFloatingToc() {
        var tocNav = document.getElementById('floating-toc');
        var content = document.querySelector('.lesson-content');
        if (!tocNav || !content) return;

        var headings = content.querySelectorAll('h2, h3');
        if (headings.length < 2) return;

        headings.forEach(function(h, i) {
            if (!h.id) h.id = 'heading-' + i;
        });

        var html = '<div class="ftoc-title">On this page</div><ul>';
        headings.forEach(function(h) {
            var level = h.tagName === 'H3' ? ' class="ftoc-h3"' : '';
            html += '<li' + level + '><a href="#' + h.id + '">' + h.textContent + '</a></li>';
        });
        html += '</ul>';
        tocNav.innerHTML = html;

        var links = tocNav.querySelectorAll('a');
        var activeIndex = 0;

        function setActive(index) {
            if (index === activeIndex && links[index].classList.contains('active')) return;
            links.forEach(function(a) { a.classList.remove('active'); });
            if (links[index]) {
                links[index].classList.add('active');
                activeIndex = index;
                links[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        }

        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var idx = Array.prototype.indexOf.call(headings, entry.target);
                    if (idx !== -1) setActive(idx);
                }
            });
        }, {
            rootMargin: '-80px 0px -70% 0px',
            threshold: 0
        });

        headings.forEach(function(h) { observer.observe(h); });

        tocNav.addEventListener('click', function(e) {
            var link = e.target.closest('a');
            if (!link) return;
            e.preventDefault();
            var target = document.getElementById(link.getAttribute('href').slice(1));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });

        setActive(0);
    })();

    document.addEventListener('keydown', function(e) {
        const tag = document.activeElement.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

        if (e.key === 'ArrowLeft') {
            const prevLink = document.querySelector('.nav-prev');
            if (prevLink) { prevLink.click(); }
        } else if (e.key === 'ArrowRight') {
            const nextLink = document.querySelector('.nav-next');
            if (nextLink) { nextLink.click(); }
        }
    });

    // --- Vocabulary Tooltips ---
    (function initVocabTooltips() {
        var vocabData = window.LESSON_VOCAB;
        if (!vocabData || !vocabData.length) return;

        var contentEl = document.querySelector('.lesson-content');
        if (!contentEl) return;

        // Sort by word length descending to match longer phrases first
        var words = vocabData.slice().sort(function(a, b) {
            return (b.target || '').length - (a.target || '').length;
        });

        // Build regex patterns for each word
        var wordEntries = [];
        words.forEach(function(w) {
            var target = w.target;
            if (!target || target.length < 2) return;
            // Escape regex special characters
            var escaped = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            // Use word boundary that handles accented characters
            var pattern = new RegExp('(?:^|(?<=[\\s,;:.!?()\\[\\]"\']))(' + escaped + ')(?=[\\s,;:.!?()\\[\\]"\']|$)', 'gi');
            wordEntries.push({ word: w, pattern: pattern });
        });

        if (!wordEntries.length) return;

        // Tags to skip when scanning for text nodes
        var SKIP_TAGS = {
            'CODE': true, 'PRE': true, 'SCRIPT': true, 'STYLE': true,
            'H1': true, 'H2': true, 'H3': true, 'H4': true, 'H5': true, 'H6': true,
            'A': true, 'KBD': true
        };

        /**
         * Collect all text nodes under an element, skipping certain tags.
         */
        function getTextNodes(root) {
            var nodes = [];
            var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
                acceptNode: function(node) {
                    var parent = node.parentNode;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    // Skip if already wrapped as tooltip
                    if (parent.classList && parent.classList.contains('vocab-tooltip')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Skip certain parent tags
                    if (SKIP_TAGS[parent.tagName]) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Skip nodes inside code blocks or pre elements
                    var ancestor = parent;
                    while (ancestor && ancestor !== root) {
                        if (SKIP_TAGS[ancestor.tagName]) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        ancestor = ancestor.parentNode;
                    }
                    if (node.nodeValue && node.nodeValue.trim().length > 0) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_REJECT;
                }
            });
            while (walker.nextNode()) {
                nodes.push(walker.currentNode);
            }
            return nodes;
        }

        /**
         * Wrap matching text in a text node with tooltip span.
         * Returns true if any replacement was made.
         */
        function wrapMatches(textNode, entry) {
            var text = textNode.nodeValue;
            var pattern = entry.pattern;
            var w = entry.word;
            pattern.lastIndex = 0;
            var match = pattern.exec(text);
            if (!match) return false;

            var before = text.substring(0, match.index);
            var matched = match[0];
            var after = text.substring(match.index + matched.length);

            var parent = textNode.parentNode;

            // Create text node for the part before the match
            if (before) {
                parent.insertBefore(document.createTextNode(before), textNode);
            }

            // Create the tooltip span
            var span = document.createElement('span');
            span.className = 'vocab-tooltip';
            span.textContent = matched;
            span.setAttribute('data-word', w.target || '');
            span.setAttribute('data-translation', w.translation || '');
            span.setAttribute('data-gender', w.gender || '');
            span.setAttribute('data-notes', w.notes || '');
            parent.insertBefore(span, textNode);

            // Update the remaining text
            textNode.nodeValue = after;

            return true;
        }

        // Process: for each word, scan all text nodes and wrap first occurrence
        var matched = {};
        wordEntries.forEach(function(entry) {
            var key = (entry.word.target || '').toLowerCase();
            if (matched[key]) return; // Only mark first occurrence per word

            var textNodes = getTextNodes(contentEl);
            for (var i = 0; i < textNodes.length; i++) {
                if (wrapMatches(textNodes[i], entry)) {
                    matched[key] = true;
                    break;
                }
            }
        });

        // --- Popup handling ---
        var activePopup = null;

        function removePopup() {
            if (activePopup) {
                activePopup.remove();
                activePopup = null;
            }
        }

        function createPopup(tooltipSpan) {
            removePopup();

            var word = tooltipSpan.getAttribute('data-word');
            var translation = tooltipSpan.getAttribute('data-translation');
            var gender = tooltipSpan.getAttribute('data-gender');
            var notes = tooltipSpan.getAttribute('data-notes');

            var popup = document.createElement('div');
            popup.className = 'vocab-popup';

            // Word line with TTS button
            var wordLine = document.createElement('div');
            wordLine.className = 'vocab-popup__word';
            wordLine.textContent = word;

            if (window.TTS && TTS.isSupported()) {
                var ttsBtn = document.createElement('button');
                ttsBtn.className = 'vocab-popup__tts';
                ttsBtn.type = 'button';
                ttsBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>';
                ttsBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    TTS.speak(word);
                });
                wordLine.appendChild(document.createTextNode(' '));
                wordLine.appendChild(ttsBtn);
            }
            popup.appendChild(wordLine);

            // Translation
            if (translation) {
                var transEl = document.createElement('div');
                transEl.className = 'vocab-popup__translation';
                transEl.textContent = translation;
                popup.appendChild(transEl);
            }

            // Gender badge
            if (gender) {
                var genderEl = document.createElement('span');
                genderEl.className = 'vocab-popup__gender gender-badge gender-badge--' + gender;
                genderEl.textContent = gender;
                popup.appendChild(genderEl);
            }

            // Notes
            if (notes) {
                var notesEl = document.createElement('div');
                notesEl.className = 'vocab-popup__notes';
                notesEl.textContent = notes;
                popup.appendChild(notesEl);
            }

            tooltipSpan.appendChild(popup);
            activePopup = popup;

            // Reposition if popup overflows viewport
            requestAnimationFrame(function() {
                var rect = popup.getBoundingClientRect();
                if (rect.top < 0) {
                    popup.style.bottom = 'auto';
                    popup.style.top = 'calc(100% + 8px)';
                }
                if (rect.left < 0) {
                    popup.style.left = '0';
                    popup.style.transform = 'none';
                } else if (rect.right > window.innerWidth) {
                    popup.style.left = 'auto';
                    popup.style.right = '0';
                    popup.style.transform = 'none';
                }
            });
        }

        // Click handler for tooltip spans
        contentEl.addEventListener('click', function(e) {
            var tooltip = e.target.closest('.vocab-tooltip');
            if (tooltip) {
                e.preventDefault();
                e.stopPropagation();
                // Toggle: if clicking same tooltip, close it
                if (activePopup && activePopup.parentNode === tooltip) {
                    removePopup();
                } else {
                    createPopup(tooltip);
                }
                return;
            }
            // Click outside popup: dismiss
            if (activePopup && !e.target.closest('.vocab-popup')) {
                removePopup();
            }
        });

        // Dismiss popup on click outside content area
        document.addEventListener('click', function(e) {
            if (activePopup && !e.target.closest('.lesson-content')) {
                removePopup();
            }
        });

        // Dismiss on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && activePopup) {
                removePopup();
            }
        });
    })();
});
