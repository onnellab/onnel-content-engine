import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const candidate = JSON.parse(fs.readFileSync('preview-candidate.json', 'utf8'));
const output = path.resolve('preview-screenshots');
fs.mkdirSync(output, { recursive: true });

for (const locale of candidate.locales as string[]) {
  test(`${locale}: exact candidate page, links and responsive controls`, async ({ page }, testInfo) => {
    const route = `/blog/${locale.toLowerCase()}/${candidate.slug}/`;
    const source = fs.readFileSync(path.join('src/content/blog', locale, `${candidate.slug}.md`), 'utf8');
    const title = JSON.parse(source.match(/^title: (.+)$/m)![1]);
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width: testInfo.project.name === 'mobile' ? 390 : 1440, height: 900 });
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    await expect(page.locator('article h1')).toHaveText(title);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `https://onnellab.com${route}`);
    for (const other of candidate.locales as string[]) {
      await expect(page.locator(`link[rel="alternate"][hreflang="${other}"]`)).toHaveAttribute('href', `https://onnellab.com/blog/${other.toLowerCase()}/${candidate.slug}/`);
    }
    await expect(page.locator('link[rel="alternate"][hreflang="x-default"]')).toHaveAttribute('href', `https://onnellab.com/blog/en/${candidate.slug}/`);
    await expect(page.locator('meta[property="article:published_time"]')).toHaveCount(0);
    await expect(page.locator('.faq-list details')).toHaveCount(4);
    await expect(page.locator('article table tbody tr')).toHaveCount(candidate.table_rows[locale]);

    // Check the browser's actual native list-marker inputs and computed style.
    // Blank-separated workflow steps must keep their authored start numbers.
    if (candidate.slug === 'design-consistent-file-naming-system') {
      const renderedNumbers = await page.locator('.article-body ol').evaluateAll(lists =>
        lists.flatMap(list => {
          const ol = list as HTMLOListElement;
          let current = ol.start;
          return Array.from(ol.children).filter(node => node.tagName === 'LI').map(node => {
            const li = node as HTMLLIElement;
            if (li.hasAttribute('value')) current = li.value;
            const style = getComputedStyle(li);
            const result = { number: current, display: style.display, type: style.listStyleType };
            current += ol.reversed ? -1 : 1;
            return result;
          });
        }));
      expect(renderedNumbers).toEqual([1, 2, 3, 4, 5, 6].map(number => ({
        number, display: 'list-item', type: 'decimal',
      })));
    }
    const image = page.locator('article img[src*="workflow-diagram"]');
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true);
    for (const storeUrl of candidate.store_urls as string[]) {
      await expect(page.locator(`article a[href="${storeUrl}"]`).first()).toBeVisible();
    }
    const hrefs = await page.locator('a[href]').evaluateAll(links => links.map(link => link.getAttribute('href')!));
    const checked: string[] = [];
    for (const href of [...new Set(hrefs)]) {
      const url = new URL(href, `https://onnellab.com${route}`);
      if (url.origin !== 'https://onnellab.com') continue;
      if (url.pathname === route && url.hash) {
        expect(await page.locator(`[id=${JSON.stringify(decodeURIComponent(url.hash.slice(1)))}]`).count(), href).toBe(1);
      } else {
        const result = await page.request.get(url.pathname + url.search);
        expect(result.ok(), href).toBe(true);
        checked.push(url.pathname);
      }
    }
    const social = await page.request.get(`/blog-assets/${locale}/${candidate.slug}/social-card.png`);
    expect(social.ok()).toBe(true);
    const png = await social.body();
    expect(png.readUInt32BE(16)).toBe(1200);
    expect(png.readUInt32BE(20)).toBe(675);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
    // Exercise the actual image viewer and its keyboard dismissal.
    await page.locator('[data-article-image-trigger]').first().click();
    await expect(page.locator('dialog.article-image-viewer')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('dialog.article-image-viewer')).not.toBeVisible();
    // Expand real FAQ controls so the screenshot includes all reviewed text.
    for (const detail of await page.locator('.faq-list details').all()) await detail.locator('summary').click();
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, `${locale}-${testInfo.project.name}.png`), fullPage: true, animations: 'disabled' });
    expect(errors).toEqual([]);
    fs.writeFileSync(path.join(output, `${locale}-${testInfo.project.name}.json`), JSON.stringify({ locale, route, viewport: page.viewportSize(), internalLinks: checked, externalLinks: hrefs.filter(href => /^https?:/.test(href) && !href.startsWith('https://onnellab.com')), pageErrors: errors, publicationDatesAdded: false }, null, 2));
  });
}
