"""Field ownership for the Item 3/4 scoring-sync and public-projection writers.

Projection sets apply to nodes owned by third_fourth_item_public. In separate
authored window reviews, public_basis/public_boundary are source prose; those
nodes are preserved by scoring sync and are not projection targets.
"""
from collections.abc import Mapping


PROJECTION_SOURCE_FIELDS = frozenset({
    'public_reading', 'public_b_source_catalog',
    'public_exclusion_reading', 'public_c_result_reading',
})
PROJECTION_DERIVED_FIELDS = frozenset({
    'public_adjudication_summary', 'public_evidence_items', 'public_boundary',
    'public_level_label', 'public_component_label', 'public_axis_projections',
    'public_military_cost', 'public_military_net_loss',
})
PUBLIC_PROJECTION_FIELDS = PROJECTION_SOURCE_FIELDS | PROJECTION_DERIVED_FIELDS
PUBLIC_METADATA_FIELDS = frozenset({
    'public_projection_schema_version', 'public_projection_status',
    'public_projection_source', 'public_projection_record_count',
    'public_projection_package_count',
})
# Retain source bookkeeping and window explanations at their existing owner.
PUBLIC_CONTEXT_FIELDS = frozenset({
    'public_basis', 'public_03_record_refs', 'public_parent_to_window_slice',
})
SCORING_SYNC_PRESERVED_FIELDS = PUBLIC_PROJECTION_FIELDS | PUBLIC_METADATA_FIELDS | PUBLIC_CONTEXT_FIELDS


def validate_public_keys(mapping):
    """New public fields require an explicit writer policy, never a prefix guess."""
    unknown = {key for key in mapping if str(key).startswith('public_') and key not in SCORING_SYNC_PRESERVED_FIELDS}
    if unknown:
        raise ValueError(f'第三／第四项公开字段未声明维护归属：{sorted(unknown)}')


def scoring_view(value):
    """Score-only comparison; source preservation is checked by the writers."""
    if isinstance(value, Mapping):
        return {key: scoring_view(child) for key, child in value.items() if key not in SCORING_SYNC_PRESERVED_FIELDS}
    if isinstance(value, list):
        return [scoring_view(child) for child in value]
    return value
