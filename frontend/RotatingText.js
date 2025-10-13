/**
 * RotatingText - Animated text rotation component
 * Vanilla JavaScript implementation inspired by framer-motion
 */

class RotatingText {
    constructor(container, options = {}) {
        this.container = container;
        this.texts = options.texts || [];
        this.rotationInterval = options.rotationInterval || 2000;
        this.staggerDuration = options.staggerDuration || 30;
        this.loop = options.loop !== false;
        this.auto = options.auto !== false;
        this.splitBy = options.splitBy || 'characters';
        this.currentTextIndex = 0;
        this.intervalId = null;

        this.init();
    }

    splitIntoCharacters(text) {
        if (typeof Intl !== 'undefined' && Intl.Segmenter) {
            const segmenter = new Intl.Segmenter('en', { granularity: 'grapheme' });
            return Array.from(segmenter.segment(text), segment => segment.segment);
        }
        return Array.from(text);
    }

    getElements(text) {
        if (this.splitBy === 'characters') {
            const words = text.split(' ');
            return words.map((word, i) => ({
                characters: this.splitIntoCharacters(word),
                needsSpace: i !== words.length - 1
            }));
        }
        if (this.splitBy === 'words') {
            return text.split(' ').map((word, i, arr) => ({
                characters: [word],
                needsSpace: i !== arr.length - 1
            }));
        }
        return [{
            characters: [text],
            needsSpace: false
        }];
    }

    createTextElement(text, direction = 'in') {
        const wrapper = document.createElement('span');
        wrapper.className = 'text-rotate-wrapper';
        wrapper.setAttribute('aria-hidden', 'true');

        const elements = this.getElements(text);
        let charIndex = 0;

        elements.forEach((wordObj, wordIndex) => {
            const wordSpan = document.createElement('span');
            wordSpan.className = 'text-rotate-word';

            wordObj.characters.forEach((char) => {
                const charSpan = document.createElement('span');
                charSpan.className = 'text-rotate-element';
                charSpan.textContent = char;
                charSpan.style.transitionDelay = `${charIndex * this.staggerDuration}ms`;

                if (direction === 'in') {
                    charSpan.classList.add('text-rotate-enter');
                    // Trigger animation
                    setTimeout(() => {
                        charSpan.classList.remove('text-rotate-enter');
                        charSpan.classList.add('text-rotate-active');
                    }, 10);
                } else {
                    charSpan.classList.add('text-rotate-active');
                }

                wordSpan.appendChild(charSpan);
                charIndex++;
            });

            if (wordObj.needsSpace) {
                const space = document.createElement('span');
                space.className = 'text-rotate-space';
                space.textContent = ' ';
                wordSpan.appendChild(space);
            }

            wrapper.appendChild(wordSpan);
        });

        return wrapper;
    }

    animateOut(element, callback) {
        const chars = element.querySelectorAll('.text-rotate-element');
        let completed = 0;

        chars.forEach((char, index) => {
            char.style.transitionDelay = `${index * this.staggerDuration}ms`;
            char.classList.remove('text-rotate-active');
            char.classList.add('text-rotate-exit');

            char.addEventListener('transitionend', function handler() {
                completed++;
                if (completed === chars.length) {
                    callback();
                }
                char.removeEventListener('transitionend', handler);
            });
        });

        // Fallback in case transitionend doesn't fire
        setTimeout(callback, (chars.length * this.staggerDuration) + 400);
    }

    render() {
        const currentText = this.texts[this.currentTextIndex];
        const existingWrapper = this.container.querySelector('.text-rotate-wrapper');

        if (existingWrapper) {
            this.animateOut(existingWrapper, () => {
                existingWrapper.remove();
                const newElement = this.createTextElement(currentText, 'in');
                this.container.appendChild(newElement);
            });
        } else {
            const newElement = this.createTextElement(currentText, 'in');
            this.container.appendChild(newElement);
        }
    }

    next() {
        const nextIndex = this.currentTextIndex === this.texts.length - 1
            ? (this.loop ? 0 : this.currentTextIndex)
            : this.currentTextIndex + 1;

        if (nextIndex !== this.currentTextIndex) {
            this.currentTextIndex = nextIndex;
            this.render();
        }
    }

    previous() {
        const prevIndex = this.currentTextIndex === 0
            ? (this.loop ? this.texts.length - 1 : this.currentTextIndex)
            : this.currentTextIndex - 1;

        if (prevIndex !== this.currentTextIndex) {
            this.currentTextIndex = prevIndex;
            this.render();
        }
    }

    jumpTo(index) {
        const validIndex = Math.max(0, Math.min(index, this.texts.length - 1));
        if (validIndex !== this.currentTextIndex) {
            this.currentTextIndex = validIndex;
            this.render();
        }
    }

    start() {
        if (this.auto && !this.intervalId) {
            this.intervalId = setInterval(() => this.next(), this.rotationInterval);
        }
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    destroy() {
        this.stop();
        this.container.innerHTML = '';
    }

    init() {
        // Add screen reader text
        const srOnly = document.createElement('span');
        srOnly.className = 'text-rotate-sr-only';
        srOnly.textContent = this.texts[this.currentTextIndex];
        this.container.appendChild(srOnly);

        // Render first text
        this.render();

        // Start auto-rotation
        if (this.auto) {
            this.start();
        }
    }
}

export default RotatingText;
