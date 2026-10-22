"""Read-only highlights from the already calculated v46 comparison."""


def build_comparison_highlights(comparison):
    """Rank metrics by absolute change; no assumptions about good/bad direction."""
    metrics = comparison.get('metrics', [])
    changed = [m for m in metrics if m['delta'] != 0]
    changed.sort(key=lambda m: (-abs(m['delta']), m['label']))
    return {
        'top': changed[:3],
        'changed_count': len(changed),
        'unchanged_count': len(metrics) - len(changed),
        'total_count': len(metrics),
    }
