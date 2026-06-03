import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // SPA build: emit a static bundle into the Python package. The Python wheel
    // serves these files; there is no Node server at runtime.
    adapter: adapter({
      pages: '../src/scorepilot/web',
      assets: '../src/scorepilot/web',
      fallback: 'index.html',
      precompress: false,
      strict: true
    })
  }
};

export default config;
