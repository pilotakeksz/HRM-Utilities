/**
 * Image Catalog Integration for Embed Builder
 * Provides functions to load and access catalogued Discord image URLs
 */

class ImageCatalogManager {
    constructor() {
        this.catalog = {};
        this.isLoaded = false;
        this.cacheExpiry = 5 * 60 * 1000; // 5 minutes
        this.lastLoadTime = 0;
    }

    /**
     * Load the image catalog from discord_urls.json
     */
    async loadCatalog() {
        const now = Date.now();
        
        // Use cache if available and not expired
        if (this.isLoaded && (now - this.lastLoadTime) < this.cacheExpiry) {
            console.log('📦 Using cached image catalog');
            return this.catalog;
        }

        try {
            console.log('📥 Loading image catalog...');
            const response = await fetch('./beta_cogs/images/discord_urls.json');
            
            if (!response.ok) {
                console.warn('⚠️ Could not load image catalog:', response.status);
                return {};
            }

            this.catalog = await response.json();
            this.isLoaded = true;
            this.lastLoadTime = now;
            console.log(`✅ Loaded ${Object.keys(this.catalog).length} images`);
            
            return this.catalog;
        } catch (error) {
            console.error('❌ Error loading image catalog:', error);
            return {};
        }
    }

    /**
     * Get URL for a specific image
     */
    async getImageUrl(filename) {
        if (!this.isLoaded) {
            await this.loadCatalog();
        }
        return this.catalog[filename] || null;
    }

    /**
     * Get list of all available images
     */
    async listImages() {
        if (!this.isLoaded) {
            await this.loadCatalog();
        }
        return Object.keys(this.catalog);
    }

    /**
     * Check if an image is catalogued
     */
    async isCatalogued(filename) {
        if (!this.isLoaded) {
            await this.loadCatalog();
        }
        return filename in this.catalog;
    }

    /**
     * Get entire catalog
     */
    async getCatalog() {
        if (!this.isLoaded) {
            await this.loadCatalog();
        }
        return this.catalog;
    }

    /**
     * Clear cache to force reload
     */
    clearCache() {
        this.isLoaded = false;
        this.catalog = {};
        console.log('🔄 Image catalog cache cleared');
    }

    /**
     * Create image picker HTML
     */
    async createImagePicker(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Container ${containerId} not found`);
            return;
        }

        const images = await this.listImages();
        
        if (images.length === 0) {
            container.innerHTML = '<p style="color: #999;">No catalogued images available</p>';
            return;
        }

        let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 10px;">';
        
        for (const filename of images) {
            const url = this.catalog[filename];
            html += `
                <div style="border: 1px solid #ddd; border-radius: 4px; padding: 5px; cursor: pointer;" 
                     onclick="imageCatalog.selectImage('${filename}')" 
                     title="${filename}">
                    <img src="${url}" style="width: 100%; height: 80px; object-fit: cover; border-radius: 2px;">
                    <small style="display: block; margin-top: 5px; word-break: break-all; font-size: 10px;">${filename}</small>
                </div>
            `;
        }
        
        html += '</div>';
        container.innerHTML = html;
    }

    /**
     * Handle image selection (to be overridden)
     */
    selectImage(filename) {
        console.log('Selected image:', filename);
        // Trigger custom event that embed builder can listen to
        const event = new CustomEvent('imageCatalogSelected', {
            detail: {
                filename: filename,
                url: this.catalog[filename]
            }
        });
        document.dispatchEvent(event);
    }
}

// Global instance
const imageCatalog = new ImageCatalogManager();

// Auto-load catalog when page loads
document.addEventListener('DOMContentLoaded', () => {
    imageCatalog.loadCatalog().catch(e => console.warn('Could not auto-load catalog:', e));
});
