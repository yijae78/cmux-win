import { describe, it, expect } from 'vitest';
import { markdownToHtml } from '../../../src/shared/markdown-parser';

describe('markdownToHtml', () => {
  it('converts h1', () => {
    expect(markdownToHtml('# Hello')).toContain('<h1>Hello</h1>');
  });

  it('converts h2', () => {
    expect(markdownToHtml('## World')).toContain('<h2>World</h2>');
  });

  it('converts bold', () => {
    expect(markdownToHtml('**bold**')).toContain('<strong>bold</strong>');
  });

  it('converts italic', () => {
    expect(markdownToHtml('*italic*')).toContain('<em>italic</em>');
  });

  it('converts inline code', () => {
    expect(markdownToHtml('`code`')).toContain('<code>code</code>');
  });

  it('converts links', () => {
    expect(markdownToHtml('[text](url)')).toContain('<a href="url">text</a>');
  });

  it('converts horizontal rule', () => {
    expect(markdownToHtml('---')).toContain('<hr>');
  });

  it('handles empty string', () => {
    expect(markdownToHtml('')).toBeDefined();
  });

  it('escapes HTML entities', () => {
    const result = markdownToHtml('<script>alert("xss")</script>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  it('converts unordered list items', () => {
    const result = markdownToHtml('- item one\n- item two');
    expect(result).toContain('<ul>');
    expect(result).toContain('<li>item one</li>');
    expect(result).toContain('<li>item two</li>');
  });

  it('converts bold-italic combo', () => {
    expect(markdownToHtml('***both***')).toContain('<strong><em>both</em></strong>');
  });

  it('converts code blocks', () => {
    const result = markdownToHtml('```js\nconsole.log("hi");\n```');
    expect(result).toContain('<pre><code>');
    expect(result).toContain('console.log');
  });
});
