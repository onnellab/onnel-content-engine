# External Account URL Update Checklist

Use this checklist after the GitHub account and Pages site migration.

Canonical website URL:

```text
https://onnellab.com/
```

Support email:

```text
onnellab.app@gmail.com
```

## Accounts

Update each public profile website URL to `https://onnellab.com/`.

```text
GitHub profile
X profile
LinkedIn profile
Dev.to profile
Hashnode profile
Bluesky profile
```

## X Developer App

Use these URLs in the app settings:

```text
Website URL: https://onnellab.com/
Callback URI / Redirect URL: https://onnellab.com/oauth/x/callback/
Terms of Service: https://onnellab.com/terms/
Privacy Policy: https://onnellab.com/privacy/
```

## Verification

After updating external accounts, verify:

```text
https://onnellab.com/
https://onnellab.com/privacy/
https://onnellab.com/terms/
https://onnellab.com/oauth/x/callback/
https://onnellab.com/favicon.svg?v=20260712-ol-transparent-v2
```

## Google Search Console

The old GitHub Pages host currently returns 404, not a 301 redirect:

```text
https://onnelakin.github.io/
https://onnelakin.github.io/privacy/
```

Because Google's Change of Address tool requires 301 redirects from the old site to the new site, do not use the Change of Address tool unless `https://onnelakin.github.io/` starts returning a server-side 301 to `https://onnellab.com/`.

Use this fallback process:

```text
1. Add a new URL-prefix property for https://onnellab.com/ in Search Console.
2. Submit https://onnellab.com/sitemap.xml.
3. Inspect and request indexing for the homepage, privacy, terms, and important app landing pages.
4. Keep canonical URLs, sitemap URLs, robots.txt, app landing pages, and external profiles on https://onnellab.com/.
5. Re-check the old host occasionally; if a real 301 becomes available, then run the Change of Address workflow.
```

For future migrations, prefer a custom domain that ONNELLAB controls directly so 301 redirects can be configured at the DNS/CDN/hosting layer.
