import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for VACAY E2E tests.
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
    testDir: './e2e',

    /* Run tests serially since we're testing a single UI */
    fullyParallel: false,

    /* Fail the build on CI if you accidentally left test.only in the source code */
    forbidOnly: !!process.env.CI,

    /* Retry failed tests once */
    retries: 1,

    /* Single worker for E2E tests */
    workers: 1,

    /* Reporter to use */
    reporter: 'html',

    /* Shared settings for all projects */
    use: {
        /* Base URL for the frontend - use 127.0.0.1 to avoid IPv6 issues */
        baseURL: 'http://127.0.0.1:5173',

        /* Capture screenshot on failure */
        screenshot: 'only-on-failure',

        /* Capture video on failure */
        video: 'retain-on-failure',

        /* Trace on failure for debugging */
        trace: 'retain-on-failure',
    },

    /* Timeout settings - increased for video processing */
    timeout: 120000, // 2 minutes per test (video processing is slow)
    expect: {
        timeout: 60000, // 1 minute for assertions
    },

    /* Configure projects for browsers */
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    /* Don't run local dev server - we expect both servers to already be running */
    // webServer: undefined
});
