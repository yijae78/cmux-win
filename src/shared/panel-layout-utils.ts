import type { PanelLayoutTree } from './types';

/** Find a leaf node by panelId */
export function findLeaf(tree: PanelLayoutTree, panelId: string): PanelLayoutTree | null {
  if (tree.type === 'leaf') {
    return tree.panelId === panelId ? tree : null;
  }
  return findLeaf(tree.children[0], panelId) ?? findLeaf(tree.children[1], panelId);
}

/** Replace a leaf with a new subtree (immutable) */
export function replaceLeaf(
  tree: PanelLayoutTree,
  panelId: string,
  replacement: PanelLayoutTree,
): PanelLayoutTree {
  if (tree.type === 'leaf') {
    return tree.panelId === panelId ? replacement : tree;
  }
  return {
    ...tree,
    children: [
      replaceLeaf(tree.children[0], panelId, replacement),
      replaceLeaf(tree.children[1], panelId, replacement),
    ],
  };
}

/** Find the parent split node containing a direct child with panelId */
export function findParentSplit(
  tree: PanelLayoutTree,
  panelId: string,
): { direction: 'horizontal' | 'vertical'; ratio: number } | null {
  if (tree.type === 'leaf') return null;
  for (const child of tree.children) {
    if (child.type === 'leaf' && child.panelId === panelId) {
      return { direction: tree.direction, ratio: tree.ratio };
    }
    const found = findParentSplit(child, panelId);
    if (found) return found;
  }
  return null;
}

/** Update the ratio of the split that directly contains panelId */
export function updateRatioForPanel(
  tree: PanelLayoutTree,
  panelId: string,
  newRatio: number,
): PanelLayoutTree {
  if (tree.type === 'leaf') return tree;
  const clamped = Math.max(0.1, Math.min(0.9, newRatio));
  const isDirectChild = tree.children.some((c) => c.type === 'leaf' && c.panelId === panelId);
  if (isDirectChild) {
    return { ...tree, ratio: clamped };
  }
  return {
    ...tree,
    children: [
      updateRatioForPanel(tree.children[0], panelId, newRatio),
      updateRatioForPanel(tree.children[1], panelId, newRatio),
    ],
  };
}

/** Remove a leaf and promote its sibling */
export function removeLeaf(tree: PanelLayoutTree, panelId: string): PanelLayoutTree | null {
  if (tree.type === 'leaf') {
    return tree.panelId === panelId ? null : tree;
  }
  const [left, right] = tree.children;
  if (left.type === 'leaf' && left.panelId === panelId) return right;
  if (right.type === 'leaf' && right.panelId === panelId) return left;
  const newLeft = removeLeaf(left, panelId);
  if (newLeft !== left) return { ...tree, children: [newLeft ?? right, right] };
  const newRight = removeLeaf(right, panelId);
  if (newRight !== right) return { ...tree, children: [left, newRight ?? left] };
  return tree;
}
