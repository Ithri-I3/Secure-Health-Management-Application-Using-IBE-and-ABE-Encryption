// Gestion du thème et des préférences utilisateur

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation des préférences utilisateur depuis localStorage
    initThemePreferences();
    
    // Gestionnaires d'événements pour les préférences d'apparence
    setupThemeEventListeners();
});

// Initialise les préférences de thème depuis localStorage
function initThemePreferences() {
    // Thème sombre/clair
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
        const isDarkMode = localStorage.getItem('darkMode') === 'true';
        darkModeToggle.checked = isDarkMode;
        applyTheme(isDarkMode);
    }
    
    // Couleur principale
    const themeColor = localStorage.getItem('themeColor');
    if (themeColor) {
        document.documentElement.style.setProperty('--primary-color', themeColor);
        highlightSelectedColor(themeColor);
    }
    
    // Taille de police
    const fontSize = localStorage.getItem('fontSize') || 'medium';
    const fontSizeRadio = document.getElementById(`fontSize${fontSize.charAt(0).toUpperCase() + fontSize.slice(1)}`);
    if (fontSizeRadio) {
        fontSizeRadio.checked = true;
        applyFontSize(fontSize);
    }
}

// Configure les écouteurs d'événements pour les préférences de thème
function setupThemeEventListeners() {
    // Bascule du mode sombre
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('change', function() {
            const isDarkMode = this.checked;
            localStorage.setItem('darkMode', isDarkMode);
            applyTheme(isDarkMode);
        });
    }
    
    // Sélection de couleur de thème
    const colorButtons = document.querySelectorAll('.theme-color-btn');
    colorButtons.forEach(button => {
        button.addEventListener('click', function() {
            const color = this.getAttribute('data-color');
            localStorage.setItem('themeColor', color);
            document.documentElement.style.setProperty('--primary-color', color);
            highlightSelectedColor(color);
        });
    });
    
    // Taille de police
    const fontSizeRadios = document.querySelectorAll('input[name="fontSize"]');
    fontSizeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.checked) {
                const fontSize = this.value;
                localStorage.setItem('fontSize', fontSize);
                applyFontSize(fontSize);
            }
        });
    });
    
    // Bouton de sauvegarde des préférences
    const saveButton = document.getElementById('saveAppearanceSettings');
    if (saveButton) {
        saveButton.addEventListener('click', function() {
            alert('Préférences d'apparence enregistrées avec succès!');
        });
    }
}

// Applique le thème sombre ou clair
function applyTheme(isDarkMode) {
    if (isDarkMode) {
        document.body.setAttribute('data-theme', 'dark');
    } else {
        document.body.removeAttribute('data-theme');
    }
}

// Met en évidence la couleur de thème sélectionnée
function highlightSelectedColor(selectedColor) {
    const colorButtons = document.querySelectorAll('.theme-color-btn');
    colorButtons.forEach(button => {
        const color = button.getAttribute('data-color');
        if (color === selectedColor) {
            button.style.border = '3px solid white';
            button.style.boxShadow = '0 0 5px rgba(0,0,0,0.5)';
        } else {
            button.style.border = 'none';
            button.style.boxShadow = 'none';
        }
    });
}

// Applique la taille de police sélectionnée
function applyFontSize(fontSize) {
    document.body.classList.remove('font-small', 'font-medium', 'font-large');
    document.body.classList.add(`font-${fontSize}`);
}