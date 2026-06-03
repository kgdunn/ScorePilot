// The client-held draft preprocessing spec. In this stage it drives previews and
// exclusions; it is shaped to serialize straight to the API's PreprocessingSpec
// when a model is later fitted from it.
import type { ScalingKind, TransformKind } from './api';

export interface VariableTransform {
  kind: TransformKind;
  c1: number;
  c2: number;
}

export interface DraftSpec {
  xColumns: string[];
  yColumns: string[];
  excludedColumns: string[];
  excludedRows: number[];
  transforms: Record<string, VariableTransform>;
  defaultScaling: ScalingKind;
  scaling: Record<string, ScalingKind>;
}

export function emptyDraft(): DraftSpec {
  return {
    xColumns: [],
    yColumns: [],
    excludedColumns: [],
    excludedRows: [],
    transforms: {},
    defaultScaling: 'unit_variance',
    scaling: {}
  };
}

export function toApiSpec(draft: DraftSpec): Record<string, unknown> {
  return {
    x_columns: draft.xColumns,
    y_columns: draft.yColumns,
    excluded_columns: draft.excludedColumns,
    excluded_rows: draft.excludedRows,
    transforms: draft.transforms,
    default_scaling: draft.defaultScaling,
    scaling: draft.scaling
  };
}

export function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function toggleNumber(list: number[], value: number): number[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}
