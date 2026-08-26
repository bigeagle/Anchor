/**
 * Minimal KaTeX extension for marked, with pandoc-style inline-math rules.
 *
 * Why not marked-katex-extension: its "standard" mode only opens math at a
 * line start or after a space (breaks `$x$` after CJK punctuation, common in
 * Chinese notes), and its "nonStandard" mode drops every guard (mangles
 * currency like "$100 到 $200" and spaced-out "$ x $"). These tokenizers
 * follow pandoc's `tex_math_dollars` rules instead:
 *
 * - the opening `$`/`$$` is not followed by whitespace and is not `\$`-escaped
 * - the closing delimiter is not preceded by whitespace or a backslash
 * - the closing `$` is NOT followed immediately by a digit — this is what
 *   keeps prices ("$100 到 $200", "$50，原价 $100") out of math mode
 *
 * Invalid TeX renders as the source text (throwOnError: false).
 */

import katex from 'katex';
import type { TokenizerAndRendererExtension } from 'marked';

const inlineRule = /^(\${1,2})(?!\$)(?!\s)((?:\\.|[^\\\n])*?(?:\\.|[^\\\s$]))\1(?!\d)/;
const blockRule = /^(\${1,2})\n((?:\\[^]|[^\\])+?)\n\1(?:\n|$)/;

function render(tex: string, displayMode: boolean): string {
  return katex.renderToString(tex, { displayMode, throwOnError: false });
}

const inlineKatex: TokenizerAndRendererExtension = {
  name: 'inlineKatex',
  level: 'inline',
  start(src: string) {
    // Find the first `$` that is not backslash-escaped.
    let from = 0;
    for (;;) {
      const index = src.indexOf('$', from);
      if (index === -1) return;
      if (src[index - 1] !== '\\') return index;
      from = index + 1;
    }
  },
  tokenizer(src: string) {
    const match = src.match(inlineRule);
    if (match) {
      return {
        type: 'inlineKatex',
        raw: match[0],
        text: match[2].trim(),
        displayMode: match[1].length === 2,
      };
    }
  },
  renderer(token) {
    return render(token.text, token.displayMode as boolean);
  },
};

const blockKatex: TokenizerAndRendererExtension = {
  name: 'blockKatex',
  level: 'block',
  tokenizer(src: string) {
    const match = src.match(blockRule);
    if (match) {
      return {
        type: 'blockKatex',
        raw: match[0],
        text: match[2].trim(),
        displayMode: true,
      };
    }
  },
  renderer(token) {
    return `${render(token.text, true)}\n`;
  },
};

export const katexExtensions = [inlineKatex, blockKatex];
