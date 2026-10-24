# Renderer asset provenance

`renderer.css` is original code for this migration foundation. It implements common structural observations from the public homepage; it does not contain copied TheBlogger CSS, JavaScript, fonts, logos, photos or icon files. The public page referenced the commercial TheBlogger/Pixelwars theme on 2026-10-24. Public accessibility alone does not establish redistribution rights. The owner's licensed theme package, exact license and customizations remain pending before any theme source/assets can be reused.

The observed homepage requested Karla and Coustard through Google Fonts. This build uses locally bundled **@fontsource/karla 5.3.0** and **@fontsource/coustard 5.3.0**, both distributed under **SIL Open Font License 1.1**. Their original `LICENSE` texts are retained here as `Karla-OFL.txt` and `Coustard-OFL.txt`; font files are bundled by Astro from the locked packages. No browser request to Google Fonts or the WordPress theme server is needed. Latin/Latin Extended Karla regular/italic/bold and Latin Coustard regular are included; other scripts use system fallbacks until the source baseline establishes requirements.

Package sources: [Karla](https://www.npmjs.com/package/@fontsource/karla), [Coustard](https://www.npmjs.com/package/@fontsource/coustard). Astro and parse5 use MIT licenses; Ajv and ajv-formats use MIT licenses. Exact package versions and transitive dependencies are recorded in the root lockfile.

`fixtures/v1/media/example.svg` is the synthetic MIG-01 fixture, verified and copied to the output with its original bytes. No production media is included by this renderer work.
