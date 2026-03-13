/**
 * DON ALPA - ULTIMATE REALISTIC BOSS
 * 8-Frame Animation System with States (Walking, Sleeping, Angry, Pointing)
 */

window.AlpaAssistant = (function () {
    let container, sprite, bubble, textElement;
    let isWalking = false;
    let walkFrame = 1;
    let direction = 1;
    let currentX = 250;
    const walkSpeed = 0.4; // Velocidad reducida para no estresar
    let state = 'IDLE'; // WALKING, SLEEPING, ANGRY, POINTING
    let lastStateChange = Date.now();
    let zzzInterval;
    let autoHideTimer;

    const phrases = [
        "Trabaja, que no te pago por mirar el techo!",
        "Ya terminaste esa cotizacin? El tiempo es oro.",
        "Djate de ver el celular, esto no se hace solo.",
        "Esa casilla no se va a llenar sola!",
        "Ests produciendo o solo haces como que trabajas?",
        "Un error ms y te vas al finiquito.",
        "Mrame a los ojos... TRABAJA!",
        "Caf? A las 5! Ahora dale a las teclas.",
        "Menos scroll y ms control!",
        "Ponte las pilas con esos nmeros!"
    ];

    function init() {
        createUI();
        injectStyles();

        setTimeout(() => {
            state = 'WALKING';
            startAnimationLoops();
            startMovement();
            startBehavioralAI();
            resetAutoHide();
        }, 1000);

        monitorErrors();
        monitorActivity();
    }

    function injectStyles() {
        if (!document.querySelector('link[href*="assistant.css"]')) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'assets/css/assistant.css';
            document.head.appendChild(link);
        }
    }

    function createUI() {
        const header = document.querySelector('header');
        if (!header) return;

        container = document.createElement('div');
        container.id = 'don-alpa-container';
        container.style.left = currentX + 'px';
        // Ensure no jump in size
        container.style.transition = 'left 0.1s linear, opacity 1s ease-in-out';

        container.innerHTML = `
            <div class="boss-bubble" id="boss-bubble">
                <span id="boss-text">Oye!</span>
            </div>
            <div class="don-alpa-sprite don_frame_walk_1" id="boss-sprite"></div>
        `;

        header.appendChild(container);

        sprite = document.getElementById('boss-sprite');
        bubble = document.getElementById('boss-bubble');
        textElement = document.getElementById('boss-text');

        // Clic para despertar al jefe si duerme
        sprite.style.pointerEvents = 'auto';
        sprite.onclick = () => {
            resetAutoHide();
            if (state === 'SLEEPING') wakeUp();
        };
    }

    function startAnimationLoops() {
        setInterval(() => {
            if (state === 'WALKING') {
                walkFrame = (walkFrame % 4) + 1;
                updateVisuals(`don_frame_walk_${walkFrame}`);
            }
            // Si est durmiendo, NO animamos el sprite (imagen esttica)
        }, 250); // Frame rate ms lento
    }

    function updateVisuals(frameClass) {
        if (!sprite) return;
        sprite.className = 'don-alpa-sprite ' + frameClass;
        if (direction === -1) sprite.classList.add('mirror');
    }

    function startMovement() {
        function loop() {
            if (state === 'WALKING') {
                updatePosition();
            }
            requestAnimationFrame(loop);
        }
        requestAnimationFrame(loop);
    }

    function updatePosition() {
        const header = document.querySelector('header');
        if (!header) return;

        // Left bound: after project selector (new UI) or page-title (legacy)
        const leftAnchor = document.querySelector('.header-project') || document.getElementById('page-title');
        // Right bound: before sync button (new UI) or fixed margin (legacy)
        const rightAnchor = document.getElementById('cloud-sync-btn');

        const minX = leftAnchor ? (leftAnchor.offsetLeft + leftAnchor.offsetWidth + 20) : 200;
        const maxX = rightAnchor ? (rightAnchor.offsetLeft - 90) : (header.offsetWidth - 220);

        if (minX >= maxX) return; // no room to walk

        currentX += walkSpeed * direction;

        if (currentX >= maxX) {
            currentX = maxX;
            direction = -1;
            sprite.classList.add('mirror');
        } else if (currentX <= minX) {
            currentX = minX;
            direction = 1;
            sprite.classList.remove('mirror');
        }

        container.style.left = currentX + 'px';
    }

    function startBehavioralAI() {
        setInterval(() => {
            if (state === 'WALKING' && Date.now() - lastStateChange > 20000) {
                const rng = Math.random();
                if (rng < 0.15) {
                    stopAndTalk();
                } else if (rng < 0.25) {
                    goToSleep();
                }
            }
        }, 5000);
    }

    function goToSleep() {
        state = 'SLEEPING';
        lastStateChange = Date.now();
        sprite.title = "Zzz... Haz clic para despertar al jefe";

        // Imagen esttica de dormir (Frame 1)
        updateVisuals('don_frame_sleep_1');

        // Burbuja Zzz intermitente
        showBubble("Zzz...");
        setTimeout(hideBubble, 2000);

        zzzInterval = setInterval(() => {
            if (state === 'SLEEPING') {
                showBubble("Zzzzz...");
                setTimeout(hideBubble, 3000);
            } else {
                clearInterval(zzzInterval);
            }
        }, 8000);
    }

    function wakeUp() {
        clearInterval(zzzInterval);
        resetAutoHide();
        if (container) container.style.opacity = '1';

        state = 'POINTING';
        updateVisuals('don_frame_point');
        showBubble("Qu? Ah! Trabaja!");

        setTimeout(() => {
            hideBubble();
            state = 'WALKING';
            lastStateChange = Date.now();
        }, 3000);
    }

    function stopAndTalk(forcedMsg = null) {
        resetAutoHide();
        if (container) container.style.opacity = '1';

        const prevState = state;
        state = forcedMsg ? 'ANGRY' : (Math.random() > 0.5 ? 'ANGRY' : 'POINTING');
        lastStateChange = Date.now();

        if (state === 'ANGRY') {
            updateVisuals('don_frame_angry');
            container.classList.add('boss-angry-shake');
        } else {
            updateVisuals('don_frame_point');
        }

        const msg = forcedMsg || phrases[Math.floor(Math.random() * phrases.length)];
        showBubble(msg);

        setTimeout(() => {
            hideBubble();
            container.classList.remove('boss-angry-shake');
            state = 'WALKING';
        }, forcedMsg ? 5000 : 3000);
    }

    function showBubble(text) {
        textElement.innerHTML = text;
        bubble.classList.add('show');
    }

    function hideBubble() {
        bubble.classList.remove('show');
    }

    // Auto-apagado tras inactividad del usuario (60s)
    function resetAutoHide() {
        if (container) container.style.opacity = '1';
        clearTimeout(autoHideTimer);
        autoHideTimer = setTimeout(() => {
            if (container) {
                container.style.opacity = '0'; // Se desvanece
            }
        }, 60000);
    }

    function monitorActivity() {
        ['mousemove', 'keypress', 'click', 'scroll'].forEach(evt =>
            document.addEventListener(evt, resetAutoHide)
        );
    }

    function monitorErrors() {
        setInterval(() => {
            const iframe = document.getElementById('app-frame');
            if (!iframe) return;

            try {
                // Try-catch to prevent SecurityError on cross-origin / local file access
                const doc = iframe.contentDocument || iframe.contentWindow.document;
                if (!doc) return;

                // Monitor Validation Errors
                doc.querySelectorAll('input, select').forEach(input => {
                    if (input.dataset.monitoredBossUltimate) return;
                    input.dataset.monitoredBossUltimate = "true";
                    input.addEventListener('blur', () => {
                        resetAutoHide();
                        setTimeout(() => validateField(input, doc), 500);
                    });
                });

                // Monitor Transaction Type Changes
                const typeSelect = doc.getElementById('t-type');
                if (typeSelect && !typeSelect.dataset.monitoredBossReaction) {
                    typeSelect.dataset.monitoredBossReaction = "true";
                    typeSelect.addEventListener('change', (e) => {
                        resetAutoHide();
                        reactToTransaction(e.target.value);
                    });
                }
            } catch (e) {
                // Silent fail for cross-origin restrictions
            }
        }, 2000);
    }

    function reactToTransaction(type) {
        resetAutoHide();

        lastStateChange = Date.now();
        state = 'REACTION';

        sprite.className = 'don-alpa-sprite reaction-mode';

        let frame = 1;
        let animationInterval;

        if (type === 'Ingreso') {
            showBubble("Eso es! A la caja fuerte! ");
            animationInterval = setInterval(() => {
                frame = (frame % 2) + 1;
                sprite.className = `don-alpa-sprite reaction-mode don_frame_income_${frame}`;
            }, 200);
        } else if (type === 'Gasto') {
            showBubble("Nooo! Cuiden las lucas! ");
            container.classList.add('boss-angry-shake');
            animationInterval = setInterval(() => {
                frame = (frame % 2) + 1;
                sprite.className = `don-alpa-sprite reaction-mode don_frame_expense_${frame}`;
            }, 100);
        }

        setTimeout(() => {
            clearInterval(animationInterval);
            hideBubble();
            container.classList.remove('boss-angry-shake');
            sprite.classList.remove('reaction-mode');
            state = 'WALKING';
        }, 4000);
    }

    function validateField(field, doc) {
        const val = field.value.trim();
        const id = field.id;
        if (!val && (id === 't-cost-center' || id === 't-amount' || id === 't-rut')) {
            stopAndTalk("AWEONAO, TE EQUIVOCASTE! LLENA ESO BIEN!");
        }
    }

    return { init };
})();

document.addEventListener('DOMContentLoaded', () => {
    AlpaAssistant.init();
});
