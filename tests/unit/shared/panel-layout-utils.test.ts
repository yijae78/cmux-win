import { describe, it, expect } from 'vitest';
import {
  findLeaf,
  replaceLeaf,
  findParentSplit,
  updateRatioForPanel,
  removeLeaf,
} from '../../../src/shared/panel-layout-utils';
import type { PanelLayoutTree } from '../../../src/shared/types';

const leaf = (panelId: string): PanelLayoutTree => ({ type: 'leaf', panelId });

const split = (
  dir: 'horizontal' | 'vertical',
  ratio: number,
  left: PanelLayoutTree,
  right: PanelLayoutTree,
): PanelLayoutTree => ({
  type: 'split',
  direction: dir,
  ratio,
  children: [left, right],
});

describe('findLeaf', () => {
  it('finds leaf in single-leaf tree', () => {
    const tree = leaf('p1');
    expect(findLeaf(tree, 'p1')).toEqual(tree);
  });

  it('finds leaf in nested split', () => {
    const tree = split(
      'horizontal',
      0.5,
      leaf('p1'),
      split('vertical', 0.5, leaf('p2'), leaf('p3')),
    );
    expect(findLeaf(tree, 'p3')).toEqual(leaf('p3'));
  });

  it('returns null for nonexistent panel', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    expect(findLeaf(tree, 'p99')).toBeNull();
  });
});

describe('replaceLeaf', () => {
  it('replaces leaf in single-leaf tree', () => {
    const tree = leaf('p1');
    const replacement = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    expect(replaceLeaf(tree, 'p1', replacement)).toEqual(replacement);
  });

  it('replaces leaf in nested split', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    const replacement = split('vertical', 0.3, leaf('p2'), leaf('p3'));
    const result = replaceLeaf(tree, 'p2', replacement);
    expect(result).toEqual(split('horizontal', 0.5, leaf('p1'), replacement));
  });

  it('preserves other leaves', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    const result = replaceLeaf(tree, 'p1', leaf('p99'));
    expect(findLeaf(result, 'p2')).toEqual(leaf('p2'));
  });
});

describe('findParentSplit', () => {
  it('finds parent split of direct child', () => {
    const tree = split('horizontal', 0.6, leaf('p1'), leaf('p2'));
    expect(findParentSplit(tree, 'p1')).toEqual({ direction: 'horizontal', ratio: 0.6 });
  });

  it('returns null for single leaf', () => {
    expect(findParentSplit(leaf('p1'), 'p1')).toBeNull();
  });

  it('returns null for nonexistent panel', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    expect(findParentSplit(tree, 'p99')).toBeNull();
  });
});

describe('updateRatioForPanel', () => {
  it('updates ratio on direct parent split', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    const result = updateRatioForPanel(tree, 'p1', 0.7);
    expect(result.type === 'split' && result.ratio).toBe(0.7);
  });

  it('clamps ratio to 0.1-0.9', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    const low = updateRatioForPanel(tree, 'p1', 0.01);
    expect(low.type === 'split' && low.ratio).toBe(0.1);
    const high = updateRatioForPanel(tree, 'p1', 0.99);
    expect(high.type === 'split' && high.ratio).toBe(0.9);
  });

  it('returns unchanged tree if panel not found', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    const result = updateRatioForPanel(tree, 'p99', 0.7);
    expect(result).toEqual(tree);
  });
});

describe('removeLeaf', () => {
  it('removes leaf and promotes sibling', () => {
    const tree = split('horizontal', 0.5, leaf('p1'), leaf('p2'));
    expect(removeLeaf(tree, 'p1')).toEqual(leaf('p2'));
  });

  it('removes nested leaf and promotes sibling subtree', () => {
    const inner = split('vertical', 0.5, leaf('p2'), leaf('p3'));
    const tree = split('horizontal', 0.5, leaf('p1'), inner);
    const result = removeLeaf(tree, 'p2');
    // After removing p2 from inner, p3 is promoted; outer becomes split(h, 0.5, p1, p3)
    expect(result).toEqual(split('horizontal', 0.5, leaf('p1'), leaf('p3')));
  });

  it('returns null for single-leaf tree', () => {
    expect(removeLeaf(leaf('p1'), 'p1')).toBeNull();
  });
});
