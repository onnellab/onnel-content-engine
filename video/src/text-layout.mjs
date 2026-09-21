/**
 * Keep copy visible in at most two lines, with a 40px minimum. Prefer author's
 * breaks, then whitespace, then character boundaries for Korean/long words.
 * @param {string} text
 * @param {number} width
 * @param {number} preferredSize
 * @param {(text: string, size: number) => number} measure
 */
export function layoutText(text, width, preferredSize, measure) {
  for (let size = preferredSize; size >= 40; size--) {
    const original = text.split('\n');
    if (original.length <= 2 && original.every(line => measure(line, size) <= width)) return {size, text};
    const flat = text.replace(/\n/g, ' ');
    const chars = [...flat];
    for (const wordsOnly of [true, false]) {
      const splits = [];
      for (let i = 1; i < chars.length; i++) {
        if (wordsOnly && chars[i] !== ' ') continue;
        const left = chars.slice(0, i).join('').trim();
        const right = chars.slice(i).join('').trim();
        const maximum = Math.max(measure(left, size), measure(right, size));
        if (left && right && maximum <= width) splits.push({maximum, text: left + '\n' + right});
      }
      splits.sort((a, b) => a.maximum - b.maximum);
      if (splits[0]) return {size, text: splits[0].text};
    }
  }
  throw new Error('Caption cannot fit at readable size; shorten the copy');
}
