import js from '@eslint/js';

export default [
  { ignores: ['dist/**', '.astro/**', 'node_modules/**'] },
  js.configs.recommended,
  {
    files: ['**/*.mjs'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { process: 'readonly', URL: 'readonly', Buffer: 'readonly', structuredClone: 'readonly' },
    },
    rules: {
      // These expressions deliberately reject control characters in imported paths.
      'no-control-regex': 'off',
    },
  },
];
