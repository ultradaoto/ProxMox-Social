/**
 * Color Utilities
 * Extract and convert colors
 */

class ColorUtils {

    /**
     * Get all colors from an element
     */
    static getElementColors(element) {
        const styles = window.getComputedStyle(element);

        const colors = {
            background: this.parseColor(styles.backgroundColor),
            text: this.parseColor(styles.color),
            border: this.parseColor(styles.borderColor),
        };

        // Check for gradient
        const bgImage = styles.backgroundImage;
        if (bgImage && bgImage !== 'none' && bgImage.includes('gradient')) {
            colors.gradient = this.extractGradientColors(bgImage);
        }

        return colors;
    }

    /**
     * Parse any CSS color to RGB
     */
    static parseColor(cssColor) {
        if (!cssColor || cssColor === 'transparent' || cssColor === 'rgba(0, 0, 0, 0)') {
            return null;
        }

        // Create temporary element to parse color
        const temp = document.createElement('div');
        temp.style.color = cssColor;
        document.body.appendChild(temp);

        const computed = window.getComputedStyle(temp).color;
        document.body.removeChild(temp);

        // Parse rgb/rgba format
        const match = computed.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (match) {
            return {
                r: parseInt(match[1]),
                g: parseInt(match[2]),
                b: parseInt(match[3]),
                hex: this.rgbToHex(parseInt(match[1]), parseInt(match[2]), parseInt(match[3])),
                rgb: `rgb(${match[1]}, ${match[2]}, ${match[3]})`,
                hsl: this.rgbToHsl(parseInt(match[1]), parseInt(match[2]), parseInt(match[3]))
            };
        }

        return null;
    }

    /**
     * Extract colors from gradient
     */
    static extractGradientColors(gradientStr) {
        const colorRegex = /#[0-9A-Fa-f]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\)/g;
        const matches = gradientStr.match(colorRegex);

        if (matches) {
            return matches.map(c => this.parseColor(c)).filter(Boolean);
        }

        return [];
    }

    /**
     * Get color at specific point in image
     */
    static getPixelColor(img, x, y) {
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);

        // Calculate position relative to image
        const rect = img.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        const imgX = Math.floor((x - rect.left) * scaleX);
        const imgY = Math.floor((y - rect.top) * scaleY);

        const pixel = ctx.getImageData(imgX, imgY, 1, 1).data;

        return {
            r: pixel[0],
            g: pixel[1],
            b: pixel[2],
            hex: this.rgbToHex(pixel[0], pixel[1], pixel[2]),
            rgb: `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`,
            hsl: this.rgbToHsl(pixel[0], pixel[1], pixel[2])
        };
    }

    /**
     * Convert RGB to HEX
     */
    static rgbToHex(r, g, b) {
        return '#' + [r, g, b].map(x => {
            const hex = x.toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('').toUpperCase();
    }

    /**
     * Convert RGB to HSL
     */
    static rgbToHsl(r, g, b) {
        r /= 255;
        g /= 255;
        b /= 255;

        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0;
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

            switch (max) {
                case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
                case g: h = ((b - r) / d + 2) / 6; break;
                case b: h = ((r - g) / d + 4) / 6; break;
            }
        }

        return `hsl(${Math.round(h * 360)}°, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
    }
}

if (typeof window !== 'undefined') {
    window.ColorUtils = ColorUtils;
}
