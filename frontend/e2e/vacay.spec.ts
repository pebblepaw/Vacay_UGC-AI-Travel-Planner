import { test, expect } from '@playwright/test';

/**
 * VACAY End-to-End Test Suite
 * 
 * Tests the complete flow:
 * 1. Upload a TikTok video
 * 2. Wait for itinerary generation
 * 3. Verify map with Mapbox markers
 * 4. Verify itinerary cards
 * 
 * Prerequisites:
 * - Backend running at http://localhost:8000
 * - Frontend running at http://localhost:5173
 */

// The new Shanghai TikTok URL to test with
const SHANGHAI_TIKTOK_URL = 'https://www.tiktok.com/@acasainlume/video/7565602614243609859?is_from_webapp=1&sender_device=pc&web_id=7598958923672962576';

test.describe('VACAY E2E Tests', () => {

    test('Complete flow: Upload video → Generate itinerary → Verify map and cards', async ({ page }) => {
        // =====================================================
        // STEP 1: Navigate to homepage
        // =====================================================
        await test.step('Navigate to homepage', async () => {
            await page.goto('/');

            // Verify the page loaded with the main components
            await expect(page).toHaveURL('/');

            // Check for the floating "+" button (AddUrlModal trigger)
            const addButton = page.locator('button').filter({ has: page.locator('svg.lucide-plus') }).first();
            await expect(addButton).toBeVisible();
        });

        // =====================================================
        // STEP 2: Open AddUrlModal and submit TikTok URL
        // =====================================================
        let tripId: string;

        await test.step('Upload TikTok video', async () => {
            // Click the floating "+" button to open modal
            const addButton = page.locator('button').filter({ has: page.locator('svg.lucide-plus') }).first();
            await addButton.click();

            // Wait for modal to open
            await expect(page.locator('[role="dialog"]')).toBeVisible();

            // Verify modal title
            await expect(page.getByText('Add Video to Trip')).toBeVisible();

            // Enter the TikTok URL
            const urlInput = page.getByPlaceholder(/paste tiktok/i);
            await expect(urlInput).toBeVisible();
            await urlInput.fill(SHANGHAI_TIKTOK_URL);

            // Verify TikTok platform is detected (badge should appear)
            await expect(page.locator('[role="dialog"]').getByText(/tiktok/i).first()).toBeVisible();

            // Click "Add to Trip" button
            const submitButton = page.getByRole('button', { name: /add to trip/i });
            await expect(submitButton).toBeEnabled();
            await submitButton.click();

            // Verify processing state appears
            await expect(page.getByText(/extracting video content/i)).toBeVisible({ timeout: 5000 });
        });

        // =====================================================
        // STEP 3: Wait for processing and redirect
        // =====================================================
        await test.step('Wait for itinerary generation', async () => {
            // Wait for success message (video processing takes 30-60 seconds)
            await expect(page.getByText(/video added to your trip/i)).toBeVisible({ timeout: 90000 });

            // Wait for redirect with trip ID in URL
            await page.waitForURL(/\?trip=trip_/, { timeout: 10000 });

            // Extract trip ID from URL
            const url = new URL(page.url());
            tripId = url.searchParams.get('trip') || '';
            expect(tripId).toBeTruthy();
            expect(tripId).toMatch(/^trip_/);

            console.log(`Generated trip ID: ${tripId}`);
        });

        // =====================================================
        // STEP 4: Verify itinerary loaded
        // =====================================================
        await test.step('Verify itinerary generation', async () => {
            // Wait for loading to complete
            await expect(page.getByText(/loading your trip/i)).not.toBeVisible({ timeout: 10000 });

            // Verify trip title appears in the map header (glass overlay)
            const mapHeader = page.locator('.glass').filter({ hasText: /locations/i }).first();
            await expect(mapHeader).toBeVisible();

            // Verify trip has at least 1 location
            const locationCountText = await mapHeader.textContent();
            expect(locationCountText).toMatch(/\d+ locations/);

            // Extract location count and verify it's > 0
            const match = locationCountText?.match(/(\d+) locations/);
            const locationCount = match ? parseInt(match[1]) : 0;
            expect(locationCount).toBeGreaterThan(0);

            console.log(`Trip has ${locationCount} locations`);
        });

        // =====================================================
        // STEP 5: Verify Mapbox map is working
        // =====================================================
        await test.step('Verify map functionality', async () => {
            // Check that Mapbox map container exists
            const mapContainer = page.locator('.mapboxgl-map');
            await expect(mapContainer).toBeVisible({ timeout: 10000 });

            // Verify map has navigation controls (added by Mapbox)
            await expect(page.locator('.mapboxgl-ctrl-zoom-in')).toBeVisible();
            await expect(page.locator('.mapboxgl-ctrl-zoom-out')).toBeVisible();

            // Verify markers are present on the map
            const markers = page.locator('.mapbox-marker');
            const markerCount = await markers.count();
            expect(markerCount).toBeGreaterThan(0);

            console.log(`Map has ${markerCount} markers`);

            // Verify first marker has numbered content
            const firstMarker = markers.first();
            await expect(firstMarker).toBeVisible();
            const markerText = await firstMarker.textContent();
            expect(markerText).toMatch(/\d+/);
        });

        // =====================================================
        // STEP 6: Verify map marker interactions
        // =====================================================
        await test.step('Verify map marker clicks', async () => {
            // Click on the first marker
            const markers = page.locator('.mapbox-marker');
            const firstMarker = markers.first();
            await firstMarker.click();

            // Verify POI info panel appears at bottom of map
            // This is the selected POI panel with image and details
            const poiPanel = page.locator('.glass').filter({ hasText: /.+/ }).last();
            await expect(poiPanel).toBeVisible({ timeout: 5000 });
        });

        // =====================================================
        // STEP 7: Switch to Cards view and verify
        // =====================================================
        await test.step('Verify Cards view', async () => {
            // Find and click the "Cards" tab button
            const cardsTab = page.getByRole('tab', { name: /cards/i });

            // If tabs not found by role, try by text
            if (await cardsTab.count() === 0) {
                await page.getByText(/cards/i).first().click();
            } else {
                await cardsTab.click();
            }

            // Wait for cards view to render
            await page.waitForTimeout(500);

            // Verify "All Destinations" header appears (CardsView component)
            await expect(page.getByText(/all destinations/i)).toBeVisible();

            // Verify destination cards are rendered
            // Cards have images, category badges, and vibe text
            const destinationCards = page.locator('.snap-center, [class*="grid"] > div').filter({
                has: page.locator('img')
            });

            // Should have at least one card
            const cardCount = await destinationCards.count();
            expect(cardCount).toBeGreaterThan(0);

            console.log(`Cards view has ${cardCount} destination cards`);
        });

        // =====================================================
        // STEP 8: Verify card content and interactions
        // =====================================================
        await test.step('Verify card content', async () => {
            // Get the first visible card
            const firstCard = page.locator('.snap-center').first();

            if (await firstCard.isVisible()) {
                // Verify card has an image
                await expect(firstCard.locator('img').first()).toBeVisible();

                // Verify card has a category badge (Food, Art, Nature, Culture, Shopping, or Nightlife)
                // The badge is rendered as a div by Shadcn, so we look for text content
                const hasCategoryText = await firstCard.getByText(/Food|Art|Nature|Culture|Shopping|Nightlife/i).count() > 0;
                expect(hasCategoryText).toBeTruthy();

                // Click the card
                await firstCard.click();

                // Card should be highlighted (has ring styling)
                // Wait a moment for animation
                await page.waitForTimeout(300);
            }
        });

        // =====================================================
        // STEP 9: Verify Timeline view
        // =====================================================
        await test.step('Verify Timeline view', async () => {
            // Click Timeline tab specifically
            const timelineTab = page.getByRole('button', { name: /timeline/i });
            await timelineTab.click();

            // Wait for view switch
            await page.waitForTimeout(500);

            // Verify Day sections are visible - look for "Day 1", "Day 2", etc.
            const dayHeaders = page.getByRole('heading', { name: /day \d+/i });
            const dayCount = await dayHeaders.count();
            expect(dayCount).toBeGreaterThan(0);

            console.log(`Timeline has ${dayCount} day headers`);
        });

    });

});

// Separate test for verifying backend health
test('Backend health check', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/api/health');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.status).toBe('healthy');
});
