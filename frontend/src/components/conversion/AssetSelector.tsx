/**
 * AssetSelector Component
 *
 * Grouped checkbox list for asset selection with select-all per Asset_Type group.
 * Displays discovered assets grouped by type with indeterminate checkbox state
 * for partial group selection and a summary bar showing selection count.
 *
 * Requirements: 11.2, 2.1, 2.2
 */

import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { AssetSelection } from '../../services/conversionApi';
import './AssetSelector.css';

// ---------------------------------------------------------------------------
// Helpers (exported for reuse by parent components)
// ---------------------------------------------------------------------------

/** Build a unique key for an asset */
export function assetKey(a: AssetSelection): string {
  return `${a.asset_type}::${a.asset_name}`;
}

/** Group assets by asset_type */
function groupAssetsByType(
  assets: AssetSelection[]
): Record<string, AssetSelection[]> {
  const groups: Record<string, AssetSelection[]> = {};
  for (const asset of assets) {
    if (!groups[asset.asset_type]) {
      groups[asset.asset_type] = [];
    }
    groups[asset.asset_type].push(asset);
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface AssetSelectorProps {
  /** Full list of discovered assets */
  assets: AssetSelection[];
  /** Currently selected asset keys (built via assetKey()) */
  selectedKeys: Set<string>;
  /** Callback when selection changes */
  onSelectionChange: (newKeys: Set<string>) => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Checkbox that supports the indeterminate state via a ref */
const IndeterminateCheckbox: React.FC<{
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
  ariaLabel: string;
}> = ({ checked, indeterminate, onChange, ariaLabel }) => {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={ariaLabel}
    />
  );
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const AssetSelector: React.FC<AssetSelectorProps> = ({
  assets,
  selectedKeys,
  onSelectionChange,
}) => {
  const groupedAssets = useMemo(() => groupAssetsByType(assets), [assets]);
  const groupNames = useMemo(
    () => Object.keys(groupedAssets).sort(),
    [groupedAssets]
  );

  const toggleAsset = useCallback(
    (asset: AssetSelection) => {
      const next = new Set(selectedKeys);
      const key = assetKey(asset);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      onSelectionChange(next);
    },
    [selectedKeys, onSelectionChange]
  );

  const toggleGroup = useCallback(
    (type: string) => {
      const group = groupedAssets[type] || [];
      const allSelected = group.every((a) => selectedKeys.has(assetKey(a)));
      const next = new Set(selectedKeys);
      for (const a of group) {
        if (allSelected) {
          next.delete(assetKey(a));
        } else {
          next.add(assetKey(a));
        }
      }
      onSelectionChange(next);
    },
    [groupedAssets, selectedKeys, onSelectionChange]
  );

  const selectedCount = useMemo(
    () => assets.filter((a) => selectedKeys.has(assetKey(a))).length,
    [assets, selectedKeys]
  );

  if (assets.length === 0) {
    return (
      <div className="asset-selector">
        <div className="asset-selection-empty">
          No discovered assets available. Assets will appear here once discovery
          is run for the migration project.
        </div>
      </div>
    );
  }

  return (
    <div className="asset-selector">
      {groupNames.map((type) => {
        const group = groupedAssets[type];
        const allSelected = group.every((a) => selectedKeys.has(assetKey(a)));
        const someSelected =
          !allSelected && group.some((a) => selectedKeys.has(assetKey(a)));

        return (
          <div className="asset-group" key={type}>
            <div className="asset-group-header">
              <label className="asset-group-checkbox">
                <IndeterminateCheckbox
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={() => toggleGroup(type)}
                  ariaLabel={`Select all ${type.replace(/_/g, ' ')} assets`}
                />
                {type.replace(/_/g, ' ')}
              </label>
              <span className="asset-group-count">{group.length}</span>
            </div>
            <div className="asset-list">
              {group.map((asset) => {
                const key = assetKey(asset);
                return (
                  <div className="asset-item" key={key}>
                    <label>
                      <input
                        type="checkbox"
                        checked={selectedKeys.has(key)}
                        onChange={() => toggleAsset(asset)}
                        aria-label={`Select ${asset.asset_name}`}
                      />
                      <span className="asset-name">{asset.asset_name}</span>
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      <div className="asset-selection-summary">
        <strong>{selectedCount}</strong> of{' '}
        <strong>{assets.length}</strong> assets selected
      </div>
    </div>
  );
};
